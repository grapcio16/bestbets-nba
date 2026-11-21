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


def verified_team_comparison(earlier: pd.DataFrame, home: str, away: str,
                             home_snapshot: dict, away_snapshot: dict,
                             ratings: dict) -> dict:
    """Descriptive facts, not new simulated or calibrated projections.

    The input history has already been restricted to distinct verified NBA
    final results strictly BEFORE the selected tipoff. Samples are limited
    to 20 games; W/L is taken from the same last 10 verified games.
    NBA Advanced is shown only when both teams have complete actual metrics.
    """
    full_advanced = home in ratings and away in ratings

    def one(code: str, snapshot: dict, venue: str) -> dict:
        own = earlier[(earlier["home"] == code) |
                      (earlier["away"] == code)]
        def record(n):
            games = own.tail(n)
            wins = sum(
                (r["home"] == code and r["home_score"] > r["away_score"]) or
                (r["away"] == code and r["away_score"] > r["home_score"])
                for _, r in games.iterrows()
            )
            observed = len(games)
            return (int(wins) if observed else None,
                    int(observed-wins) if observed else None,
                    round(100 * wins / observed, 1) if observed else None)
        w5, l5, wp5 = record(5)
        w10, l10, wp10 = record(10)
        adv = ratings[code] if full_advanced else {}
        return {
            "team": code,
            "sample": snapshot.get("sample", 0),
            "n5": snapshot.get("n5", 0),
            "n10": snapshot.get("n10", 0),
            "n20": snapshot.get("n20", 0),
            "pts5": snapshot.get("pts5"),
            "allowed5": snapshot.get("allowed5"),
            "margin5": snapshot.get("margin5"),
            "wins5": w5, "losses5": l5, "win_pct5": wp5,
            "pts10": snapshot.get("pts10"),
            "allowed10": snapshot.get("allowed10"),
            "margin10": snapshot.get("margin10"),
            "wins10": w10, "losses10": l10, "win_pct10": wp10,
            "venue": venue,
            "venue_sample": snapshot.get("venue_sample", 0),
            "venue_scored": snapshot.get("venue_scored"),
            "venue_allowed": snapshot.get("venue_allowed"),
            # Do not infer possessions from a points/total score series.
            "pace": adv.get("pace"),
            "off_rating": adv.get("off"),
            "def_rating": adv.get("def"),
        }

    return {
        "source": "Verified ESPN NBA finals strictly before game tipoff",
        "advanced_available": full_advanced,
        "away": one(away, away_snapshot, "away"),
        "home": one(home, home_snapshot, "home"),
        "disclaimer": (
            "Observed points/defense and form are pregame descriptive averages; "
            "PACE/OFFRTG/DEFRTG come only from both verified NBA Advanced rows. "
            "Neither source guarantees future points, wins or bookmaker outcomes."
        ),
    }


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
        "team_comparison": verified_team_comparison(
            earlier, home, away, home_stats, away_stats, ratings),
        "warnings": (home_stats.get("warnings", []) + away_stats.get("warnings", []))[:6],
    }
    return {"means": means, "score_noise": noise, "context": context}
