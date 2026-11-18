"""Historical NBA player averages for the Premium Players directory.

Only verified completed-game rows are summarized.  The caller must enforce
Premium entitlement before fetching these values or placing them in a page
payload.  This module intentionally contains no predictions or bet advice.
"""
from __future__ import annotations

import math

import pandas as pd

from core import norm_name, normalize_logs


def load_verified_player_history(player_id: str, name: str, team: str, season: str,
                                 gamelog_fetch=None, recent_team_fetch=None) -> dict:
    """Prefer ESPN's per-athlete season; use real recent boxscores as fallback.

    A fall back is explicitly a *partial sample*. It never invents appearances
    or includes another athlete with the same name. Fetches remain bounded to
    eight completed games for only the selected team on primary-feed failure.
    """
    if not str(player_id).isascii() or not str(player_id).isdecimal():
        raise ValueError("Nieprawidłowy identyfikator zawodnika")
    if gamelog_fetch is None:
        from espn_player_data import detailed_espn_gamelog
        gamelog_fetch = detailed_espn_gamelog
    if recent_team_fetch is None:
        from roster_data import team_recent_logs
        recent_team_fetch = team_recent_logs
    try:
        logs, metadata = gamelog_fetch(player_id, name, team, season)
        result = build_player_averages(logs, metadata)
        if player_id in result["id_rows"]:
            return result
        raise ValueError("Brak zweryfikowanego sezonowego występu zawodnika")
    except Exception as primary_error:
        # A missing ESPN athlete history is common during outages or just after
        # roster changes. Only real, finished boxscores may fill the gap.
        try:
            logs, metadata = recent_team_fetch(team, season, games_per_team=8)
            if not isinstance(logs, pd.DataFrame) or logs.empty or "PLAYER_ID" not in logs:
                raise ValueError("Brak boxscore zawodnika")
            own = logs[logs["PLAYER_ID"].astype(str) == str(player_id)]
            if own.empty:
                raise ValueError("Zawodnik nie wystąpił w zweryfikowanej próbce")
            meta = dict(metadata or {})
            meta["source"] = "ESPN · ostatnie potwierdzone boxscore drużyny"
            meta["partial"] = True
            result = build_player_averages(own, meta)
            if player_id not in result["id_rows"]:
                raise ValueError("Niekompletne boxscore zawodnika")
            return result
        except Exception:
            raise ValueError("Historia zawodnika chwilowo niedostępna w ESPN") from primary_error


def verified_roster_targets(requested_ids, catalog, limit: int = 7) -> list[dict]:
    """Resolve a bounded set of browser IDs against the server's actual roster.

    A browser may request which visible athletes to load, but it cannot supply
    the name, team, or Premium entitlement used for the underlying lookup.
    """
    if not isinstance(requested_ids, list) or not isinstance(catalog, dict):
        return []
    allowed = {}
    for player in catalog.get("players", []):
        if not isinstance(player, dict):
            continue
        identifier = str(player.get("id") or "")
        name = str(player.get("name") or "").strip()
        team = str(player.get("team") or "").strip()
        if identifier.isascii() and identifier.isdecimal() and len(identifier) <= 12 and name and team:
            allowed[identifier] = {"id": identifier, "name": name, "team": team}
    selected, seen = [], set()
    for identifier in requested_ids[:32]:
        identifier = str(identifier)
        if identifier in allowed and identifier not in seen:
            selected.append(allowed[identifier])
            seen.add(identifier)
            if len(selected) >= limit:
                break
    return selected


def build_player_averages(raw: pd.DataFrame, metadata: dict | None = None) -> dict:
    """Summarize verified appearances, keyed by athlete ID when available.

    Missing three-point data does not invalidate otherwise complete PTS/REB/AST
    observations. Every shooting rate includes its own observation count.
    """
    meta = metadata if isinstance(metadata, dict) else {}
    source = str(meta.get("source") or "NBA / ESPN")[:80]
    complete = source.lower() in {"nba stats", "cache"} and not meta.get("partial")
    result = {"rows": {}, "id_rows": {}, "scope": "sezon zasadniczy" if complete else "dostępna próbka meczów",
              "source": source, "season": "2026/27", "partial": not complete}
    if not isinstance(raw, pd.DataFrame) or raw.empty:
        result["error"] = "Brak potwierdzonych statystyk zawodników w źródle."
        return result

    logs = normalize_logs(raw)
    logs = logs[(logs["MIN"] > 0) & (logs["PTS"].notna()) &
                (logs["REB"].notna()) & (logs["AST"].notna()) &
                (logs[["PTS", "REB", "AST"]] >= 0).all(axis=1)].copy()
    if logs.empty:
        result["error"] = "Źródło nie zwróciło poprawnych rozegranych spotkań."
        return result
    logs["_name_key"] = logs["PLAYER_NAME"].map(norm_name)
    logs = logs[logs["_name_key"].str.len() > 2]
    # Player IDs come from the verified provider, not browser-provided names.
    # Identical display names can belong to different athletes.
    if "PLAYER_ID" in logs:
        ids = logs["PLAYER_ID"].fillna("").astype(str).str.strip()
        logs["_identity"] = ids.where(ids.str.fullmatch(r"\d{1,12}"), "name:" + logs["_name_key"])
    else:
        logs["_identity"] = "name:" + logs["_name_key"]
    # If a source includes both a duplicate record and its corrected version,
    # count the athlete's finished match once.
    if "GAME_ID" in logs:
        game_ids = logs["GAME_ID"].fillna("").astype(str).str.strip()
        # A missing game ID must not collapse every otherwise dated match into
        # one. Dates here are provider timestamps, never fabricated IDs.
        logs["_game_key"] = game_ids.where(game_ids.ne(""),
                                           "date:" + logs["GAME_DATE"].astype(str))
        logs = logs.drop_duplicates(subset=["_identity", "_game_key"], keep="last")
    name_owners = logs.groupby("_name_key")["_identity"].nunique().to_dict()
    for identity, games in logs.groupby("_identity", sort=False):
        games = games.sort_values("GAME_DATE")
        latest = games.iloc[-1]
        name_key = str(latest["_name_key"])
        made = games["FG3M"]
        attempts = games["FG3A"]
        consistent = made.isna() | attempts.isna() | (made <= attempts)
        valid_made = games[(made.notna()) & (made >= 0) & consistent]
        valid_attempts = games[(attempts.notna()) & (attempts >= 0) & consistent]
        valid_pct = games[(attempts.notna()) & (attempts >= 0) &
                          (made.notna()) & (made >= 0) & (made <= attempts)]
        metrics = {
            "pts": round(float(games["PTS"].mean()), 1),
            "reb": round(float(games["REB"].mean()), 1),
            "ast": round(float(games["AST"].mean()), 1),
            "three_pm": round(float(valid_made["FG3M"].mean()), 1) if not valid_made.empty else None,
            "three_pa": round(float(valid_attempts["FG3A"].mean()), 1) if not valid_attempts.empty else None,
            "three_pct": None,
            "games": int(len(games)),
            "three_pm_games": int(len(valid_made)),
            "three_pa_games": int(len(valid_attempts)),
            "three_pct_games": int(len(valid_pct)),
            "last_game": latest["GAME_DATE"].strftime("%Y-%m-%d"),
            "last_team": str(latest["TEAM_ABBREVIATION"] or "")[:5],
        }
        total_attempts = float(valid_pct["FG3A"].sum())
        if math.isfinite(total_attempts) and total_attempts > 0:
            metrics["three_pct"] = round(
                100 * float(valid_pct["FG3M"].sum()) / total_attempts, 1)
        if identity.isdecimal():
            result["id_rows"][identity] = metrics
        # Legacy name lookup is safe only when the name is unambiguous.
        if name_owners[name_key] == 1:
            result["rows"][name_key] = metrics
    return result
