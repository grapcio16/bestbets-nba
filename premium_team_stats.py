"""Paid team trends from verified completed NBA season scoreboards.

No upcoming game, incomplete result, approximate opponent or inferred
advanced rating may be substituted for an observed stat.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from math import isfinite
import re

import pandas as pd

from teams import TEAM_FULL


def _score(value):
    try:
        result = float(value)
        return result if isfinite(result) and 55 <= result <= 200 else None
    except (ValueError, TypeError, OverflowError):
        return None


def _average(values):
    return round(sum(values) / len(values), 1) if values else None


def load_verified_advanced(season: str, read_verified_cache, fetch_official) -> dict:
    """Try authentic NBA Advanced once; never infer ratings from game scores.

    Data loaders are injected so validation can run without Streamlit or the
    network. The official fetch adapter bounds its timeout and caches failures.
    """
    from simulation_engine import advanced_ratings

    verified = read_verified_cache(season)
    if not isinstance(verified, pd.DataFrame) or verified.empty:
        verified = pd.DataFrame()
        try:
            loaded, meta = fetch_official("Drużyny • advanced (pace/def)", season)
            if not meta.get("stale"):
                verified = loaded
        except Exception:
            # Hosting may be blocked by stats.nba.com. Use verified ESPN
            # history in the frontend, not approximate possession metrics.
            pass
    return advanced_ratings(verified)


_ESPN_ALIASES = {"GS": "GSW", "NY": "NYK", "SA": "SAS", "NO": "NOP",
                 "PHO": "PHX", "WSH": "WAS", "BRK": "BKN"}


def _stat_key(value):
    return re.sub(r"[^a-z0-9]", "", str(value or "").lower())


def _whole(value):
    try:
        number = float(value)
        return int(number) if isfinite(number) and number >= 0 and number.is_integer() else None
    except (ValueError, TypeError, OverflowError):
        return None


def _box_stat(items, aliases, *, attempts=False):
    """Accept ESPN's explicitly named team totals, not inferred percentages."""
    if not isinstance(items, list):
        return None
    for alias in aliases:
        for item in items:
            if not isinstance(item, dict):
                continue
            keys = {_stat_key(item.get(field)) for field in
                    ("name", "abbreviation", "label", "shortDisplayName")}
            if _stat_key(alias) not in keys:
                continue
            raw = item.get("displayValue", item.get("value"))
            if attempts and isinstance(raw, str) and "-" in raw:
                parts = raw.split("-", 1)
                made, total = _whole(parts[0]), _whole(parts[1])
                if made is not None and total is not None and made <= total:
                    return total
            elif not attempts or _stat_key(alias) in (
                    "fieldgoalsattempted", "freethrowsattempted", "fga", "fta"):
                number = _whole(raw)
                if number is not None:
                    return number
    return None


def parse_espn_possessions_boxscore(payload: dict, game: dict) -> dict | None:
    """Read *both* teams' traditional boxscores from one verified final game.

    This estimates possessions from real FGA, FTA, OREB and turnovers. It is
    deliberately NOT advertised as the official NBA Stats advanced feed.
    """
    if not isinstance(payload, dict) or not isinstance(game, dict):
        return None
    expected_id = str(game.get("game_id") or "")
    header = payload.get("header") or {}
    competitions = header.get("competitions") or []
    competition = competitions[0] if isinstance(competitions, list) and competitions else {}
    observed_id = str(competition.get("id") or header.get("id") or "")
    if observed_id and observed_id != expected_id:
        return None
    blocks = (payload.get("boxscore") or {}).get("teams") or []
    if not isinstance(blocks, list):
        return None
    codes = (str(game.get("home") or ""), str(game.get("away") or ""))
    if len(set(codes)) != 2 or any(code not in TEAM_FULL for code in codes):
        return None
    observations = {}
    for block in blocks:
        if not isinstance(block, dict):
            continue
        team = block.get("team") or {}
        code = _ESPN_ALIASES.get(str(team.get("abbreviation") or "").upper(),
                                 str(team.get("abbreviation") or "").upper())
        if code not in codes or code in observations:
            continue
        stats = block.get("statistics") or []
        fga = _box_stat(stats, ("fieldGoalsAttempted", "fga",
                                "fieldGoalsMade-fieldGoalsAttempted", "FG"), attempts=True)
        fta = _box_stat(stats, ("freeThrowsAttempted", "fta",
                                "freeThrowsMade-freeThrowsAttempted", "FT"), attempts=True)
        oreb = _box_stat(stats, ("offensiveRebounds", "OREB", "OR"))
        tov = _box_stat(stats, ("totalTurnovers", "turnovers", "TO", "TOV"))
        if any(value is None for value in (fga, fta, oreb, tov)):
            return None
        if not (50 <= fga <= 130 and fta <= 65 and oreb <= 40 and
                oreb <= fga and tov <= 45):
            return None
        possessions = fga + 0.44 * fta - oreb + tov
        if not 65 <= possessions <= 145:
            return None
        observations[code] = possessions
    if len(observations) != 2:
        return None
    home, away = codes
    hs, aps = _score(game.get("home_score")), _score(game.get("away_score"))
    if hs is None or aps is None or hs == aps:
        return None
    # Both sides observed in the same boxscore. Averaging their possession
    # estimates reduces the asymmetry from terminal possession and team ORB.
    possessions = (observations[home] + observations[away]) / 2
    status = (competition.get("status") or {}) if isinstance(competition, dict) else {}
    period = _whole(status.get("period"))
    duration = 48 + max(0, (period or 4) - 4) * 5
    return {"home": home, "away": away, "points": {home: hs, away: aps},
            "possessions": possessions, "duration": duration}


def estimate_team_ratings_from_boxscores(team_code: str, games: pd.DataFrame | None,
                                         fetch_summary, *, max_games=10,
                                         min_verified_games=4) -> dict | None:
    """Calculate OFF/DEF/PACE from verified ESPN final boxscores on demand.

    These are documented estimates from observed possessions, NOT the
    proprietary exact possession counts in NBA Stats advanced.
    """
    if team_code not in TEAM_FULL or not isinstance(games, pd.DataFrame) or games.empty:
        return None
    frame = games.copy()
    if "start_utc" not in frame or "game_id" not in frame:
        return None
    frame["start_utc"] = pd.to_datetime(frame["start_utc"], utc=True, errors="coerce")
    frame = frame.dropna(subset=["start_utc"]).sort_values("start_utc", ascending=False)
    frame = frame.drop_duplicates(subset=["game_id"])
    now = pd.Timestamp.now(tz="UTC")
    finals = []
    for row in frame.to_dict("records"):
        if team_code not in (row.get("home"), row.get("away")):
            continue
        date = row["start_utc"]
        event = str(row.get("game_id") or "")
        if not (pd.Timestamp("2026-10-01", tz="UTC") <= date < now and
                re.fullmatch(r"\d{6,10}", event)):
            continue
        if _whole(row.get("status_code")) != 3:
            continue
        if _score(row.get("home_score")) is None or _score(row.get("away_score")) is None:
            continue
        finals.append(row)
        if len(finals) == max_games:
            break
    if not finals:
        return None
    confirmed = []
    with ThreadPoolExecutor(max_workers=min(4, len(finals))) as pool:
        futures = {pool.submit(fetch_summary, row): row for row in finals}
        for future in as_completed(futures):
            try:
                game = parse_espn_possessions_boxscore(future.result(), futures[future])
                if game is not None:
                    confirmed.append(game)
            except (RuntimeError, TypeError, ValueError, KeyError, OSError):
                continue
    if len(confirmed) < min_verified_games:
        return None
    points = sum(g["points"][team_code] for g in confirmed)
    allowed = sum(g["points"][g["away"] if team_code == g["home"] else g["home"]]
                  for g in confirmed)
    possessions = sum(g["possessions"] for g in confirmed)
    duration = sum(g["duration"] for g in confirmed)
    return {"off": round(100 * points / possessions, 1),
            "def": round(100 * allowed / possessions, 1),
            "pace": round(48 * possessions / duration, 1),
            "rating_source": "ESPN — szacunek z boxscore",
            "rating_sample": len(confirmed), "rating_estimated": True}


def build_team_analytics(games: pd.DataFrame | None, advanced: dict | None = None) -> dict:
    """Only paid, historical metrics from completed season games.

    Advanced ratings are optional and must already have passed the official
    NBA Stats cache validation (see simulation_engine.advanced_ratings).
    """
    advanced = advanced if isinstance(advanced, dict) else {}
    history = {code: [] for code in TEAM_FULL}
    if isinstance(games, pd.DataFrame) and not games.empty:
        frame = games.copy()
        if "start_utc" not in frame:
            return {"teams": {}, "source": "ESPN", "partial": True,
                    "error": "Brak potwierdzonych dat spotkań."}
        frame["start_utc"] = pd.to_datetime(frame["start_utc"], utc=True, errors="coerce")
        frame = frame.dropna(subset=["start_utc"]).sort_values("start_utc")
        if "game_id" in frame:
            frame = frame.drop_duplicates(subset=["game_id"], keep="last")
        for row in frame.to_dict("records"):
            # A completed result must also be in the past and in this season.
            start = row["start_utc"]
            if not (pd.Timestamp("2026-10-01", tz="UTC") <= start <
                    min(pd.Timestamp("2027-07-01", tz="UTC"), pd.Timestamp.now(tz="UTC"))):
                continue
            try:
                if int(row.get("status_code") or 0) != 3:
                    continue
            except (ValueError, TypeError, OverflowError):
                continue
            home, away = str(row.get("home") or ""), str(row.get("away") or "")
            if home not in TEAM_FULL or away not in TEAM_FULL or home == away:
                continue
            hs, aps = _score(row.get("home_score")), _score(row.get("away_score"))
            if hs is None or aps is None or hs == aps:
                continue
            history[home].append((hs, aps, "home", hs > aps))
            history[away].append((aps, hs, "away", aps > hs))

    results = {}
    for code, rows in history.items():
        last = rows[-10:]
        rating = advanced.get(code, {}) if isinstance(advanced.get(code), dict) else {}
        verified_rating = rating.get("source") == "NBA Stats — advanced"
        values = {"sample": len(last), "points": _average([r[0] for r in last]),
                  "allowed": _average([r[1] for r in last]),
                  "home": _average([r[0] for r in rows if r[2] == "home"]),
                  "away": _average([r[0] for r in rows if r[2] == "away"]),
                  "last5": "".join("W" if r[3] else "L" for r in rows[-5:]),
                  "off": rating.get("off") if verified_rating else None,
                  "def": rating.get("def") if verified_rating else None,
                  "pace": rating.get("pace") if verified_rating else None,
                  "rating_source": "NBA Stats — advanced" if verified_rating else None,
                  "rating_sample": None, "rating_estimated": False}
        # No fake numeric zero when ESPN and NBA Stats had no reliable data.
        if rows or verified_rating:
            results[code] = values
    return {"teams": results, "source": "ESPN · zakończone mecze sezonu 2026/27",
            "advanced_source": "NBA Stats · zweryfikowany cache",
            "partial": len(results) < len(TEAM_FULL)}
