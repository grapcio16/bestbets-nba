"""Verified regular-season NBA standings for the public Centrum team-form widget.

The short ESPN scoreboard window is never sufficient for a season W-L record.
Fetch the season's actual conference standings and label missing teams truthfully.
"""
from __future__ import annotations

import math
import re

from teams import TEAM_FULL, TEAM_MAP

STANDINGS_URL = "https://site.api.espn.com/apis/v2/sports/basketball/nba/standings"
SEASON_YEAR = 2027
SEASON_LABEL = "2026/27"


def _integer(raw):
    """Accept whole nonnegative numeric values, never infer missing stats as zero."""
    try:
        if raw is None or isinstance(raw, bool) or str(raw).strip() == "":
            return None
        number = float(raw)
        if not math.isfinite(number) or not number.is_integer() or number < 0 or number > 82:
            return None
        return int(number)
    except (TypeError, ValueError, OverflowError):
        return None


def _points_per_game(stats: dict, games: int):
    """Use a verified season scoring average, never the short scoreboard sample."""
    if games <= 0:
        return None
    normalized = {re.sub(r"[^a-z0-9]", "", key): value
                  for key, value in stats.items()}
    for key in ("avgpointsfor", "pointspergame", "avgpoints", "ppg"):
        raw = normalized.get(key)
        try:
            value = float(raw)
            if math.isfinite(value) and 50 <= value <= 160:
                return round(value, 1)
        except (ValueError, TypeError, OverflowError):
            pass
    # Some feeds supply only total points scored across regular-season games.
    # Accept this fallback only when it is unambiguously a total, not an average.
    if games:
        try:
            total = float(normalized.get("pointsfor"))
            average = total / games
            if math.isfinite(total) and total >= games * 50 and 50 <= average <= 160:
                return round(average, 1)
        except (ValueError, TypeError, OverflowError):
            pass
    return None


def parse_season_standings(payload: dict, expected_year: int = SEASON_YEAR) -> dict:
    """Parse ESPN's children[].standings.entries[] format without invented records."""
    if not isinstance(payload, dict):
        raise ValueError("Brak tabeli NBA")
    season = payload.get("season")
    year = season.get("year") if isinstance(season, dict) else season
    if year is not None:
        try:
            if int(year) != expected_year:
                raise ValueError("Tabela NBA pochodzi z innego sezonu")
        except (TypeError, ValueError) as exc:
            raise ValueError("Niezweryfikowany sezon tabeli NBA") from exc

    records = {}
    pending = [payload]
    while pending:
        node = pending.pop()
        if not isinstance(node, dict):
            continue
        pending.extend(node.get("children", []) if isinstance(node.get("children"), list) else [])
        standings = node.get("standings") or {}
        entries = standings.get("entries", []) if isinstance(standings, dict) else []
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            team = entry.get("team") or {}
            code = str(team.get("abbreviation") or "").strip().upper() if isinstance(team, dict) else ""
            if code not in TEAM_FULL:
                # ESPN sometimes emits nonstandard abbreviations (e.g. UTAH).
                # Resolve the official full team name, never an approximate match.
                code = TEAM_MAP.get(str(team.get("displayName") or "").strip(), "")
            if code not in TEAM_FULL:
                continue
            stats = {}
            for item in entry.get("stats", []):
                if not isinstance(item, dict):
                    continue
                key = str(item.get("name") or item.get("abbreviation") or "").strip().lower()
                value = item.get("value")
                if value is None:
                    value = item.get("displayValue")
                stats[key] = value
            wins = _integer(stats.get("wins", stats.get("w")))
            losses = _integer(stats.get("losses", stats.get("l")))
            if wins is None or losses is None or wins + losses > 82:
                continue
            record = {"wins": wins, "losses": losses, "sample": wins + losses,
                      "record_verified": True,
                      "ppg": _points_per_game(stats, wins + losses)}
            # Repeated conference/division entries must agree.
            if code in records and records[code] != record:
                raise ValueError("Sprzeczne bilanse drużyny NBA")
            records[code] = record
    if len(records) != len(TEAM_FULL):
        raise ValueError("Tabela sezonu NBA jest niekompletna")
    return records


def fetch_season_standings():
    """One short, cached standings request (never 30 per-team requests)."""
    from sources import memoized_json

    raw, meta = memoized_json(
        "bb-centre-espn-season-standings-" + str(SEASON_YEAR),
        STANDINGS_URL,
        params={"season": SEASON_YEAR, "seasontype": 2, "type": 0},
        ttl_seconds=15 * 60,
        request_timeout=5,
    )
    return parse_season_standings(raw), meta


def apply_season_form(snapshot: dict, records=None, meta=None) -> dict:
    """Override truncated last-week form. Missing provider data stays unknown."""
    records = records if isinstance(records, dict) else {}
    meta = meta or {}
    snapshot["form_period"] = SEASON_LABEL
    snapshot["form_available"] = bool(records)
    snapshot["form_stale"] = bool(meta.get("stale")) if records else False
    options = []
    for item in snapshot.get("form_options") or []:
        code = item.get("team")
        source = records.get(code)
        options.append({
            **item,
            "wins": source["wins"] if source else None,
            "losses": source["losses"] if source else None,
            "sample": source["sample"] if source else 0,
            "record_verified": bool(source),
            "ppg": source.get("ppg") if source else None,
        })
    snapshot["form_options"] = options
    by_code = {item["team"]: item for item in options}
    defaults = [by_code[row["team"]] for row in snapshot.get("form", [])
                if row.get("team") in by_code]
    if not defaults:
        defaults = sorted(options, key=lambda item: (
            not item["record_verified"], -item["wins"] if item["record_verified"] else 0,
            item["team"],
        ))[:2]
    snapshot["form"] = defaults[:2]
    return snapshot
