"""Read-only BALLDONTLIE vs ESPN audit; never changes Hoopzaro predictions.

Usage (after placing BALLDONTLIE_API_KEY in the *local* environment):
    python bdl_shadow_audit.py --date 2026-11-17

GOAT trial requests are limited to five per minute, so the default delay is
12.5 seconds per BALLDONTLIE request. ESPN and BDL game/player IDs differ.
Only completed games and positive-minute player performances are compared.
"""

from __future__ import annotations

import argparse
from datetime import date
import json
import os
from pathlib import Path
import re
import time
import unicodedata

BDL_API = "https://api.balldontlie.io/v1"
COMPARE_FIELDS = ("PTS", "REB", "AST", "FG3M", "FG3A", "FGA", "OREB", "DREB", "TOV")
TEAM_ALIASES = {"GS": "GSW", "NY": "NYK", "SA": "SAS", "NO": "NOP", "PHO": "PHX", "BRK": "BKN", "WSH": "WAS"}


def normalized_team(value: object) -> str:
    code = str(value or "").strip().upper()
    return TEAM_ALIASES.get(code, code)


def normalized_name(value: object) -> str:
    value = unicodedata.normalize("NFKD", str(value or ""))
    value = "".join(c for c in value if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]", "", value.casefold())


def valid_number(value: object) -> float | None:
    try:
        result = float(value)
        return result if result == result and abs(result) != float("inf") else None
    except (ValueError, TypeError):
        return None


def minutes(value: object) -> float | None:
    if ":" in str(value or ""):
        try:
            m, s = str(value).split(":", 1)
            return float(m) + float(s) / 60
        except (ValueError, TypeError):
            return None
    return valid_number(value)


def bdl_player_rows(payload: list[dict]) -> list[dict]:
    """Normalize BDL boxscore fields to the existing ESPN column names."""
    rows = []
    for record in payload:
        player = record.get("player") or {}
        team = record.get("team") or {}
        played = minutes(record.get("min"))
        if played is None or played <= 0:
            continue  # Missing participation classifications must NOT be invented.
        name = " ".join(filter(None, (player.get("first_name"), player.get("last_name"))))
        code = normalized_team(team.get("abbreviation"))
        if not name or not code:
            continue
        rows.append({
            "PLAYER_NAME": name,
            "PLAYER_ID_BDL": player.get("id"),
            "TEAM_ABBREVIATION": code,
            "MIN": played,
            "PTS": valid_number(record.get("pts")),
            "REB": valid_number(record.get("reb")),
            "AST": valid_number(record.get("ast")),
            "FG3M": valid_number(record.get("fg3m")),
            "FG3A": valid_number(record.get("fg3a")),
            "FGA": valid_number(record.get("fga")),
            "OREB": valid_number(record.get("oreb")),
            "DREB": valid_number(record.get("dreb")),
            "TOV": valid_number(record.get("turnover")),
        })
    return rows


class BDLClient:
    def __init__(self, api_key: str, *, min_interval: float = 12.5, session=None,
                 clock=None, sleeper=None):
        if not api_key.strip():
            raise ValueError("Brak klucza BALLDONTLIE_API_KEY.")
        self._api_key = api_key.strip()
        if session is None:
            import requests  # Installed in Hoopzaro deployment, optional for offline tests.
            session = requests.Session()
        self._session = session
        self._min_interval = max(min_interval, 12.0)
        self._clock = clock or time.monotonic
        self._sleep = sleeper or time.sleep
        self._last_request: float | None = None

    def _get(self, endpoint: str, params: dict) -> dict:
        if not endpoint.startswith("/"):
            raise ValueError("Nieprawidłowa ścieżka API.")
        for attempt in range(3):
            now = self._clock()
            if self._last_request is not None:
                remaining = self._min_interval - (now - self._last_request)
                if remaining > 0:
                    self._sleep(remaining)
            self._last_request = self._clock()
            response = self._session.get(
                BDL_API + endpoint, params=params,
                headers={"Authorization": self._api_key, "Accept": "application/json"},
                timeout=20,
            )
            if response.status_code == 429 and attempt < 2:
                # Never bypass rate limits; honor the next conservative slot.
                retry_after = valid_number(response.headers.get("Retry-After"))
                self._sleep(max(self._min_interval, retry_after or 0))
                self._last_request = self._clock()
                continue
            response.raise_for_status()
            data = response.json()
            if not isinstance(data, dict) or not isinstance(data.get("data"), list):
                raise ValueError("BALLDONTLIE zwrócił niepoprawny format danych.")
            return data
        raise RuntimeError("Przekroczono limit zapytań BALLDONTLIE.")

    def pages(self, endpoint: str, params: dict) -> list[dict]:
        collected: list[dict] = []
        cursor = None
        seen: set[str] = set()
        for _ in range(100):  # Guard against a broken pagination cursor.
            query = {**params, "per_page": 100}
            if cursor is not None:
                query["cursor"] = cursor
            result = self._get(endpoint, query)
            collected.extend(result["data"])
            next_cursor = (result.get("meta") or {}).get("next_cursor")
            if next_cursor is None:
                return collected
            marker = str(next_cursor)
            if marker in seen:
                raise ValueError("Pętla paginacji BALLDONTLIE.")
            seen.add(marker)
            cursor = next_cursor
        raise ValueError("Zbyt wiele stron danych; przerwano audyt.")

    def games(self, game_date: str) -> list[dict]:
        return self.pages("/games", {"dates[]": game_date})

    def player_stats(self, game_id: int) -> list[dict]:
        return self.pages("/stats", {"game_ids[]": game_id})


def align_games(espn_games: list[dict], bdl_games: list[dict]) -> tuple[list[tuple[dict, dict]], list[str]]:
    """Match by opponents, not by mismatched ESPN/BDL numeric game IDs."""
    final_bdl = {}
    for game in bdl_games:
        if str(game.get("status_state") or "").lower() != "final":
            continue
        home = normalized_team((game.get("home_team") or {}).get("abbreviation"))
        away = normalized_team((game.get("visitor_team") or {}).get("abbreviation"))
        if home and away:
            final_bdl.setdefault((home, away), []).append(game)
    pairs = []
    warnings = []
    for game in espn_games:
        key = (normalized_team(game.get("home")), normalized_team(game.get("away")))
        matches = final_bdl.get(key) or []
        if len(matches) != 1:
            warnings.append(f"ESPN {game.get('game_id')}: brak jednoznacznego dopasowania BDL ({key})")
            continue
        other = matches.pop()
        pairs.append((game, other))
        for espn_key, bdl_key in (("home_score", "home_team_score"), ("away_score", "visitor_team_score")):
            expected, actual = valid_number(game.get(espn_key)), valid_number(other.get(bdl_key))
            if expected is not None and actual is not None and expected != actual:
                warnings.append(f"Wynik meczu {key}: {espn_key} ESPN={expected} BDL={actual}")
    return pairs, warnings


def compare_game(espn_rows: list[dict], bdl_rows: list[dict], *, game_label: str) -> dict:
    def index(rows: list[dict]) -> tuple[dict, list[str]]:
        result: dict[tuple[str, str], dict] = {}
        conflicts: set[tuple[str, str]] = set()
        for row in rows:
            key = (normalized_team(row.get("TEAM_ABBREVIATION")), normalized_name(row.get("PLAYER_NAME")))
            if key in result:
                conflicts.add(key)
                result.pop(key, None)
            elif key not in conflicts:
                result[key] = row
        return result, sorted(str(x) for x in conflicts)

    espn, espn_conflicts = index(espn_rows)
    bdl, bdl_conflicts = index(bdl_rows)
    common = sorted(espn.keys() & bdl.keys())
    diffs = []
    comparable = matches = 0
    minute_differences = []
    for key in common:
        for field in COMPARE_FIELDS:
            ev = valid_number(espn[key].get(field))
            bv = valid_number(bdl[key].get(field))
            if ev is None or bv is None:
                continue  # Missing data is unknown, never an assumed zero.
            comparable += 1
            if abs(ev - bv) < 1e-8:
                matches += 1
            else:
                diffs.append({"game": game_label, "team": key[0],
                              "player": espn[key]["PLAYER_NAME"], "field": field,
                              "espn": ev, "bdl": bv})
        em, bm = valid_number(espn[key].get("MIN")), valid_number(bdl[key].get("MIN"))
        if em is not None and bm is not None and abs(em - bm) > 1.0:
            minute_differences.append({"player": espn[key]["PLAYER_NAME"],
                                       "espn": em, "bdl": bm})
    return {
        "game": game_label,
        "espn_players": len(espn), "bdl_players": len(bdl),
        "matched_players": len(common),
        "only_espn": [espn[k]["PLAYER_NAME"] for k in sorted(espn.keys() - bdl.keys())],
        "only_bdl": [bdl[k]["PLAYER_NAME"] for k in sorted(bdl.keys() - espn.keys())],
        "comparable_fields": comparable, "matching_fields": matches,
        "mismatches": diffs, "minute_differences_over_1m": minute_differences,
        "duplicate_players": {"espn": espn_conflicts, "bdl": bdl_conflicts},
    }


def run(game_date: str, client: BDLClient, *, max_games: int = 10) -> dict:
    import requests
    from espn_player_data import fetch_boxscore
    from sources import ESPN_SCOREBOARD, memoized_json, parse_espn_schedule

    date.fromisoformat(game_date)  # Reject invalid dates before any API request.
    scoreboard, meta = memoized_json(
        "bdl-shadow-espn-calendar-" + game_date, ESPN_SCOREBOARD,
        params={"dates": game_date.replace("-", ""), "limit": 100},
        ttl_seconds=2 * 3600, request_timeout=10,
    )
    schedule = parse_espn_schedule(scoreboard)
    completed = schedule[schedule["status_code"] == 3].to_dict(orient="records")
    paired, warnings = align_games(completed, client.games(game_date))
    checks = []
    for espn_game, bdl_game in paired[:max_games]:
        label = f"{espn_game['away']} @ {espn_game['home']} ({game_date})"
        try:
            espn_rows = fetch_boxscore(espn_game)
            bdl_rows = bdl_player_rows(client.player_stats(int(bdl_game["id"])))
            if not espn_rows or not bdl_rows:
                warnings.append(f"{label}: co najmniej jedno źródło zwróciło pusty boxscore")
            checks.append(compare_game(espn_rows, bdl_rows, game_label=label))
        except (requests.RequestException, RuntimeError, ValueError, KeyError) as exc:
            # Do not log auth headers, query secrets, or personal account data.
            warnings.append(f"{label}: błąd pobierania/parsowania {type(exc).__name__}")
    field_count = sum(x["comparable_fields"] for x in checks)
    correct = sum(x["matching_fields"] for x in checks)
    return {
        "date": game_date,
        "provider": "BALLDONTLIE vs ESPN (nieoficjalne, niezależne źródło kontrolne)",
        "espn_calendar_stale": bool(meta.get("stale")),
        "completed_espn_games": len(completed),
        "matched_games": len(paired),
        "audited_games": len(checks),
        "matched_athlete_appearances": sum(x["matched_players"] for x in checks),
        "compared_stat_fields": field_count,
        "exact_matches": correct,
        "exact_match_rate": round(correct / field_count, 4) if field_count else None,
        "warnings": warnings,
        "games": checks,
        "notice": "Test jakości, NIE potwierdzenie licencji ani pochodzenia praw do danych.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Audyt porównawczy BDL/ESPN bez zmian w aplikacji")
    parser.add_argument("--date", required=True, help="Dzień meczów NBA (YYYY-MM-DD)")
    parser.add_argument("--output-dir", default=".bdl-audit", help="Lokalny katalog raportów")
    parser.add_argument("--max-games", type=int, default=10)
    parser.add_argument("--min-interval", type=float, default=12.5)
    args = parser.parse_args()
    if args.max_games < 1:
        parser.error("--max-games musi wynosić co najmniej 1")
    try:
        client = BDLClient(os.environ.get("BALLDONTLIE_API_KEY", ""),
                           min_interval=args.min_interval)
    except ValueError as exc:
        parser.error(str(exc) + " Ustaw go jako sekret środowiskowy; nie wpisuj w kodzie.")
    result = run(args.date, client, max_games=args.max_games)
    folder = Path(args.output_dir)
    folder.mkdir(parents=True, exist_ok=True)
    filename = folder / f"bdl-shadow-{args.date}.json"
    filename.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf8")
    print(f"Zapisano: {filename} | mecze={result['audited_games']} | zgodne pola="
          f"{result['exact_matches']}/{result['compared_stat_fields']}; "
          f"ostrzeżenia={len(result['warnings'])}")
    return 0 if result["audited_games"] and result["compared_stat_fields"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
