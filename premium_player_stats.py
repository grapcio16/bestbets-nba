"""Historical NBA player averages for the Premium Players directory.

Only verified completed-game rows are summarized.  The caller must enforce
Premium entitlement before fetching these values or placing them in a page
payload.  This module intentionally contains no predictions or bet advice.
"""
from __future__ import annotations

import math

import pandas as pd

from core import norm_name, normalize_logs


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
    """Return per-player season/sample means, using attempts for true 3P%.

    The summary is keyed by normalized player name because the public ESPN
    roster and NBA Stats game logs do not necessarily share athlete IDs.
    Missing 3-point attempts are not guessed from made shots.
    """
    meta = metadata if isinstance(metadata, dict) else {}
    source = str(meta.get("source") or "NBA / ESPN")[:80]
    complete = source.lower() in {"nba stats", "cache"} and not meta.get("partial")
    result = {"rows": {}, "scope": "sezon zasadniczy" if complete else "dostępna próbka meczów",
              "source": source, "season": "2026/27", "partial": not complete}
    if not isinstance(raw, pd.DataFrame) or raw.empty:
        result["error"] = "Brak potwierdzonych statystyk zawodników w źródle."
        return result

    logs = normalize_logs(raw)
    logs = logs[(logs["MIN"] > 0) & (logs["PTS"].notna()) &
                (logs["REB"].notna()) & (logs["AST"].notna()) &
                (logs["FG3M"].notna())].copy()
    if logs.empty:
        result["error"] = "Źródło nie zwróciło poprawnych rozegranych spotkań."
        return result
    logs["_name_key"] = logs["PLAYER_NAME"].map(norm_name)
    logs = logs[logs["_name_key"].str.len() > 2]
    # If a source includes both a duplicate record and its corrected version,
    # count the athlete's finished match once.
    if "GAME_ID" in logs and logs["GAME_ID"].notna().any():
        logs = logs.drop_duplicates(subset=["_name_key", "GAME_ID"], keep="last")
    for name_key, games in logs.groupby("_name_key", sort=False):
        games = games.sort_values("GAME_DATE")
        latest = games.iloc[-1]
        metrics = {
            "pts": round(float(games["PTS"].mean()), 1),
            "reb": round(float(games["REB"].mean()), 1),
            "ast": round(float(games["AST"].mean()), 1),
            "three_pm": round(float(games["FG3M"].mean()), 1),
            "three_pa": None,
            "three_pct": None,
            "games": int(len(games)),
            "last_team": str(latest["TEAM_ABBREVIATION"] or "")[:5],
        }
        attempts = games["FG3A"]
        valid = games[(attempts.notna()) & (attempts >= 0) &
                      (games["FG3M"] >= 0) & (games["FG3M"] <= attempts)]
        total_attempts = float(valid["FG3A"].sum())
        if not valid.empty:
            metrics["three_pa"] = round(float(valid["FG3A"].mean()), 1)
        if math.isfinite(total_attempts) and total_attempts > 0:
            metrics["three_pct"] = round(
                100 * float(valid["FG3M"].sum()) / total_attempts, 1)
        result["rows"][name_key] = metrics
    return result
