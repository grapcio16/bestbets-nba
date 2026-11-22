"""HOOPZARO conditional quarter research (V7.2/V7.4/V7.5/V7.6 shadow).

Each model's Q1-Q4 draws partition the EXACT SAME 5,000 completed-score
scenarios used by its parent game model. Every draw conserves each team's
final simulated total. Missing historical quarters -> no quarter forecasts.

IMPORTANT: This is an experimental conditioned time-allocation model, NOT
possession/play-by-play forecasting. The parent's simplified OT points are
allocated across Q1-Q4; grading therefore excludes actual overtime games.
It does not alter public outcomes or claim calibrated quarter probabilities.
"""
from __future__ import annotations

from hashlib import sha256
import numpy as np
import pandas as pd

from simulation_quarter_model import QCOLS, pregame_quarter_evidence
from simulation_data_audit import verified_history

MODEL_IDS = {
    "auto_legacy_v72": "auto_q_v72_shadow_v1",
    "auto_research_form_v74": "auto_q_v74_shadow_v1",
    "auto_context_full_v75": "auto_q_v75_shadow_v1",
    "auto_shadow_home_v76": "auto_q_v76_shadow_v1",
}
N_DRAWS = 5000



def complete_quarter_history(history, cutoff):
    """Verified four-quarter regulation finals only, with no future leakage."""
    rows = verified_history(history, cutoff)
    if rows.empty or not set(QCOLS).issubset(rows.columns):
        return rows.iloc[:0].copy()
    rows = rows.copy()
    for col in QCOLS:
        rows[col] = pd.to_numeric(rows[col], errors="coerce")
    valid = rows[list(QCOLS)].notna().all(axis=1)
    for side in ("home", "away"):
        cols = [f"{side}_q{i}" for i in range(1, 5)]
        points = rows[cols]
        valid &= points.ge(0).all(axis=1) & points.le(75).all(axis=1)
        valid &= (points % 1).eq(0).all(axis=1)
        valid &= points.sum(axis=1).eq(rows[f"{side}_score"])
    return rows.loc[valid].sort_values("start_utc").copy()


def _allocate_total(scores, weights, rng):
    """Per-scenario four-quarter partition; sums remain exactly unchanged."""
    remaining = np.asarray(scores, dtype=np.int32).copy()
    result = np.zeros((len(remaining), 4), dtype=np.int32)
    remaining_weight = np.ones(len(remaining), dtype=float)
    for i in range(3):
        p = np.clip(weights[:, i] / np.maximum(remaining_weight, 1e-10), 0, 1)
        result[:, i] = rng.binomial(remaining, p)
        remaining -= result[:, i]
        remaining_weight -= weights[:, i]
    result[:, 3] = remaining
    if not np.array_equal(np.sum(result, axis=1), scores):
        raise AssertionError("Quarter allocation must preserve every game draw.")
    return result


def generate_quarter_draws(history, game, home_draws, away_draws, base_model_id):
    """Return (home[n,4], away[n,4]) from frozen game draws, or None."""
    if base_model_id not in MODEL_IDS:
        return None
    gid = str(game.get("game_id") or "")
    start = pd.to_datetime(game.get("start_utc"), utc=True, errors="coerce")
    h = np.asarray(home_draws)
    a = np.asarray(away_draws)
    if (not gid.isdecimal() or pd.isna(start)
            or h.shape != (N_DRAWS,) or a.shape != (N_DRAWS,)
            or not np.isfinite(h).all() or not np.isfinite(a).all()
            or np.any(h < 0) or np.any(a < 0)
            or not np.array_equal(h, np.rint(h))
            or not np.array_equal(a, np.rint(a))):
        return None
    observed = pregame_quarter_evidence(history, game)
    if observed.get("available") is not True:
        return None
    home_share = np.asarray(observed["home"], dtype=float)
    away_share = np.asarray(observed["away"], dtype=float)
    if (home_share.shape != (4,) or away_share.shape != (4,)
            or not np.isfinite(home_share).all() or not np.isfinite(away_share).all()
            or min(home_share.min(), away_share.min()) <= 0
            or abs(home_share.sum()-1) > .001 or abs(away_share.sum()-1) > .001):
        return None

    seed = int.from_bytes(sha256((gid + "|" + base_model_id + "|Q1").encode()).digest()[:8], "big")
    rng = np.random.default_rng(seed)
    # Matchup-specific observed scoring shares, shrunk through the existing
    # ESPN quarter evidence. Common quarter pace correlates both teams.
    shared = rng.dirichlet((home_share + away_share) * 16.0, size=N_DRAWS)
    h_weights = .3 * shared + .7 * rng.dirichlet(home_share * 75.0, size=N_DRAWS)
    a_weights = .3 * shared + .7 * rng.dirichlet(away_share * 75.0, size=N_DRAWS)
    q_h = _allocate_total(h.astype(np.int32), h_weights, rng)
    q_a = _allocate_total(a.astype(np.int32), a_weights, rng)
    return q_h, q_a, observed


def forecast_game_quarters(history, game, home_draws, away_draws, base_model_id):
    """Freeze independent per-quarter snapshots tied to a parent score model."""
    result = generate_quarter_draws(history, game, home_draws, away_draws, base_model_id)
    if result is None:
        return []
    home_q, away_q, evidence = result
    forecasts = []
    for idx in range(4):
        win_h = round(float(np.mean(home_q[:, idx] > away_q[:, idx]) * 100), 2)
        win_a = round(float(np.mean(home_q[:, idx] < away_q[:, idx]) * 100), 2)
        tie = round(100 - win_h - win_a, 2)
        forecasts.append({
            "game_id": str(game["game_id"]),
            "model_id": MODEL_IDS[base_model_id],
            "base_model_id": base_model_id,
            "start_utc": game["start_utc"],
            "home": str(game["home"]), "away": str(game["away"]),
            "quarter": idx + 1,
            "home_points": round(float(home_q[:, idx].mean()), 3),
            "away_points": round(float(away_q[:, idx].mean()), 3),
            "home_win_pct": win_h,
            "away_win_pct": win_a,
            "tie_pct": tie,
            "home_sample": evidence["home_sample"],
            "away_sample": evidence["away_sample"],
            "source": ("ESPN completed regulation quarters; conditional on "
                       + base_model_id + " 5000 complete-game score draws; "
                       "OT allocation approximated; uncalibrated research"),
        })
    return forecasts


def build_quarter_forecasts(history, parent_scenarios):
    """Input: frozen model's actual score scenarios, not a second game forecast."""
    forecasts = []
    for item in parent_scenarios:
        forecasts.extend(forecast_game_quarters(
            history, item["game"], item["home_draws"], item["away_draws"],
            item["base_model_id"]))
    return forecasts


def quarter_performance_metrics(frame):
    """Per parent model / quarter: team MAE, signed bias, winner hit, Brier."""
    cols = ["model_id", "quarter", "n", "team_mae", "team_bias",
            "winner_accuracy", "brier_3way"]
    if frame is None or frame.empty:
        return pd.DataFrame(columns=cols)
    valid = frame.dropna(subset=["home_actual", "away_actual"])
    result = []
    for (model, quarter), g in valid.groupby(["model_id", "quarter"]):
        hp, ap = g["home_points"].to_numpy(float), g["away_points"].to_numpy(float)
        ha, aa = g["home_actual"].to_numpy(float), g["away_actual"].to_numpy(float)
        probs = np.stack([
            g["home_win_pct"].to_numpy(float),
            g["away_win_pct"].to_numpy(float),
            g["tie_pct"].to_numpy(float),
        ], axis=1) / 100
        realized = np.stack([ha > aa, aa > ha, ha == aa], axis=1).astype(float)
        result.append({
            "model_id": model, "quarter": int(quarter), "n": len(g),
            "team_mae": round(float(np.mean((np.abs(hp-ha) + np.abs(ap-aa)) / 2)), 3),
            "team_bias": round(float(np.mean(((hp-ha) + (ap-aa)) / 2)), 3),
            "winner_accuracy": round(float(np.mean(
                np.argmax(probs, axis=1) == np.argmax(realized, axis=1)) * 100), 2),
            "brier_3way": round(float(np.mean(np.sum((probs-realized)**2, axis=1))), 4),
        })
    return pd.DataFrame(result, columns=cols).sort_values(["model_id", "quarter"])
