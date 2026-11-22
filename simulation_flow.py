"""Conditional game-flow reconstruction from the SAME 5,000 end-score draws.

The existing Monte Carlo engine models final NBA scores, not actual possessions,
quarter rotations, scoring runs or verified starting lineups. This auxiliary
display samples a neutral, shared-pace allocation of each already-simulated
final team total across eight six-minute windows. No new outcome/winner is
inferred or fed back into V7.2/V7.4/V7.5. Every output carries that caveat.
"""
from __future__ import annotations

from hashlib import sha256
import numpy as np


METHOD = (
    "Rekonstrukcja warunkowa z 5 000 wyników końcowych. "
    "Neutralny rozkład punktów w czasie; nie są to dane play-by-play, "
    "prognozowane rotacje ani zweryfikowane prawdopodobieństwa kwart. "
    "Dogrywka zawarta w wyniku końcowym jest umownie rozłożona na 48 minut."
)


def _allocate(scores: np.ndarray, weights: np.ndarray, rng) -> np.ndarray:
    """Vectorized per-draw multinomial split, keeping each final EXACT."""
    scores = np.asarray(scores, dtype=np.int64)
    n = len(scores)
    out = np.zeros((n, 8), dtype=np.int32)
    remaining = scores.copy()
    fraction = np.ones(n, dtype=float)
    for j in range(7):
        p = np.clip(weights[:, j] / np.maximum(fraction, 1e-12), 0, 1)
        drawn = rng.binomial(remaining, p)
        out[:, j] = drawn
        remaining -= drawn
        fraction -= weights[:, j]
    out[:, 7] = remaining
    return out


def conditional_flow(away_scores, home_scores, *, game_id: str, model_id: str):
    """Derive compact, evidence-limited flow data from final score draws only."""
    a = np.asarray(away_scores)
    h = np.asarray(home_scores)
    if (a.ndim != 1 or h.ndim != 1 or len(a) != 5000 or len(h) != 5000
            or not np.isfinite(a).all() or not np.isfinite(h).all()
            or np.any(a < 0) or np.any(h < 0)):
        return {"available": False, "reason": "Brak pełnych 5 000 losowań końcowego wyniku."}
    # Independent display RNG: cannot alter existing seeded 5k score draws.
    digest = sha256((str(game_id)+"|"+str(model_id)+"|FLOW_V1|"+
                     str(int(np.sum(a)))+"|"+str(int(np.sum(h)))).encode()).digest()
    rng = np.random.default_rng(int.from_bytes(digest[:8], "big"))
    # Both teams share a game-specific pace profile within a draw. We have
    # no quarter-specific evidence, so 8 equal prior windows, not fake trends.
    weights = rng.dirichlet(np.full(8, 20.0), size=5000)
    away = _allocate(a.astype(np.int32), weights, rng)
    home = _allocate(h.astype(np.int32), weights, rng)
    delta = home - away
    cumulative = np.column_stack(
        [np.zeros(5000, dtype=int), np.cumsum(delta, axis=1)])
    timeline = []
    for step in range(9):
        margin = cumulative[:, step]
        timeline.append({
            "minute": step*6,
            "margin_mean": round(float(np.mean(margin)), 2),
            "margin_p10": round(float(np.percentile(margin, 10)), 2),
            "margin_p90": round(float(np.percentile(margin, 90)), 2),
            "away_ahead_pct": round(100*float(np.mean(margin < 0)), 1),
            "home_ahead_pct": round(100*float(np.mean(margin > 0)), 1),
            "tie_pct": round(100*float(np.mean(margin == 0)), 1),
        })
    quarters = []
    for q in range(4):
        m = np.sum(delta[:, q*2:q*2+2], axis=1)
        quarters.append({
            "quarter": q + 1,
            "away_outscores_pct": round(float(np.mean(m < 0))*100, 1),
            "home_outscores_pct": round(float(np.mean(m > 0))*100, 1),
            "tie_pct": round(float(np.mean(m == 0))*100, 1),
            "away_mean": round(float(np.mean(away[:, q*2:q*2+2])), 2) * 2,
            "home_mean": round(float(np.mean(home[:, q*2:q*2+2])), 2) * 2,
        })
    clutch = delta[:, 7]
    spread = h - a
    return {
        "available": True, "method": "conditional_neutral_6min_v1",
        "n_sims": 5000, "source": METHOD,
        "timeline": timeline, "quarters": quarters,
        "clutch": {
            "away_outscores_pct": round(float(np.mean(clutch < 0))*100, 1),
            "home_outscores_pct": round(float(np.mean(clutch > 0))*100, 1),
            "tie_pct": round(float(np.mean(clutch == 0))*100, 1),
            "home_margin_mean": round(float(np.mean(clutch)), 2),
        },
        "volatility": {
            "final_spread_p10": round(float(np.percentile(spread, 10)), 1),
            "final_spread_p90": round(float(np.percentile(spread, 90)), 1),
            "final_spread_sd": round(float(np.std(spread)), 1),
        },
        "rotation_available": False, "scoring_runs_available": False,
    }
