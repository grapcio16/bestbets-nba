"""Evidence-only V8 readiness audit.

This is NOT a synthetic training substitute. Count the completed, observed
boxscores which can form chronological model examples. In particular the
number of stored boxscores is NOT the number of trainable observations.
"""
from __future__ import annotations

from collections import Counter

import pandas as pd

from v8_shadow.engine import (
    MIN_HOLDOUT, MIN_TEAM_GAMES, MIN_TRAIN, _examples, _prepare_history, _time,
)


def audit_evidence(games, asof):
    clock = _time(asof)
    history = [g for g in _prepare_history(games)
               if _time(g["start_utc"]) < clock]
    team_count = Counter()
    for g in history:
        team_count[g["home"]] += 1
        team_count[g["away"]] += 1
    xs, _ = _examples(history, clock)
    n = int(len(xs))
    validation_n = max(MIN_HOLDOUT, int(n * 0.24))
    train_n = max(0, n - validation_n)
    ready = n >= MIN_TRAIN + MIN_HOLDOUT and train_n >= MIN_TRAIN
    return {
        "model": "V8 Shadow",
        "asof_utc": clock.isoformat(),
        "observed_final_games": len(history),
        "trainable_chronological_examples": n,
        "minimum_examples": MIN_TRAIN + MIN_HOLDOUT,
        "effective_training_examples": train_n,
        "reserved_validation_examples": validation_n if ready else 0,
        "ready_for_eligible_matchups": bool(ready),
        "readiness_reason": ("training_evidence_sufficient" if ready
                             else "chronological_history_incomplete"),
        "teams_observed": len(team_count),
        "teams_with_minimum_history": sum(
            count >= MIN_TEAM_GAMES for count in team_count.values()),
        "teams_below_minimum": sorted(
            team for team, count in team_count.items()
            if count < MIN_TEAM_GAMES),
        "oldest_observation_utc": (
            _time(history[0]["start_utc"]).isoformat() if history else None),
        "newest_observation_utc": (
            _time(history[-1]["start_utc"]).isoformat() if history else None),
        "no_forecast_generated": True,
    }
