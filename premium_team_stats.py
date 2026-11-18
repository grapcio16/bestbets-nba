"""Paid team trends from verified completed NBA season scoreboards.

No upcoming game, incomplete result, approximate opponent or inferred
advanced rating may be substituted for an observed stat.
"""
from __future__ import annotations

from math import isfinite

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
                  "pace": rating.get("pace") if verified_rating else None}
        # No fake numeric zero when ESPN and NBA Stats had no reliable data.
        if rows or verified_rating:
            results[code] = values
    return {"teams": results, "source": "ESPN · zakończone mecze sezonu 2026/27",
            "advanced_source": "NBA Stats · zweryfikowany cache",
            "partial": len(results) < len(TEAM_FULL)}
