"""HOOPZARO V8 Shadow v0.1 — independent, evidence-only possession model.

This module intentionally imports NOTHING from V7 simulation engines. It uses
only numpy/pandas, real past final box scores, and chronological training.
No bookmaker odds, dummy possessions, made-up injuries, retroactive updates,
or release-facing predictions.

A game is encoded as two physical teams with validated FGA/FTA/OREB/TOV,
plus verified final points. The model learns expected points from previous
possession-based attack, defense, pace, form and rest. Both team scores are
sampled JOINTLY from out-of-time residual pairs.

A representative scenario is a high-density 5x5-point score bin from the
joint distribution; it is not presented as a uniquely likely exact score.
Expected scores remain separately available. No claims of superior accuracy
until prospective data and disjoint historical evaluation support them.
"""
from __future__ import annotations

from collections import defaultdict
from hashlib import sha256
from math import isfinite

import numpy as np
import pandas as pd

VERSION = "v8_possessions_shadow_v01"
MIN_TEAM_GAMES = 5
MIN_TRAIN = 40
MIN_HOLDOUT = 16
# No historical final-result timestamp is archived by the current provider.
# Treat a game as safely known only four hours after its recorded tipoff.
# Conservative for regulation games; overtime is excluded from V8 evidence.
FINAL_RESULT_DELAY = pd.Timedelta(hours=4)
FEATURES = (
    "home_off_above_league", "away_def_above_league",
    "away_off_above_league", "home_def_above_league",
    "expected_possessions_minus_league", "home_off_trend",
    "away_off_trend", "home_rest_days", "away_rest_days",
    "home_recent_venue_off", "away_recent_venue_off",
)


def _time(value):
    stamp = pd.to_datetime(value, utc=True, errors="coerce")
    if pd.isna(stamp):
        raise ValueError("missing/invalid UTC instant")
    return stamp


def _finite(value):
    try:
        number = float(value)
    except (ValueError, TypeError, OverflowError):
        raise ValueError("missing numerical stat")
    if not isfinite(number):
        raise ValueError("nonfinite stat")
    return number


def _valid_game(g):
    if not isinstance(g, dict):
        raise ValueError("game must be a record")
    code = str(g.get("game_id") or "")
    if not code.isdecimal() or len(code) > 20:
        raise ValueError("game id missing")
    away, home = str(g.get("away") or ""), str(g.get("home") or "")
    if not (2 <= len(away) <= 3 and 2 <= len(home) <= 3 and away != home):
        raise ValueError("invalid team codes")
    _time(g.get("start_utc"))
    for side in ("away", "home"):
        points = _finite(g.get(f"{side}_score"))
        poss = _finite(g.get(f"{side}_poss"))
        if not (50 <= points <= 200 and 65 <= poss <= 140):
            raise ValueError("implausible final points/possessions")
    if abs(_finite(g["home_poss"]) - _finite(g["away_poss"])) > 12:
        raise ValueError("both possession estimates are inconsistent")
    return g


def _recent_mean(values, decay=11.0):
    a = np.asarray(values, dtype=float)
    if not len(a) or not np.isfinite(a).all():
        raise ValueError("history missing/corrupt")
    ages = np.arange(len(a) - 1, -1, -1)
    weights = np.exp(-ages / decay)
    return float(np.average(a, weights=weights))


def _profile(past: list[dict], team: str):
    relevant = [g for g in past if team in (g["away"], g["home"])]
    if len(relevant) < MIN_TEAM_GAMES:
        return None
    recent = relevant[-25:]
    scored, allowed, pace, venues = [], [], [], []
    for g in recent:
        side = "home" if g["home"] == team else "away"
        other = "away" if side == "home" else "home"
        pp = float(g[side + "_poss"])
        oo = float(g[other + "_poss"])
        scored.append(float(g[side + "_score"]) * 100 / pp)
        allowed.append(float(g[other + "_score"]) * 100 / oo)
        pace.append((pp + oo) / 2)
        venues.append(side)
    home_attacks = [x for x, side in zip(scored, venues) if side == "home"]
    away_attacks = [x for x, side in zip(scored, venues) if side == "away"]
    return {
        "off": _recent_mean(scored), "def": _recent_mean(allowed),
        "pace": _recent_mean(pace),
        "trend": _recent_mean(scored[-5:], 4.0) - _recent_mean(scored, 11.0),
        "venue_home": _recent_mean(home_attacks, 7.0) if len(home_attacks) >= 3 else None,
        "venue_away": _recent_mean(away_attacks, 7.0) if len(away_attacks) >= 3 else None,
        "last": _time(recent[-1]["start_utc"]), "n": len(relevant),
    }


def _feature_row(game: dict, past: list[dict]):
    home = _profile(past, game["home"])
    away = _profile(past, game["away"])
    if home is None or away is None or len(past) < 32:
        return None
    efficiency = np.mean([
        float(g[side + "_score"]) / float(g[side + "_poss"]) * 100
        for g in past[-180:] for side in ("home", "away")
    ])
    league_pace = np.mean([(float(g["home_poss"]) + float(g["away_poss"])) / 2
                           for g in past[-180:]])
    predicted_poss = (home["pace"] + away["pace"]) / 2
    kickoff = _time(game["start_utc"])
    home_rest = (kickoff - home["last"]).total_seconds() / 86400 - 1
    away_rest = (kickoff - away["last"]).total_seconds() / 86400 - 1
    # Rest is full days *between* game starts, minus the game day.
    # A real back-to-back can begin <24h after the previous tipoff and has
    # zero days off; that is not chronology leakage. Only a previous game
    # with a strictly LATER start time signals leakage.
    if min(home_rest, away_rest) < -1.001:
        raise ValueError("history leakage: previous game starts in future")
    rest = lambda n: float(min(max(n, 0.0), 5.0))
    def venue_shift(p, key):
        if p[key] is None:
            return 0.0  # Unsupported signal contributes no venue adjustment.
        return p[key] - p["off"]
    vector = [
        (home["off"] - efficiency) * predicted_poss / 100,
        (away["def"] - efficiency) * predicted_poss / 100,
        (away["off"] - efficiency) * predicted_poss / 100,
        (home["def"] - efficiency) * predicted_poss / 100,
        predicted_poss - league_pace,
        home["trend"] * predicted_poss / 100,
        away["trend"] * predicted_poss / 100,
        rest(home_rest), rest(away_rest),
        venue_shift(home, "venue_home") * predicted_poss / 100,
        venue_shift(away, "venue_away") * predicted_poss / 100,
    ]
    if not np.isfinite(vector).all():
        raise ValueError("invalid input features")
    return {"x": np.asarray(vector, dtype=float),
            "home_sample": home["n"], "away_sample": away["n"],
            "league_off": float(efficiency),
            "league_pace": float(league_pace),
            "expected_possessions": float(predicted_poss),
            "asof_utc": kickoff.isoformat()}


def _prepare_history(games):
    """Only validated data; never fill missing FGA, FTA or possessions."""
    valid = {}
    for original in games:
        try:
            row = dict(_valid_game(dict(original)))
        except (ValueError, TypeError, KeyError):
            continue
        key = row["game_id"]
        if key in valid:
            raise ValueError("duplicate game id in V8 historical evidence")
        valid[key] = row
    return sorted(valid.values(), key=lambda g: (_time(g["start_utc"]), g["game_id"]))


def _examples(games, cutoff):
    """Construct genuine pregame features with a conservative results delay.

    Previously, the final score of a 19:00 game could enter features for a
    19:30 game, even though the 19:00 game was still being played. That is
    target leakage, not forecasting skill. Only games whose tipoff was at
    least FINAL_RESULT_DELAY earlier can inform another game's features.
    """
    xs, ys = [], []
    ordered = sorted(
        (g for g in games
         if _time(g["start_utc"]) + FINAL_RESULT_DELAY <= cutoff),
        key=lambda row: _time(row["start_utc"]),
    )
    if not ordered:
        return np.asarray(xs, dtype=float), np.asarray(ys, dtype=float)

    known, completed_index = [], 0
    for stamp, group in pd.DataFrame(ordered).groupby("start_utc", sort=True):
        forecast_time = _time(stamp)
        while (completed_index < len(ordered) and
               _time(ordered[completed_index]["start_utc"]) +
               FINAL_RESULT_DELAY <= forecast_time):
            known.append(ordered[completed_index])
            completed_index += 1
        for g in group.to_dict("records"):
            example = _feature_row(g, known)
            if example is not None:
                xs.append(example["x"])
                ys.append([float(g["home_score"]), float(g["away_score"])])
    return np.asarray(xs, dtype=float), np.asarray(ys, dtype=float)


def _ridge_fit(x, y, alpha=24.0):
    # Standardize every signal so alpha does not depend on arbitrary units.
    mean = np.mean(x, axis=0)
    std = np.std(x, axis=0)
    std = np.where(std < 1e-8, 1.0, std)
    z = (x - mean) / std
    design = np.column_stack((np.ones(len(z)), z))
    penalty = np.eye(design.shape[1]) * alpha
    penalty[0, 0] = 0
    weights = np.linalg.solve(design.T @ design + penalty, design.T @ y)
    return mean, std, weights


def _predict(model, xs):
    mean, std, weights = model
    x = np.asarray(xs, dtype=float)
    if x.ndim == 1:
        x = x.reshape(1, -1)
    return np.column_stack((np.ones(len(x)), (x - mean) / std)) @ weights


def _residual_evidence(xs, ys):
    n = len(xs)
    holdout = max(MIN_HOLDOUT, int(n * 0.24))
    if n - holdout < MIN_TRAIN:
        raise ValueError(f"insufficient chronological training evidence ({n})")
    early = _ridge_fit(xs[:-holdout], ys[:-holdout])
    predicted = _predict(early, xs[-holdout:])
    residuals = np.asarray(ys[-holdout:] - predicted, dtype=float)
    if not np.isfinite(residuals).all():
        raise ValueError("invalid out-of-time residuals")
    if np.any(np.std(residuals, axis=0) < 3):
        raise ValueError("insufficient empirical score volatility")
    # The held-out residual mean is retained for bias diagnostics, but the
    # bootstrap is centered: a small recent window cannot force a bias shift.
    return residuals, {
        "holdout_n": holdout,
        "holdout_team_mae": float(np.mean(np.abs(residuals))),
        "holdout_total_mae": float(np.mean(np.abs(residuals.sum(axis=1)))),
        "holdout_home_bias": float(np.mean(residuals[:, 0])),
        "holdout_away_bias": float(np.mean(residuals[:, 1])),
    }


def _scenario(draws, width=5):
    bins = np.floor(draws / width).astype(int)
    cells, counts = np.unique(bins, axis=0, return_counts=True)
    winners = np.flatnonzero(counts == counts.max())
    # Deterministic tie break: joint cell closest to expectation.
    target = draws.mean(axis=0)
    chosen = min(winners, key=lambda idx: float(np.linalg.norm(
        (cells[idx] + .5) * width - target)))
    mask = (bins == cells[chosen]).all(axis=1)
    inside = draws[mask]
    centre = np.median(inside, axis=0)
    selected = inside[np.argmin(np.linalg.norm(inside - centre, axis=1))]
    return [int(selected[0]), int(selected[1])], float(counts[chosen] / len(draws))


def predict_v8(games, scheduled_game: dict, asof, n=5000):
    """Return frozen pregame V8 forecast or explicit insufficiency diagnostic.

    Games must represent actual final team boxscores (no synthetic possession
    estimates). The upcoming event is never inserted into the training set.
    """
    if n < 500 or n > 20000:
        raise ValueError("n outside research simulation bounds")
    cutoff = _time(asof)
    tipoff = _time(scheduled_game.get("start_utc"))
    if tipoff <= cutoff + pd.Timedelta(minutes=15):
        raise ValueError("must capture at least 15 min before tipoff")
    if scheduled_game.get("home") == scheduled_game.get("away"):
        raise ValueError("same team scheduled twice")
    history = _prepare_history(games)
    # Provider archives no reliable completion timestamp. A game whose tipoff
    # precedes this forecast by just 30–90 minutes may still be LIVE; its
    # final points could not have been known. Enforce the same conservative
    # four-hour availability rule in training and current-match features.
    past = [g for g in history
            if _time(g["start_utc"]) + FINAL_RESULT_DELAY <= cutoff]
    x, y = _examples(past, cutoff)
    if len(x) < MIN_TRAIN + MIN_HOLDOUT:
        return {"status": "insufficient_evidence", "model_id": VERSION,
                "training_examples": len(x), "required": MIN_TRAIN + MIN_HOLDOUT}
    fresh = _feature_row(scheduled_game, past)
    if fresh is None:
        return {"status": "insufficient_team_history", "model_id": VERSION,
                "training_examples": len(x)}
    residuals, validation = _residual_evidence(x, y)
    model = _ridge_fit(x, y)
    mean_score = _predict(model, fresh["x"])[0]
    if np.any(~np.isfinite(mean_score)) or np.any((mean_score < 70) | (mean_score > 165)):
        return {"status": "unreliable_extrapolation", "model_id": VERSION}
    seed = int.from_bytes(sha256(
        f"{VERSION}|{scheduled_game['game_id']}|{cutoff.isoformat()}".encode()
    ).digest()[:8], "big")
    rng = np.random.default_rng(seed)
    ids = rng.integers(0, len(residuals), size=n)
    # Two-team residual pairs preserve shared effects (tempo, shootouts).
    paired = residuals[ids] - residuals.mean(axis=0)
    # Calibrated light kernel smoothing around empirical score-pair residuals.
    empirical_cov = np.cov(residuals, rowvar=False)
    jitter = rng.multivariate_normal([0, 0], empirical_cov * 0.08, size=n)
    draws = np.rint(mean_score + paired + jitter).astype(int)
    # A 60–180 range bounds physically implausible bootstrap tail estimates;
    # it is not used to shrink the expected pregame score.
    draws = np.clip(draws, 60, 180)
    selected, mass = _scenario(draws)
    home, away = draws[:, 0], draws[:, 1]
    home_wins = float(np.mean(home > away) + 0.5 * np.mean(home == away))
    def quantiles(values):
        return [round(float(z), 1) for z in np.quantile(values, [.1, .5, .9])]
    return {
        "status": "shadow_only",
        "model_id": VERSION,
        "game_id": str(scheduled_game["game_id"]),
        "start_utc": tipoff.isoformat(),
        "forecast_time_utc": cutoff.isoformat(),
        "home": str(scheduled_game["home"]), "away": str(scheduled_game["away"]),
        "scenario_home": selected[0], "scenario_away": selected[1],
        "scenario_bin_size_pts": 5,
        "scenario_bin_probability_pct": round(mass * 100, 2),
        "mean_home": round(float(mean_score[0]), 2),
        "mean_away": round(float(mean_score[1]), 2),
        "mean_total": round(float(mean_score.sum()), 2),
        "home_win_probability_pct": round(home_wins * 100, 2),
        "away_win_probability_pct": round((1 - home_wins) * 100, 2),
        "home_p10_p50_p90": quantiles(home),
        "away_p10_p50_p90": quantiles(away),
        "total_p10_p50_p90": quantiles(home + away),
        "training_examples": int(len(x)),
        "history_matches": int(len(past)),
        "home_sample": fresh["home_sample"],
        "away_sample": fresh["away_sample"],
        "expected_possessions": round(fresh["expected_possessions"], 2),
        "holdout_team_mae": round(validation["holdout_team_mae"], 2),
        "holdout_total_mae": round(validation["holdout_total_mae"], 2),
        "holdout_n": validation["holdout_n"],
        "feature_names": list(FEATURES),
        "source": "Observed past NBA final boxscores; possession estimator",
        "uncertainty": ("Official lineups/injuries and betting odds are NOT "
                        "included; scenario is a distribution mode, not an "
                        "exact-score certainty."),
        "n": int(n),
    }
