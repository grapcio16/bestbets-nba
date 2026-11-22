"""HOOPZARO research-only quarter forecasts, independent of final-score draws.

Only observed completed four-quarter ESPN games strictly before tipoff train
this experimental baseline. Does not model possessions, runs or player rotations.
Quarter lead probabilities are Monte Carlo fractions, NOT calibrated odds.
"""
from __future__ import annotations

from hashlib import sha256
import numpy as np
import pandas as pd

from simulation_data_audit import verified_history
from simulation_quarter_model import QCOLS

MODEL_ID = "auto_quarters_shadow_v1"
SAMPLE_MIN = 6
WINDOW = 15
N_DRAWS = 5000


def complete_quarter_history(history, cutoff):
    """Reject missing/corrupt regulation linescores and any future observation."""
    rows = verified_history(history, cutoff)
    if not set(QCOLS).issubset(rows.columns):
        return rows.iloc[:0].copy()
    rows = rows.copy()
    for col in QCOLS:
        rows[col] = pd.to_numeric(rows[col], errors="coerce")
    valid = rows[list(QCOLS)].notna().all(axis=1)
    for side in ("home", "away"):
        cols = [f"{side}_q{i}" for i in range(1, 5)]
        points = rows[cols]
        valid &= points.ge(0).all(axis=1) & points.le(75).all(axis=1)
        valid &= points.sum(axis=1).eq(rows[f"{side}_score"])
        valid &= (points % 1).eq(0).all(axis=1)
    return rows.loc[valid].sort_values("start_utc").copy()


def _team_samples(rows, team):
    own = rows[(rows["home"] == team) | (rows["away"] == team)].tail(WINDOW)
    if own.empty:
        return None
    home = (own["home"] == team).to_numpy()
    scored = np.asarray([
        np.where(home, own[f"home_q{i}"], own[f"away_q{i}"])
        for i in range(1, 5)
    ], dtype=float).T
    allowed = np.asarray([
        np.where(home, own[f"away_q{i}"], own[f"home_q{i}"])
        for i in range(1, 5)
    ], dtype=float).T
    return {"count": len(own), "home": home, "scored": scored, "allowed": allowed}


def _expected_points(offense, defense, is_home, league):
    """Shrink noisy offense/defense to observed season league quarter means."""
    base = .55 * offense["scored"].mean(axis=0) + .45 * defense["allowed"].mean(axis=0)
    n = min(offense["count"], defense["count"])
    trust = n / (n + 10.0)
    mean = trust * base + (1 - trust) * league
    venue = offense["home"] == bool(is_home)
    if venue.sum() >= 4:
        mean = .85 * mean + .15 * offense["scored"][venue].mean(axis=0)
    return np.clip(mean, 8.0, 55.0)


def forecast_game_quarters(history, game):
    """Return four frozen research predictions or [] if evidence is insufficient."""
    gid = str(game.get("game_id") or "")
    home, away = str(game.get("home") or ""), str(game.get("away") or "")
    start = pd.to_datetime(game.get("start_utc"), utc=True, errors="coerce")
    if (not gid.isdecimal() or len(gid) > 20 or not home or not away
            or home == away or pd.isna(start)):
        return []
    rows = complete_quarter_history(history, start)
    if rows.empty:
        return []
    home_sample = _team_samples(rows, home)
    away_sample = _team_samples(rows, away)
    if (home_sample is None or away_sample is None
            or min(home_sample["count"], away_sample["count"]) < SAMPLE_MIN):
        return []

    league = np.mean(np.stack([
        rows[[f"home_q{i}" for i in range(1, 5)]].to_numpy(dtype=float),
        rows[[f"away_q{i}" for i in range(1, 5)]].to_numpy(dtype=float)
    ], axis=1), axis=(0, 1))
    mean_h = _expected_points(home_sample, away_sample, True, league)
    mean_a = _expected_points(away_sample, home_sample, False, league)

    # A shared game pace and per-quarter pace couple both teams; individual
    # efficiency noise permits leads to reverse without forcing reversals.
    # Volatility priors are preliminary and must be walk-forward validated.
    seed = int.from_bytes(sha256((gid + "|" + MODEL_ID).encode()).digest()[:8], "big")
    rng = np.random.default_rng(seed)
    game_pace = rng.lognormal(mean=-.5 * .06**2, sigma=.06, size=(N_DRAWS, 1))
    quarter_pace = rng.lognormal(mean=-.5 * .12**2, sigma=.12, size=(N_DRAWS, 4))
    away_eff = rng.lognormal(mean=-.5 * .09**2, sigma=.09, size=(N_DRAWS, 4))
    home_eff = rng.lognormal(mean=-.5 * .09**2, sigma=.09, size=(N_DRAWS, 4))
    a = rng.poisson(mean_a * game_pace * quarter_pace * away_eff)
    h = rng.poisson(mean_h * game_pace * quarter_pace * home_eff)

    predictions = []
    for idx in range(4):
        hp = float(np.mean(h[:, idx] > a[:, idx]) * 100)
        ap = float(np.mean(a[:, idx] > h[:, idx]) * 100)
        tp = 100.0 - hp - ap
        predictions.append({
            "game_id": gid, "model_id": MODEL_ID, "start_utc": start,
            "home": home, "away": away, "quarter": idx + 1,
            "home_points": round(float(np.mean(h[:, idx])), 3),
            "away_points": round(float(np.mean(a[:, idx])), 3),
            "home_win_pct": round(hp, 2),
            "away_win_pct": round(ap, 2),
            "tie_pct": round(max(tp, 0.0), 2),
            "home_sample": int(home_sample["count"]),
            "away_sample": int(away_sample["count"]),
            "source": "ESPN verified regulation Q1-Q4; independent research model",
        })
    return predictions


def build_quarter_forecasts(upcoming, history):
    if not isinstance(upcoming, pd.DataFrame) or upcoming.empty:
        return []
    records = []
    for game in upcoming.to_dict("records"):
        records.extend(forecast_game_quarters(history, game))
    return records


def quarter_performance_metrics(frame):
    """Return grouped, settled-only MAE, signed bias and 3-way Brier scores."""
    if frame is None or frame.empty:
        return pd.DataFrame(columns=["quarter", "n", "team_mae", "team_bias", "brier_3way"])
    valid = frame.dropna(subset=["home_actual", "away_actual"]).copy()
    if valid.empty:
        return pd.DataFrame(columns=["quarter", "n", "team_mae", "team_bias", "brier_3way"])
    result = []
    for quarter, g in valid.groupby("quarter"):
        hp = g["home_points"].to_numpy(dtype=float)
        ap = g["away_points"].to_numpy(dtype=float)
        ha = g["home_actual"].to_numpy(dtype=float)
        aa = g["away_actual"].to_numpy(dtype=float)
        prob = np.stack([
            g["home_win_pct"].to_numpy(dtype=float),
            g["away_win_pct"].to_numpy(dtype=float),
            g["tie_pct"].to_numpy(dtype=float),
        ], axis=1) / 100
        actual = np.stack([ha > aa, aa > ha, ha == aa], axis=1).astype(float)
        result.append({
            "quarter": int(quarter), "n": len(g),
            "team_mae": round(float(np.mean((np.abs(hp-ha) + np.abs(ap-aa)) / 2)), 3),
            "team_bias": round(float(np.mean(((hp-ha) + (ap-aa)) / 2)), 3),
            "brier_3way": round(float(np.mean(np.sum((prob-actual)**2, axis=1))), 4),
        })
    return pd.DataFrame(result).sort_values("quarter").reset_index(drop=True)
