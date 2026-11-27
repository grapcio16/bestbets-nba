"""Conservative calendar gate for V8.03's 2026-27 research evidence.

Existing archive has no provider season-type field. Until it is available,
use the official season window, excluding the Cup final and All-Star break.
Unknown seasons fail closed; never mutate or relabel the historical archive.
"""
import pandas as pd

SOURCE = "https://pr.nba.com/2026-27-nba-regular-season-schedule"
SEASON = "2026-27"
FIRST_TIP = pd.Timestamp("2026-10-20T19:00:00Z")
END_EXCLUSIVE = pd.Timestamp("2027-04-12T04:00:00Z")
EXCLUDED_LOCAL_DATES = frozenset(("2026-12-11", "2027-02-19", "2027-02-20", "2027-02-21"))


def calendar_supported(season):
    return season == SEASON


def in_regular_window(row, season):
    if not calendar_supported(season) or row.get("season", season) != season:
        return False
    try:
        tip = pd.to_datetime(row.get("start_utc"), utc=True, errors="coerce")
        if pd.isna(tip) or not FIRST_TIP <= tip < END_EXCLUSIVE:
            return False
        return tip.tz_convert("America/New_York").date().isoformat() not in EXCLUDED_LOCAL_DATES
    except (TypeError, ValueError, OverflowError):
        return False


def filter_regular_window(rows, season):
    return [row for row in rows if in_regular_window(row, season)]
