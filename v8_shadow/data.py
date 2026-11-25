"""Independent V8 research ingest: verified ESPN finished team box scores.

No guesses for missing FGA, FTA, OREB or TOV. Only genuinely observed
team-level stats can produce possession estimates. ESPN summary uses the
same ESPN game ID as the existing pregame Tracker; official NBA CDN IDs
are NOT confused with ESPN event IDs.

This data provider is for isolated model research while commercial use terms
and licensing are reviewed. Do not expose source data in paid UI.
"""
from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import pandas as pd
import requests

SUMMARY_URL = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary"
ALIASES = {"GS": "GSW", "NY": "NYK", "SA": "SAS", "NO": "NOP",
           "UT": "UTA", "PHO": "PHX", "WSH": "WAS", "BRK": "BKN"}
PAIR = re.compile(r"^\s*(\d{1,3})\s*-\s*(\d{1,3})\s*$")


def _team_code(code):
    name = str(code or "").upper().strip()
    return ALIASES.get(name, name)


def _integer(value):
    if isinstance(value, bool):
        raise ValueError("not a verified numeric stat")
    try:
        val = float(value)
    except (ValueError, TypeError, OverflowError):
        raise ValueError("missing team box stat")
    if not val.is_integer():
        raise ValueError("fractional boxscore statistic")
    return int(val)


def _stat_map(statistics):
    if not isinstance(statistics, list):
        raise ValueError("missing ESPN team statistics")
    results = {}
    for row in statistics:
        if isinstance(row, dict):
            label = str(row.get("name") or "").strip()
            if label:
                results[label] = row.get("displayValue", row.get("value"))
    return results


def _count(stats, *names):
    for key in names:
        if key in stats:
            return _integer(stats[key])
    raise ValueError("required count absent: " + names[0])


def _attempts(stats, made_key, attempt_key, combo_key):
    if attempt_key in stats:
        made = _integer(stats.get(made_key))
        attempted = _integer(stats[attempt_key])
    else:
        text = str(stats.get(combo_key) or "")
        m = PAIR.fullmatch(text)
        if not m:
            raise ValueError("required verified made-attempted pair missing")
        made, attempted = int(m[1]), int(m[2])
    if not (0 <= made <= attempted):
        raise ValueError("made attempts exceed attempted attempts")
    return attempted


def _team_box_stats(statistics):
    stats = _stat_map(statistics)
    fga = _attempts(stats, "fieldGoalsMade", "fieldGoalsAttempted",
                    "fieldGoalsMade-fieldGoalsAttempted")
    fta = _attempts(stats, "freeThrowsMade", "freeThrowsAttempted",
                    "freeThrowsMade-freeThrowsAttempted")
    oreb = _count(stats, "offensiveRebounds", "reboundsOffensive")
    tov = _count(stats, "totalTurnovers", "turnovers")
    if not (55 <= fga <= 135 and 0 <= fta <= 95 and 0 <= oreb <= 40
            and 0 <= tov <= 45):
        raise ValueError("invalid observed boxscore bounds")
    possessions = fga - oreb + tov + 0.44 * fta
    if not 65 <= possessions <= 140:
        raise ValueError("invalid calculated possessions")
    return {"fga": fga, "fta": fta, "oreb": oreb, "tov": tov,
            "poss": round(possessions, 3)}


def parse_espn_summary(payload, expected):
    """Single ESPN completed game with both team boxscore stat sets.

    A malformed or unconfirmed game returns a failure, not a fabricated
    no-data feature. Excludes overtime for now, since 48-minute offensive
    and pace signals must not mix 53/58-minute games without normalization.
    """
    if not isinstance(payload, dict):
        raise ValueError("ESPN summary not a JSON object")
    eid = str(expected.get("game_id") or "")
    if not (eid.isdecimal() and len(eid) <= 20):
        raise ValueError("invalid ESPN event id")
    start = pd.to_datetime(expected.get("start_utc"), utc=True, errors="coerce")
    if pd.isna(start):
        raise ValueError("no observed scheduled start")
    if _integer(expected.get("status_code")) != 3:
        raise ValueError("only ESPN final games are eligible")
    header = payload.get("header") or {}
    match = (header.get("competitions") or [None])[0]
    if not isinstance(match, dict):
        raise ValueError("unverified ESPN event header")
    header_id = str(header.get("id") or match.get("id") or "")
    if header_id != eid:
        raise ValueError("ESPN summary ID does not match requested event")
    state = ((match.get("status") or {}).get("type") or {})
    if state and not (state.get("completed") is True or
                      str(state.get("name") or "").startswith("STATUS_FINAL")):
        raise ValueError("ESPN summary is not completed")
    opponents = {}
    for side in match.get("competitors") or []:
        label = side.get("homeAway")
        if label in ("away", "home"):
            opponents[label] = side
    if set(opponents) != {"home", "away"}:
        raise ValueError("ESPN home/away evidence incomplete")
    observed = {}
    for side, comp in opponents.items():
        team = _team_code((comp.get("team") or {}).get("abbreviation"))
        if team != expected[side]:
            raise ValueError("ESPN team id mismatch")
        score = _integer(comp.get("score"))
        if score != _integer(expected[f"{side}_score"]):
            raise ValueError("final score mismatch")
        scores = comp.get("linescores")
        if isinstance(scores, list) and len(scores) > 4:
            raise ValueError("overtime not normalized, excluded from V8 training")
        observed[side] = score
    items = (payload.get("boxscore") or {}).get("teams")
    if not isinstance(items, list):
        raise ValueError("no ESPN official team boxscore")
    sides = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        code = _team_code((item.get("team") or {}).get("abbreviation"))
        if code not in (expected["home"], expected["away"]):
            continue
        if code in sides:
            raise ValueError("duplicate boxscore team entry")
        sides[code] = _team_box_stats(item.get("statistics"))
    if set(sides) != {expected["home"], expected["away"]}:
        raise ValueError("both team stat lines must be verified")
    a = sides[expected["away"]]
    h = sides[expected["home"]]
    if abs(a["poss"] - h["poss"]) > 12:
        raise ValueError("team possession estimates disagree")
    return {
        "game_id": eid, "season": str(expected["season"]),
        "start_utc": start.isoformat(),
        "home": str(expected["home"]), "away": str(expected["away"]),
        "home_score": observed["home"], "away_score": observed["away"],
        "home_fga": h["fga"], "home_fta": h["fta"],
        "home_oreb": h["oreb"], "home_tov": h["tov"],
        "away_fga": a["fga"], "away_fta": a["fta"],
        "away_oreb": a["oreb"], "away_tov": a["tov"],
        "home_poss": h["poss"], "away_poss": a["poss"],
        "source": "ESPN game summary — observed team boxscore, estimated possessions",
    }


def fetch_espn_summary(game, get=None):
    if get is None:
        get = requests.get
    game_id = str(game.get("game_id") or "")
    if not game_id.isdecimal():
        raise ValueError("invalid game id")
    response = get(SUMMARY_URL, params={"event": game_id},
                   headers={"User-Agent": "Mozilla/5.0 (Hoopzaro V8 research)"},
                   timeout=13)
    response.raise_for_status()
    return parse_espn_summary(response.json(), game)


def categorize_rejection(exc):
    """Safe provider diagnosis, without persisting arbitrary exception texts."""
    if isinstance(exc, requests.RequestException) or isinstance(
        exc, (OSError, ConnectionError, TimeoutError)):
        return "transport_unavailable"
    if isinstance(exc, ValueError):
        msg = str(exc).lower()
        if "overtime" in msg:
            return "overtime_unmodeled"
        if ("required" in msg or "team boxscore" in msg or
            "team statistics" in msg or "missing" in msg):
            return "required_box_stats_missing"
        if "score mismatch" in msg:
            return "score_mismatch"
        if ("team id mismatch" in msg or "both team" in msg or
            "duplicate boxscore team" in msg):
            return "team_evidence_mismatch"
        if "possession" in msg:
            return "invalid_possession_estimate"
        if "final" in msg or "not completed" in msg:
            return "unverified_final"
        return "invalid_provider_schema"
    return "provider_failure"


def collect_team_boxes(finals, existing_ids=(), limit=16, fetch=None):
    """Safely bounded incremental collector. Network errors never mutate data."""
    if fetch is None:
        fetch = fetch_espn_summary
    required = {"game_id", "season", "start_utc", "home", "away",
                "home_score", "away_score", "status_code"}
    if not isinstance(finals, pd.DataFrame) or not required.issubset(finals):
        return [], {"checked": 0, "accepted": 0, "reason": "missing verified schedule"}
    if not 1 <= limit <= 60:
        raise ValueError("bounded collector limit required")
    existing = {str(g) for g in existing_ids}
    safe = finals.copy()
    safe["start_utc"] = pd.to_datetime(safe["start_utc"], utc=True, errors="coerce")
    safe["status_code"] = pd.to_numeric(safe["status_code"], errors="coerce")
    safe = safe[(safe["status_code"] == 3) & safe["start_utc"].notna() &
                (safe["start_utc"] < pd.Timestamp.now(tz="UTC"))]
    safe = safe[~safe["game_id"].astype(str).isin(existing)]
    safe = safe.sort_values("start_utc", ascending=False).drop_duplicates("game_id")
    selected = safe.head(limit).to_dict("records")
    successful = []
    errors = []
    # Small, fixed concurrency: no unbounded ESPN scraping. Rights audit
    # needed before commercial use or mass historical data collection.
    with ThreadPoolExecutor(max_workers=2) as pool:
        jobs = [pool.submit(fetch, game) for game in selected]
        for game, job in zip(selected, jobs):
            try:
                box = job.result(timeout=25)
                successful.append(box)
            except Exception as exc:
                errors.append({"game_id": str(game["game_id"]),
                               "reason_code": categorize_rejection(exc)})
    reason_counts = {}
    for failure in errors:
        key = failure["reason_code"]
        reason_counts[key] = reason_counts.get(key, 0) + 1
    return successful, {
        "rejection_categories": reason_counts,
        "checked": len(selected), "accepted": len(successful),
        "rejected": len(errors),
        "rejections": errors[:20],
        "source": "ESPN NBA team boxscore, research-only",
    }
