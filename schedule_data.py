"""Fetch requested NBA dates without restricting the calendar to current month."""
from datetime import datetime, timezone

import pandas as pd

from sources import ESPN_SCOREBOARD, memoized_json, parse_espn_schedule
from viewer_time import games_on_day, local_day_start_end


def required_utc_months(day, zone):
    start, end = local_day_start_end(day, zone)
    # Subtract a microsecond from the exclusive end to avoid an unnecessary next month.
    return sorted({start.strftime("%Y%m"), (end - pd.Timedelta(microseconds=1)).strftime("%Y%m")})


def missing_archive_months(day, zone, current_utc=None):
    """The primary ESPN adapter already supplies this and next UTC month."""
    now = pd.Timestamp(current_utc) if current_utc is not None else pd.Timestamp.now(tz="UTC")
    now = now.tz_localize("UTC") if now.tzinfo is None else now.tz_convert("UTC")
    next_month = now + pd.offsets.MonthBegin(1)
    loaded = {now.strftime("%Y%m"), next_month.strftime("%Y%m")}
    return [m for m in required_utc_months(day, zone) if m not in loaded]


def fetch_month(month, nonce=0):
    """ESPN monthly archive, cached independently by requested month."""
    payload, meta = memoized_json(
        "espn-nba-scoreboard-month-" + month,
        ESPN_SCOREBOARD, params={"dates":month, "limit":500},
        ttl_seconds=20 * 60, refresh=nonce > 0
    )
    return parse_espn_schedule(payload), meta


def fixtures_for_day(schedule, day, zone, nonce=0, fetcher=None, now_utc=None):
    """Join only missing month archives, then filter by the viewer's local date.

    Never substitute predicted scores for missing official match information.
    """
    all_rows = schedule.copy() if schedule is not None else pd.DataFrame()
    errors = []
    fetcher = fetcher or fetch_month
    for month in missing_archive_months(day, zone, current_utc=now_utc):
        try:
            archived, metadata = fetcher(month, nonce)
            if archived is not None and not archived.empty:
                all_rows = pd.concat([all_rows, archived], ignore_index=True)
            if metadata.get("stale"):
                errors.append(month + ": zapis z pamięci")
        except Exception as exc:
            errors.append(month + ": " + str(exc)[:100])
    if not all_rows.empty:
        all_rows["start_utc"] = pd.to_datetime(all_rows["start_utc"], utc=True, errors="coerce")
        all_rows = all_rows.dropna(subset=["start_utc"]).drop_duplicates("game_id", keep="first")
    return games_on_day(all_rows, day, zone), errors
