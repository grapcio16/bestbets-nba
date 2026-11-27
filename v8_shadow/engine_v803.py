"""V8.03 research-only factorized pace/efficiency model.

Shares validated input and final-score mechanics with V8.02, but fits a
different target. No historical settled shadow forecast is used for tuning.
"""
from hashlib import sha256
import numpy as np
import pandas as pd

from v8_shadow.engine import (
    FINAL_RESULT_DELAY, MIN_TRAIN, MIN_HOLDOUT, _feature_row, _prepare_history,
    _time, _ridge_fit, _predict, _scenario, _resolve_overtime_draws,
)

VERSION = "v8_possessions_shadow_v03"
LEAD = pd.Timedelta(minutes=15)
ALPHA = 24.0


def _vector(row):
    return np.r_[row["x"], row["league_pace"], row["league_off"]]


def _targets(game):
    pace = (float(game["home_poss"]) + float(game["away_poss"])) / 2
    return np.array([pace, 100 * float(game["home_score"]) / pace,
                     100 * float(game["away_score"]) / pace])


def _points(targets):
    targets = np.asarray(targets)
    return targets[..., 0, None] * targets[..., 1:] / 100


def _examples(past):
    features, targets, times = [], [], []
    known, cursor = [], 0
    for game in past:
        tip = _time(game["start_utc"])
        while (cursor < len(past) and
               _time(past[cursor]["start_utc"]) + FINAL_RESULT_DELAY <= tip - LEAD):
            known.append(past[cursor])
            cursor += 1
        row = _feature_row(game, known)
        if row is not None:
            features.append(_vector(row))
            targets.append(_targets(game))
            times.append(tip)
    return np.asarray(features), np.asarray(targets), times


def _fit(x, y, times):
    holdout = max(MIN_HOLDOUT, int(len(x) * 0.24))
    if len(x) <= holdout:
        return None
    # Purge labels from games not yet safely complete at first validation forecast.
    boundary = times[-holdout] - LEAD
    fit_n = sum(t + FINAL_RESULT_DELAY <= boundary for t in times[:-holdout])
    if fit_n < MIN_TRAIN:
        return None
    early = _ridge_fit(x[:fit_n], y[:fit_n], alpha=ALPHA)
    predicted = _predict(early, x[-holdout:])
    residuals = y[-holdout:] - predicted
    point_errors = _points(y[-holdout:]) - _points(predicted)
    if not np.isfinite(residuals).all() or np.any(np.std(point_errors, axis=0) < 3):
        raise ValueError("insufficient empirical score volatility")
    diagnostics = {
        "holdout_n": holdout,
        "holdout_fit_n": fit_n,
        "holdout_team_mae": round(float(np.abs(point_errors).mean()), 2),
        "holdout_total_mae": round(float(np.abs(point_errors.sum(axis=1)).mean()), 2),
        "holdout_pace_mae": round(float(np.abs(residuals[:, 0]).mean()), 2),
        "holdout_total_bias_pred_minus_actual": round(float(-point_errors.sum(axis=1).mean()), 2),
    }
    return _ridge_fit(x, y, alpha=ALPHA), residuals, diagnostics


def predict_v803(games, scheduled_game, asof, n=5000):
    if type(n) is not int or not 500 <= n <= 20000:
        raise ValueError("n outside research simulation bounds")
    cutoff = _time(asof)
    tip = _time(scheduled_game["start_utc"])
    if tip <= cutoff + LEAD:
        raise ValueError("must capture at least 15 min before tipoff")
    if scheduled_game["home"] == scheduled_game["away"]:
        raise ValueError("same team scheduled twice")
    past = [g for g in _prepare_history(games)
            if _time(g["start_utc"]) + FINAL_RESULT_DELAY <= cutoff
            and str(g["game_id"]) != str(scheduled_game["game_id"])]
    x, y, times = _examples(past)
    fit = _fit(x, y, times)
    if fit is None:
        return {"status": "insufficient_evidence", "model_id": VERSION,
                "training_examples": len(x)}
    fresh = _feature_row(scheduled_game, past)
    if fresh is None:
        return {"status": "insufficient_team_history", "model_id": VERSION,
                "training_examples": len(x)}
    model, residuals, diagnostics = fit
    center = _predict(model, _vector(fresh))[0]
    mean = _points(center)
    if not np.isfinite(center).all() or not 75 <= center[0] <= 125 or np.any((mean < 70) | (mean > 165)):
        return {"status": "unreliable_extrapolation", "model_id": VERSION}
    seed = int.from_bytes(sha256(f"{VERSION}|{scheduled_game['game_id']}|{cutoff.isoformat()}".encode()).digest()[:8], "big")
    rng = np.random.default_rng(seed)
    # Bootstrap pace and two efficiencies together; preserve their dependence.
    # No hard-coded subtraction based on the nine already settled games.
    sampled = center + residuals[rng.integers(len(residuals), size=n)] - residuals.mean(axis=0)
    sampled += rng.multivariate_normal(np.zeros(3), np.cov(residuals, rowvar=False) * .08, size=n)
    sampled[:, 0] = np.clip(sampled[:, 0], 65, 140)
    sampled[:, 1:] = np.clip(sampled[:, 1:], 55, 180)
    regulation = np.clip(np.rint(_points(sampled)), 60, 180).astype(int)
    draws, ties, periods = _resolve_overtime_draws(regulation, mean, rng)
    selected, mass = _scenario(draws)
    home, away = draws.T
    win = float(np.mean(home > away))
    quantiles = lambda v: [round(float(z), 1) for z in np.quantile(v, [.1, .5, .9])]
    return {
        "status": "shadow_only", "model_id": VERSION,
        "game_id": str(scheduled_game["game_id"]),
        "start_utc": tip.isoformat(), "forecast_time_utc": cutoff.isoformat(),
        "home": str(scheduled_game["home"]), "away": str(scheduled_game["away"]),
        "scenario_home": selected[0], "scenario_away": selected[1],
        "scenario_bin_size_pts": 5, "scenario_bin_probability_pct": round(mass * 100, 2),
        "mean_home": round(float(home.mean()), 2), "mean_away": round(float(away.mean()), 2),
        "mean_total": round(float((home + away).mean()), 2),
        "regulation_mean_home": round(float(mean[0]), 2),
        "regulation_mean_away": round(float(mean[1]), 2),
        "expected_possessions": round(float(center[0]), 2),
        "expected_home_points_per_100": round(float(center[1]), 2),
        "expected_away_points_per_100": round(float(center[2]), 2),
        "home_win_probability_pct": round(100 * win, 2),
        "away_win_probability_pct": round(100 * (1 - win), 2),
        "home_p10_p50_p90": quantiles(home), "away_p10_p50_p90": quantiles(away),
        "total_p10_p50_p90": quantiles(home + away),
        "overtime_probability_pct": round(100 * ties / n, 2),
        "overtime_trajectory_count": ties, "overtime_max_periods_simulated": int(periods.max()),
        "final_scores_include_simulated_overtime": True,
        "training_examples": len(x), "history_matches": len(past),
        "home_sample": fresh["home_sample"], "away_sample": fresh["away_sample"],
        "source": "Observed regulation team boxscores; joint pace and efficiency model",
        "uncertainty": "Research only; no verified lineups/injuries; overtime approximation.",
        "n": n, **diagnostics,
    }
