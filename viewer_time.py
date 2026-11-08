"""Browser-local NBA schedule helpers; all source instants are UTC."""
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError, available_timezones

import pandas as pd

COMMON_ZONES = ("UTC", "Europe/Warsaw", "Europe/London", "America/New_York",
                "America/Los_Angeles", "Asia/Tokyo", "Australia/Sydney")


def choices():
    """Searchable full IANA database, with stable fallbacks on limited machines."""
    return ["Automatyczna"] + sorted(set(available_timezones()) | set(COMMON_ZONES))


def resolve_zone(selected="Automatyczna", browser=None):
    candidate = browser if selected in ("Automatyczna", "", None) else selected
    try:
        return ZoneInfo(str(candidate or "UTC"))
    except (ZoneInfoNotFoundError, TypeError, ValueError, KeyError):
        return timezone.utc


def localize(values, zone):
    """UTC instant -> civil datetime in selected zone (including DST)."""
    result = pd.to_datetime(values, utc=True, errors="coerce")
    if isinstance(result, pd.Series):
        return result.dt.tz_convert(zone)
    if isinstance(result, pd.DatetimeIndex):
        return result.tz_convert(zone)
    return result.tz_convert(zone) if not pd.isna(result) else result


def local_day_start_end(day, zone):
    """Use each *local midnight*; a DST day may have 23 or 25 hours."""
    start = pd.Timestamp(datetime.combine(day, time.min)).tz_localize(zone)
    end = pd.Timestamp(datetime.combine(day + timedelta(days=1), time.min)).tz_localize(zone)
    return start.tz_convert("UTC"), end.tz_convert("UTC")


def games_on_day(games, day, zone):
    if games is None or games.empty:
        return games.copy() if isinstance(games, pd.DataFrame) else pd.DataFrame()
    start, end = local_day_start_end(day, zone)
    when = pd.to_datetime(games["start_utc"], utc=True, errors="coerce")
    return games.loc[(when >= start) & (when < end)].copy()


def format_local_date(ts, zone, pattern="%d.%m.%Y %H:%M"):
    t = localize(ts, zone)
    return t.strftime(pattern) if not pd.isna(t) else "—"
