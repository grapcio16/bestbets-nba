"""Research-only roster and minutes projection, version 1.

No public UI, storage, injury feed or V7/V8 side effects. Inputs must be
point-in-time, stable player IDs and verified roster membership; absent
injury records are never treated as confirmed available.
"""
from __future__ import annotations

from collections import defaultdict
from math import isfinite
import numpy as np
import pandas as pd

VERSION = "player_intelligence_shadow_v01"
MARKETS = ("PTS", "REB", "AST", "FG3M")
MIN_HISTORY = 3
MAX_HISTORY = 15
MAX_PLAYER_MINUTES = 48.0
TEAM_MINUTES = 240.0
MAX_ROSTER_AGE = pd.Timedelta(hours=24)
MAX_STATUS_AGE = pd.Timedelta(hours=6)
LEAD = pd.Timedelta(minutes=15)
STATUSES = {"available", "out", "questionable", "doubtful", "probable", "unknown"}


def _time(value):
    t = pd.to_datetime(value, utc=True, errors="coerce")
    if pd.isna(t):
        raise ValueError("missing/invalid UTC timestamp")
    return t


def _number(value, upper):
    if isinstance(value, (bool, np.bool_)):
        raise ValueError("boolean is not a numerical observation")
    x = float(value)
    if not isfinite(x) or not 0 <= x <= upper:
        raise ValueError("invalid observed statistic")
    return x


def _id(value):
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise ValueError("stable string identifier required")
    return value


def _allocate_minutes(weights, target=TEAM_MINUTES):
    """Capped proportional allocation; no imaginary reserve player."""
    w = np.asarray(weights, dtype=float)
    if w.ndim != 1 or not len(w) or not np.isfinite(w).all() or np.any(w < 0):
        raise ValueError("invalid minutes weights")
    if np.count_nonzero(w > 0) * MAX_PLAYER_MINUTES < target:
        raise ValueError("insufficient eligible rotation capacity")
    if np.count_nonzero(w > 0) * MAX_PLAYER_MINUTES == target:
        return np.where(w > 0, MAX_PLAYER_MINUTES, 0.0)
    low, high = 0., MAX_PLAYER_MINUTES / np.min(w[w > 0])
    for _ in range(80):
        mid = (low + high) / 2
        if np.minimum(w * mid, MAX_PLAYER_MINUTES).sum() < target:
            low = mid
        else:
            high = mid
    allocation = np.minimum(w * ((low + high) / 2), MAX_PLAYER_MINUTES)
    if abs(float(allocation.sum()) - target) > 1e-7:
        raise ValueError("minutes conservation failed")
    return allocation


def _history(logs, team, roster_ids, asof, game_id):
    by_player = defaultdict(list)
    seen = set()
    for row in logs:
        if row.get("team") != team or row.get("player_id") not in roster_ids:
            continue
        if row.get("game_id") == game_id:
            continue
        tip = _time(row["start_utc"])
        observed = _time(row["observed_at"])
        if tip >= asof or observed > asof:
            continue
        if row.get("final_verified") is not True or observed < tip + pd.Timedelta(hours=4):
            continue
        key = (_id(row["player_id"]), _id(row["game_id"]))
        if key in seen:
            raise ValueError("duplicate player-game evidence")
        seen.add(key)
        # Regulation only; reject unknown duration rather than mix OT minutes.
        if row.get("regulation_only") is not True:
            continue
        mins = _number(row["minutes"], MAX_PLAYER_MINUTES)
        stats = np.array([_number(row[m], 150) for m in MARKETS])
        if mins == 0 and np.any(stats != 0):
            raise ValueError("nonzero stats without minutes")
        if stats[3] * 3 > stats[0]:
            raise ValueError("three-point makes exceed total points")
        by_player[key[0]].append((tip, mins, stats))
    return by_player


def _profile(rows):
    # A zero-minute DNP is not evidence of a player's conditional active rate.
    active = sorted((r for r in rows if r[1] > 0), key=lambda r: r[0])[-MAX_HISTORY:]
    if len(active) < MIN_HISTORY:
        return None
    mins = np.asarray([r[1] for r in active])
    stats = np.stack([r[2] for r in active])
    weights = np.exp(-np.arange(len(active)-1, -1, -1)/6.)
    weighted_minutes = float(np.average(mins, weights=weights))
    exposure = float(np.dot(weights, mins))
    if exposure < 20:
        return None
    rates = (weights @ stats) / exposure
    return weighted_minutes, rates, len(active)


def project_rotation(*, game, team, asof, roster, logs, availability,
                     assume_active_ids=(), assume_out_ids=()):
    """Conditional regulation projection, not an injury probability model.

    roster: {team, observed_at, complete_verified, players:[{player_id}]}.
    logs: per-player verified final game records, with observation time.
    availability: explicit team + ID + status + observation timestamp.
    Assumptions must resolve every unconfirmed player; no invented probability.
    """
    cutoff = _time(asof)
    tip = _time(game["start_utc"])
    gid = _id(game["game_id"])
    if cutoff + LEAD >= tip or game.get("home") == game.get("away") or team not in (game.get("home"), game.get("away")):
        raise ValueError("invalid pregame fixture or cutoff")
    if roster.get("team") != team or roster.get("complete_verified") is not True:
        return {"status": "insufficient_verified_roster", "model_id": VERSION}
    roster_time = _time(roster["observed_at"])
    if not cutoff-MAX_ROSTER_AGE <= roster_time <= cutoff:
        return {"status": "stale_or_future_roster", "model_id": VERSION}
    ids = [_id(p["player_id"]) for p in roster["players"]]
    if len(ids) != len(set(ids)) or not 5 <= len(ids) <= 25:
        raise ValueError("invalid roster size or duplicate stable ID")
    ids = sorted(ids)
    active_assumption, out_assumption = set(assume_active_ids), set(assume_out_ids)
    if active_assumption & out_assumption or not (active_assumption | out_assumption) <= set(ids):
        raise ValueError("conflicting or unknown scenario assumption")
    latest = {}
    for row in availability:
        if row.get("team") != team or row.get("player_id") not in ids:
            continue
        stamp = _time(row["observed_at"])
        if not cutoff-MAX_STATUS_AGE <= stamp <= cutoff or row.get("verified") is not True:
            continue
        pid = row["player_id"]
        status = row.get("status")
        if status not in STATUSES:
            raise ValueError("unsupported availability status")
        old = latest.get(pid)
        if old and stamp == old[0] and old[1] != status:
            raise ValueError("contradictory same-time availability")
        if old is None or stamp > old[0]:
            latest[pid] = (stamp, status)
    resolved, unresolved = {}, []
    for pid in ids:
        status = latest.get(pid, (None, "unknown"))[1]
        if status == "out":
            if pid in active_assumption:
                raise ValueError("scenario contradicts verified OUT")
            resolved[pid] = ("out", False)
        elif status == "available":
            if pid in out_assumption:
                raise ValueError("scenario contradicts verified available")
            resolved[pid] = ("available", True)
        elif pid in active_assumption:
            resolved[pid] = ("assumed_active", True)
        elif pid in out_assumption:
            resolved[pid] = ("assumed_out", False)
        else:
            unresolved.append(pid)
    if unresolved:
        return {"status": "unresolved_availability", "model_id": VERSION,
                "unresolved_player_ids": unresolved}
    evidence = _history(logs, team, set(ids), cutoff, gid)
    profiles, missing = {}, []
    for pid in ids:
        if resolved[pid][1]:
            profile = _profile(evidence[pid])
            if profile is None:
                missing.append(pid)
            else:
                profiles[pid] = profile
    if missing:
        return {"status": "insufficient_player_evidence", "model_id": VERSION,
                "missing_player_ids": missing}
    weights = [profiles[pid][0] if pid in profiles else 0. for pid in ids]
    try:
        allocation = _allocate_minutes(weights)
    except ValueError:
        return {"status": "insufficient_rotation_capacity", "model_id": VERSION}
    players = []
    for pid, minutes in zip(ids, allocation):
        status, is_active = resolved[pid]
        result = {"player_id": pid, "availability": status,
                  "minutes": float(minutes), "sample_games": 0}
        values = np.zeros(4)
        if is_active:
            _, rates, sample = profiles[pid]
            values = rates * minutes
            result["sample_games"] = sample
        result.update({m: float(value) for m, value in zip(MARKETS, values)})
        result["PRA"] = result["PTS"] + result["REB"] + result["AST"]
        players.append(result)
    return {"status": "shadow_conditional", "model_id": VERSION,
            "game_id": gid, "team": team, "asof": cutoff.isoformat(),
            "team_minutes": float(allocation.sum()), "players": players,
            "assumptions_used": any(p["availability"].startswith("assumed_") for p in players),
            "limitations": "Conditional active rates; no calibrated injury probabilities, team impact, OT or matchup adjustment."}
