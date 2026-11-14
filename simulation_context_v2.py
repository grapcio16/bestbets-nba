"""Richer, no-lookahead evidence for the HOOPZARO experimental simulator.

Only verified *completed* games before the selected tip-off are allowed.
Actual NBA Advanced OFF/DEF/PACE is included when a fresh cache is available.
Venue, rest and opponent samples are reported, but do not create unvalidated
point bonuses. Historical scoring variability replaces fixed team noise when
the sample is sufficiently large; estimates are shrunk to a conservative prior.
"""
from __future__ import annotations

from math import sqrt

import numpy as np
import pandas as pd

from match_context import matchup_schedule_context
from simulation_data_audit import team_snapshot, verified_history
from simulation_engine import advanced_ratings, completed_team_scores, matchup_means


def score_volatility(verified: pd.DataFrame, team: str, minimum: int = 8) -> dict:
    """Observed recent scoring SD with prior shrinkage, never fake precision."""
    rows = verified[(verified["home"] == team) | (verified["away"] == team)].tail(20)
    sample = len(rows)
    if sample < minimum:
        return {"sample": sample, "sd": None}
    scores = np.where(rows["home"].eq(team), rows["home_score"], rows["away_score"])
    observed = float(np.std(scores.astype(float), ddof=1))
    if not np.isfinite(observed):
        return {"sample": sample, "sd": None}
    reliability = sample / (sample + 15.0)
    # Prior variance reflects an experimental baseline, not a calibrated NBA
    # statistic. Cap extrapolation from outlier-heavy short histories.
    variance = reliability * float(np.clip(observed, 7.0, 20.0)) ** 2
    variance += (1.0 - reliability) * (12.5 ** 2)
    return {"sample": sample, "sd": round(sqrt(variance), 3)}


def simulation_inputs(completed: pd.DataFrame, game: dict,
                      advanced: pd.DataFrame | None = None) -> dict:
    """Prepare evidence-rich scoring inputs, excluding this or future games."""
    earlier = verified_history(completed, game.get("start_utc"))
    home, away = str(game["home"]), str(game["away"])
    ratings = advanced_ratings(advanced)
    means = matchup_means(home, away, ratings, completed_team_scores(earlier))
    if means is None:
        return {"means": None, "score_noise": None, "context": {
            "source": "ESPN", "completed_games": len(earlier),
            "warning": "Za mało zakończonych spotkań przed rozpoczęciem meczu."}}

    home_stats = team_snapshot(earlier, home, opponent=away, venue="home")
    away_stats = team_snapshot(earlier, away, opponent=home, venue="away")
    rest = matchup_schedule_context(earlier, game)
    home_sd = score_volatility(earlier, home)
    away_sd = score_volatility(earlier, away)
    # The 6-point shared pace term stays an explicit baseline assumption.
    # Independent noise is adapted only when enough historical games exist.
    shared = 6.0
    noise = {
        "shared_sd": shared,
        "home_sd": round(sqrt(max(16.0, home_sd["sd"] ** 2 - shared ** 2)), 3)
                   if home_sd["sd"] is not None else 11.0,
        "away_sd": round(sqrt(max(16.0, away_sd["sd"] ** 2 - shared ** 2)), 3)
                   if away_sd["sd"] is not None else 11.0,
    }
    context = {
        "source": "NBA Advanced + ESPN" if home in ratings and away in ratings else "ESPN",
        "completed_games": len(earlier),
        "home_sample": home_stats["sample"],
        "away_sample": away_stats["sample"],
        "venue_samples": [away_stats.get("venue_sample", 0),
                          home_stats.get("venue_sample", 0)],
        "rest_days": [rest["away"].get("rest_days"),
                      rest["home"].get("rest_days")],
        "score_sd_samples": [away_sd["sample"], home_sd["sample"]],
        "advanced_available": home in ratings and away in ratings,
        "warnings": (home_stats.get("warnings", []) + away_stats.get("warnings", []))[:6],
    }
    return {"means": means, "score_noise": noise, "context": context}
