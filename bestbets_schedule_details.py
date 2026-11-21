"""Verified on-demand ESPN details for a FREE NBA schedule game.

No calls are made until a visitor expands a completed/live game.  The
scoreboard owns the event identity; browser-provided IDs are never authority.
"""
from __future__ import annotations

import math
import re

from teams import TEAM_FULL

_ALIASES = {"GS":"GSW", "NY":"NYK", "SA":"SAS", "NO":"NOP",
            "PHO":"PHX", "WSH":"WAS", "BRK":"BKN"}


def _code(competitor):
    team = competitor.get("team") or {}
    name = str(team.get("abbreviation") or "").upper()
    return _ALIASES.get(name, name)


def _integer(value, max_value=300):
    try:
        value = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return int(value) if math.isfinite(value) and value.is_integer() and 0 <= value <= max_value else None


def _stat_key(value):
    return re.sub(r"[^a-z0-9]", "", str(value or "").lower())


def _stat_value(block, names, *, percent=False):
    allowed = {_stat_key(name) for name in names}
    for item in (block.get("statistics") or []):
        if not isinstance(item, dict):
            continue
        keys = {_stat_key(item.get(field)) for field in ("name", "abbreviation", "label", "shortDisplayName")}
        if not (keys & allowed):
            continue
        raw = item.get("displayValue", item.get("value"))
        try:
            value = float(str(raw).strip().rstrip("%"))
        except (TypeError, ValueError, OverflowError):
            continue
        if not math.isfinite(value) or value < 0 or value > (100 if percent else 300):
            continue
        return f"{value:.1f}%" if percent else str(int(value)) if value.is_integer() else f"{value:.1f}"
    return None


def parse_game_details(payload, game_id, away, home):
    """Parse only teams and statistics verified against the selected event."""
    if not isinstance(payload, dict) or away not in TEAM_FULL or home not in TEAM_FULL or away == home:
        raise ValueError("Nieprawidłowy mecz")
    header = payload.get("header") or {}
    competitions = header.get("competitions") or []
    comp = competitions[0] if isinstance(competitions, list) and competitions else {}
    if str(header.get("id") or "") != game_id or str(comp.get("id") or "") != game_id:
        raise ValueError("ESPN zwrócił inny mecz")
    competitors = comp.get("competitors") or []
    if not isinstance(competitors, list) or len(competitors) != 2:
        raise ValueError("Brak potwierdzonych drużyn")
    by_side = {c.get("homeAway"): c for c in competitors if isinstance(c, dict)}
    if set(by_side) != {"home", "away"} or _code(by_side["away"]) != away or _code(by_side["home"]) != home:
        raise ValueError("Niezgodne drużyny meczu")
    quarters = []
    a_lines = by_side["away"].get("linescores") or []
    h_lines = by_side["home"].get("linescores") or []
    if isinstance(a_lines, list) and isinstance(h_lines, list):
        for i in range(min(len(a_lines), len(h_lines), 8)):
            a = _integer((a_lines[i] or {}).get("value") if isinstance(a_lines[i], dict) else None, 90)
            h = _integer((h_lines[i] or {}).get("value") if isinstance(h_lines[i], dict) else None, 90)
            if a is not None and h is not None:
                quarters.append({"period":"Q"+str(i+1) if i<4 else "OT"+str(i-3),
                                 "away":a,"home":h})
    boxscore = payload.get("boxscore") or {}
    team_blocks = {}
    for block in boxscore.get("teams") or []:
        if not isinstance(block, dict):
            continue
        code = _code(block)
        if code in (away, home):
            team_blocks[code] = block
    metrics = [
        ("FG%", ("fieldGoalPct", "fieldGoalPercentage", "FG%"), True),
        ("3PT%", ("threePointFieldGoalPct", "threePointFieldGoalPercentage", "3P%"), True),
        ("REB", ("totalRebounds", "rebounds", "REB"), False),
        ("AST", ("assists", "AST"), False),
        ("TOV", ("totalTurnovers", "turnovers", "TO"), False),
    ]
    team_stats = []
    if away in team_blocks and home in team_blocks:
        for label, names, percent in metrics:
            a = _stat_value(team_blocks[away], names, percent=percent)
            h = _stat_value(team_blocks[home], names, percent=percent)
            if a is not None and h is not None:
                team_stats.append({"label":label, "away":a, "home":h})
    # Reuse the established parser; it rejects DNP and incomplete PTS/REB/AST.
    from espn_player_data import parse_summary
    rows = parse_summary(payload, {"game_id":game_id, "away":away, "home":home, "start_utc":comp.get("date") or ""})
    leaders = {}
    for side, code in (("away", away), ("home", home)):
        athletes = [row for row in rows if row.get("TEAM_ABBREVIATION") == code
                    and all(_integer(row.get(stat), 150) is not None for stat in ("PTS", "REB", "AST"))]
        athletes.sort(key=lambda row: (-int(row["PTS"]), -int(row["REB"]), str(row.get("PLAYER_NAME") or "")))
        leaders[side] = [{"name":str(p["PLAYER_NAME"])[:75],
                          "pts":int(p["PTS"]), "reb":int(p["REB"]), "ast":int(p["AST"])}
                         for p in athletes[:3]]
    return {"id":game_id, "away":away, "home":home,
            "quarters":quarters, "team_stats":team_stats, "leaders":leaders,
            "source":"ESPN"}


def load_game_details(game_id, away, home, state):
    """Fetch a single, already-verified scoreboard event after explicit click."""
    if not re.fullmatch(r"\d{6,15}", str(game_id)) or state not in ("live", "final"):
        raise ValueError("Nieobsługiwany mecz")
    if away not in TEAM_FULL or home not in TEAM_FULL or away == home:
        raise ValueError("Nieprawidłowe drużyny")
    from espn_player_data import ESPN_SUMMARY
    from sources import memoized_json
    payload, meta = memoized_json("bb-free-schedule-summary-v1-"+game_id,
                                  ESPN_SUMMARY,params={"event":game_id},
                                  ttl_seconds=45 if state=="live" else 3600,
                                  request_timeout=7)
    result = parse_game_details(payload, game_id, away, home)
    result["stale"] = bool(meta.get("stale"))
    return result
