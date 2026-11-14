"""Centrum-only, single-game facts. No Props models, billing or remote image URLs."""
from __future__ import annotations

import copy
import hashlib
import json
import math
import os
import re
import unicodedata

import pandas as pd
from teams import TEAM_FULL

MARKETS = {"points": "PTS", "rebounds": "REB", "assists": "AST"}
POSITIONS = frozenset({"PG", "SG", "SF", "PF", "C", "G", "F", "G-F", "F-G", "F-C", "C-F"})
ALIASES = {"GS": "GSW", "NY": "NYK", "SA": "SAS", "NO": "NOP",
           "PHO": "PHX", "WSH": "WAS", "BRK": "BKN", "UTAH": "UTA"}
LIMITS = {"PTS": 100, "REB": 55, "AST": 35, "3PM": 35}
SCHEMA = 1


def integer(value, maximum):
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
        return int(number) if math.isfinite(number) and number.is_integer() and 0 <= number <= maximum else None
    except (TypeError, ValueError, OverflowError):
        return None


def identifier(value, length=20):
    return isinstance(value, str) and re.fullmatch(r"[0-9]{1," + str(length) + r"}", value) is not None


def team_code(item):
    code = str((item.get("team") or {}).get("abbreviation") or "").upper()
    return ALIASES.get(code, code)


def athlete_position(athlete):
    """Only display positions explicitly reported by the player data source."""
    pos = athlete.get("position") if isinstance(athlete, dict) else None
    if not isinstance(pos, dict):
        return ""
    value = str(pos.get("abbreviation") or "").strip().upper()
    return value if value in POSITIONS else ""


def completed(event, competition):
    statuses = [(obj.get("status") or {}).get("type") or {} for obj in (event, competition)]
    return (any(s.get("completed") is True for s in statuses)
            and not any(s.get("completed") is False or s.get("state") in ("pre", "in") for s in statuses))


def detail_key(row):
    facts = [row.get(k) for k in ("game_id", "athlete_id", "market", "value", "date", "team", "opponent")]
    return hashlib.sha256(json.dumps(facts, separators=(",", ":")).encode()).hexdigest()


def photo_policy():
    # Separate from Player Props. Absence of this explicit operator setting
    # means NO headshot requests, even if a source supplies an image URL.
    return os.environ.get("BESTBETS_CENTRE_HEADSHOTS_LICENSED", "").lower() == "true"


def extract_free_leaders(payload, now=None, covered_days=None):
    """Latest NBA/ET day first; never backfill a missing category from older days.

    Require each final game's BOTH teams to report that category, otherwise its
    maximum cannot be established. Equal maxima use a stable ID tie-breaker.
    """
    now = pd.Timestamp(now) if now is not None else pd.Timestamp.now(tz="UTC")
    now = now.tz_localize("Europe/Warsaw") if now.tzinfo is None else now.tz_convert("UTC")
    games = {}
    for event in payload.get("events", []) if isinstance(payload, dict) else []:
        if not isinstance(event, dict):
            continue
        comps = event.get("competitions") or []
        if not comps or not isinstance(comps[0], dict) or not completed(event, comps[0]):
            continue
        when = pd.to_datetime(event.get("date"), utc=True, errors="coerce")
        if pd.isna(when) or when > now:
            continue
        # Select the date even when that game's IDs/leader data are incomplete.
        games[str(event.get("id") or event.get("uid") or len(games))] = (event, comps[0], when)
    latest = max((t.tz_convert("America/New_York").date().isoformat() for _, _, t in games.values()), default="")
    result = {"free_schema": SCHEMA, "free_leaders": [], "free_leader_day": latest,
              "free_missing_categories": list(MARKETS.values()), "free_warning": ""}
    if not latest:
        return result
    if covered_days is not None:
        required = pd.date_range(latest, now.tz_convert("America/New_York").date()).strftime("%Y%m%d")
        if not set(required).issubset(set(covered_days)):
            result["free_warning"] = "Niepełne dane ESPN — nie można potwierdzić najnowszego dnia liderów."
            return result
    candidates = {market: [] for market in MARKETS.values()}
    complete = {market: True for market in candidates}
    for event, comp, when in games.values():
        if when.tz_convert("America/New_York").date().isoformat() != latest:
            continue
        competitors = comp.get("competitors") or []
        valid = (identifier(str(event.get("id") or ""), 10) and len(competitors) == 2
                 and all(isinstance(c, dict) and team_code(c) in TEAM_FULL for c in competitors)
                 and {c.get("homeAway") for c in competitors} == {"home", "away"}
                 and len({team_code(c) for c in competitors}) == 2)
        if not valid:
            complete = dict.fromkeys(complete, False)
            continue
        for i, competitor in enumerate(competitors):
            reported = {market: [] for market in candidates}
            for group in competitor.get("leaders") or []:
                market = MARKETS.get(group.get("name")) if isinstance(group, dict) else None
                if not market:
                    continue
                for leader in group.get("leaders") or []:
                    athlete = leader.get("athlete") or {}
                    name = str(athlete.get("displayName") or athlete.get("fullName") or "").strip()
                    ident = str(athlete.get("id") or "")
                    value = integer(leader.get("value"), LIMITS[market])
                    if not identifier(ident) or not name or len(name) > 70 or value is None:
                        continue
                    row = {"name": name, "athlete_id": ident, "game_id": str(event["id"]),
                           "team": team_code(competitor), "opponent": team_code(competitors[1-i]),
                           "home_away": competitor["homeAway"], "market": market, "value": value,
                           "date": latest, "local_date": when.tz_convert("Europe/Warsaw").date().isoformat(),
                           "event_date": when.isoformat()}
                    position = athlete_position(athlete)
                    if position:
                        row["position"] = position
                    row["detail_key"] = detail_key(row)
                    reported[market].append(row)
            for market in candidates:
                complete[market] &= bool(reported[market])
                candidates[market].extend(reported[market])
    for market, rows in candidates.items():
        if complete[market] and rows:
            winner = max(rows, key=lambda r: (r["value"], r["event_date"], r["game_id"], r["athlete_id"]))
            winner["tie_count"] = len({r["athlete_id"] for r in rows if r["value"] == winner["value"]})
            result["free_leaders"].append(winner)
            result["free_missing_categories"].remove(market)
    return result


def select_leader(snapshot, key):
    """Untrusted client supplies an opaque key, never athlete IDs or URLs."""
    if not isinstance(key, str) or not re.fullmatch(r"[0-9a-f]{64}", key):
        return None
    return next((row for row in snapshot.get("free_leaders", [])
                 if row.get("detail_key") == key and detail_key(row) == key), None)


def get_free_leader_boxscore(leader):
    """Verify raw ESPN header before reusing the established boxscore parser."""
    from sources import memoized_json
    from espn_player_data import ESPN_SUMMARY, parse_summary
    game_id, player_id = str(leader.get("game_id") or ""), str(leader.get("athlete_id") or "")
    team, opponent = leader.get("team"), leader.get("opponent")
    if (not identifier(game_id, 10) or not identifier(player_id) or team not in TEAM_FULL
            or opponent not in TEAM_FULL or team == opponent or leader.get("home_away") not in ("home", "away")
            or leader.get("market") not in LIMITS or detail_key(leader) != leader.get("detail_key")):
        raise ValueError("Brak zweryfikowanego identyfikatora meczu lub zawodnika.")
    payload, meta = memoized_json("bb-free-final-summary-v1-" + game_id, ESPN_SUMMARY,
                                 params={"event": game_id}, ttl_seconds=120, request_timeout=6)
    header = payload.get("header") or {}
    comps = header.get("competitions") or []
    comp = comps[0] if comps else {}
    when = pd.to_datetime(comp.get("date"), utc=True, errors="coerce")
    expected = {team: leader["home_away"], opponent: "away" if leader["home_away"] == "home" else "home"}
    actual = {team_code(c): c.get("homeAway") for c in comp.get("competitors") or []}
    if (str(header.get("id")) != game_id or str(comp.get("id")) != game_id or not completed({}, comp)
            or pd.isna(when) or when > pd.Timestamp.now(tz="UTC")
            or when.tz_convert("America/New_York").date().isoformat() != leader["date"]
            or actual != expected):
        raise ValueError("Niepotwierdzony mecz ESPN.")
    game = {"game_id": game_id, "start_utc": when.isoformat(),
            "away": next(k for k, v in expected.items() if v == "away"),
            "home": next(k for k, v in expected.items() if v == "home")}
    normalized = copy.deepcopy(payload)
    for block in (normalized.get("boxscore") or {}).get("players", []):
        block["team"]["abbreviation"] = team_code(block)
    rows = [r for r in parse_summary(normalized, game)
            if str(r.get("PLAYER_ID")) == player_id and r.get("TEAM_ABBREVIATION") == team]
    def name_key(name):
        return unicodedata.normalize("NFKC", name).casefold().strip()
    if len(rows) != 1 or name_key(rows[0]["PLAYER_NAME"]) != name_key(leader["name"]):
        raise ValueError("ESPN nie potwierdził tożsamości zawodnika.")
    result = {k: leader[k] for k in ("name", "athlete_id", "team", "opponent", "date", "market")}
    for source, target in (("PTS", "PTS"), ("REB", "REB"), ("AST", "AST"), ("FG3M", "3PM")):
        value = integer(rows[0].get(source), LIMITS[target])
        if value is None:
            raise ValueError("Niekompletne statystyki ESPN.")
        result[target] = value
    if result[leader["market"]] != leader["value"] or result["PTS"] < 3 * result["3PM"]:
        raise ValueError("Wartości ESPN leaderboard i boxscore nie są zgodne.")
    return {**result, "verified": True, "stale": bool(meta.get("stale")),
            "fetched_at": meta.get("timestamp", "")}
