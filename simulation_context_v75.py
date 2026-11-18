"""Experimental V7.5: verified venue split and schedule-rest research signals.

Only games completed BEFORE the predicted tipoff are eligible. This model is
separate from V7.2/V7.4 to allow prospective comparison. Adjustments are
deliberately small, are NOT trained/calibrated, and cannot imply that missing
injury or projected-minute information has been accounted for.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from match_context import matchup_schedule_context
from simulation_context_v2 import simulation_inputs
from simulation_data_audit import team_snapshot, verified_history


def _venue_delta(attack: dict, opposing_defense: dict) -> float:
    """Shrunk attack and allowed-point venue contrast, zero if under-sampled."""
    n_attack = int(attack.get("venue_sample") or 0)
    n_defense = int(opposing_defense.get("venue_sample") or 0)
    if min(n_attack, n_defense) < 4:
        return 0.0
    needed = ((attack.get("venue_scored"), attack.get("pts20")),
              (opposing_defense.get("venue_allowed"), opposing_defense.get("allowed20")))
    if any(x is None or y is None for x, y in needed):
        return 0.0
    attack_difference = float(needed[0][0]) - float(needed[0][1])
    defense_difference = float(needed[1][0]) - float(needed[1][1])
    # Weak prior and capped response guard against noisy early-season splits.
    reliability = min(n_attack, n_defense) / (min(n_attack, n_defense) + 12.0)
    return float(np.clip((attack_difference + defense_difference) * .5 * reliability,
                         -3.0, 3.0))


def _rest_deltas(rest: dict) -> tuple[float, float]:
    """Conservative, uncalibrated fatigue hypothesis; neither team gets a
    rest bonus when the other team has the same short turnaround.
    """
    home, away = rest.get("home") or {}, rest.get("away") or {}
    if not home.get("available") or not away.get("available"):
        return 0.0, 0.0
    if home.get("back_to_back") and not away.get("back_to_back"):
        return -0.8, 0.4
    if away.get("back_to_back") and not home.get("back_to_back"):
        return 0.4, -0.8
    return 0.0, 0.0


def simulation_inputs_v75(completed: pd.DataFrame, game: dict,
                          advanced: pd.DataFrame | None = None) -> dict:
    """V7.4 evidence plus guarded venue/rest adjustments with provenance."""
    prior = simulation_inputs(completed, game, advanced)
    if prior["means"] is None:
        return prior
    earlier = verified_history(completed, game.get("start_utc"))
    home, away = str(game["home"]), str(game["away"])
    h = team_snapshot(earlier, home, opponent=away, venue="home")
    a = team_snapshot(earlier, away, opponent=home, venue="away")
    schedule = matchup_schedule_context(earlier, game)

    venue_home = _venue_delta(h, a)
    venue_away = _venue_delta(a, h)
    rest_home, rest_away = _rest_deltas(schedule)
    original = prior["means"]
    # The simulator validates the final result; never conceal invalid source
    # ratings by forcing a nonsensical mean into its accepted input range.
    updated = {
        **original,
        "home": float(original["home"] + venue_home + rest_home),
        "away": float(original["away"] + venue_away + rest_away),
        "source": str(original.get("source") or "ESPN") + " • V7.5 (dom/wyjazd, odpoczynek)",
        "warning": (str(original.get("warning") or "") + " "
                    "V7.5: eksperymentalna korekta dom/wyjazd i back-to-back; "
                    "bez potwierdzonej kalibracji ani wpływu absencji zawodników.").strip(),
    }
    factors = {
        "venue_home_pts": round(venue_home, 2),
        "venue_away_pts": round(venue_away, 2),
        "rest_home_pts": rest_home,
        "rest_away_pts": rest_away,
        "home_venue_games": h.get("venue_sample", 0),
        "away_venue_games": a.get("venue_sample", 0),
        "injuries_confirmed": False,
        "minutes_confirmed": False,
        "calibrated": False,
    }
    return {
        **prior, "means": updated,
        "context": {**prior["context"], "v75_factors": factors},
    }
