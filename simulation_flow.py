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


def _neutral_run_proxy(away_points: np.ndarray, home_points: np.ndarray, rng) -> dict:
    """Toy neutral order of two-point scoring events, conditional on final scores.

    1 leftover point is allowed for odd totals. This is NOT possession,
    play-by-play, bookmaker probability or a calibrated basketball run model.
    Fast vectorized 5k x up to 176 events, never touches final results.
    """
    a = np.asarray(away_points, dtype=np.int32)
    h = np.asarray(home_points, dtype=np.int32)
    n_a = (a + 1) // 2
    n_h = (h + 1) // 2
    max_events = int(max(n_a.max(), n_h.max()))
    indices = np.arange(max_events)[None, :]
    valid_a, valid_h = indices < n_a[:, None], indices < n_h[:, None]
    a_value = np.where(valid_a, 2, 0)
    h_value = np.where(valid_h, 2, 0)
    a_value = np.where((indices == n_a[:, None]-1) & ((a % 2)[:, None] == 1),
                       1, a_value)
    h_value = np.where((indices == n_h[:, None]-1) & ((h % 2)[:, None] == 1),
                       1, h_value)
    vals = np.concatenate((a_value, h_value), axis=1)
    n = len(a)
    teams = np.broadcast_to(np.r_[np.zeros(max_events, dtype=np.int8),
                                  np.ones(max_events, dtype=np.int8)], (n, 2*max_events))
    keys = rng.random((n, 2*max_events))
    keys[vals == 0] = 2.0
    order = np.argsort(keys, axis=1)
    points = np.take_along_axis(vals, order, axis=1)
    owners = np.take_along_axis(teams, order, axis=1)
    current = np.zeros(n, dtype=np.int16)
    previous = np.full(n, -1, dtype=np.int8)
    longest = np.zeros(n, dtype=np.int16)
    for step in range(points.shape[1]):
        point, owner = points[:, step], owners[:, step]
        active = point > 0
        current = np.where(active & (owner == previous), current + point,
                           np.where(active, point, current))
        previous = np.where(active, owner, previous)
        longest = np.maximum(longest, current)
    return {
        "method": "neutral_order_two_point_events_v1",
        "basis": "Wariant ilustracyjny: losowa kolejność zdobyczy 2 pkt "
                 "(z końcową 1 pkt dla nieparzystych sum). Nie jest to "
                 "play-by-play, rzeczywista seria NBA ani skalibrowana szansa.",
        "n_sims": int(n),
        "at_least_6_pct": round(100*float(np.mean(longest >= 6)), 1),
        "at_least_8_pct": round(100*float(np.mean(longest >= 8)), 1),
        "at_least_10_pct": round(100*float(np.mean(longest >= 10)), 1),
        "average_max_unanswered": round(float(np.mean(longest)), 1),
    }


def conditional_flow(away_scores, home_scores, *, game_id: str, model_id: str,
                     quarter_evidence: dict | None = None):
    """Allocate original final-score draws using verified pretipoff quarter profiles.

    A neutral illustrative trajectory is retained when ESPN Q evidence is
    missing, but NO quarter forecast or quarter-winning percentage is exposed.
    """
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
    evidence = quarter_evidence if isinstance(quarter_evidence, dict) else {}
    def valid_profile(key):
        raw = evidence.get(key)
        if not isinstance(raw, (list, tuple)) or len(raw) != 4:
            return None
        try:
            vec = np.asarray(raw, dtype=float)
        except (ValueError, TypeError):
            return None
        if (not np.isfinite(vec).all() or np.any(vec < .08)
                or np.any(vec > .45) or abs(float(vec.sum()) - 1.0) > .001):
            return None
        return vec / vec.sum()

    aw_profile = valid_profile("away")
    ho_profile = valid_profile("home")
    observed = (evidence.get("available") is True
                and evidence.get("method") == "espn_regulation_quarters_v1"
                and isinstance(evidence.get("away_sample"), int)
                and isinstance(evidence.get("home_sample"), int)
                and evidence["away_sample"] >= 6
                and evidence["home_sample"] >= 6
                and aw_profile is not None and ho_profile is not None)
    if observed:
        # Data-driven Q shares for each team. Common random pace creates
        # correlated high/low-scoring quarters; team-specific Q shape comes
        # only from observed offense/defense/venue, NOT a 25%-per-Q prior.
        shared = rng.dirichlet((aw_profile + ho_profile) * 32, size=5000)
        aw_q = rng.dirichlet(aw_profile * 90, size=5000)
        ho_q = rng.dirichlet(ho_profile * 90, size=5000)
        aw_q = .35 * shared + .65 * aw_q
        ho_q = .35 * shared + .65 * ho_q
        # No 6-minute evidence: the two halves within each real-data-backed
        # quarter are still transparently neutral illustrative allocations.
        halves = rng.beta(18.0, 18.0, size=(5000, 4))
        aw_weights = np.empty((5000, 8), dtype=float)
        ho_weights = np.empty((5000, 8), dtype=float)
        aw_weights[:, ::2] = aw_q * halves
        aw_weights[:, 1::2] = aw_q * (1.0 - halves)
        ho_weights[:, ::2] = ho_q * halves
        ho_weights[:, 1::2] = ho_q * (1.0 - halves)
    else:
        # Never claim this neutral pattern predicts Q1–Q4 points.
        weights = rng.dirichlet(np.full(8, 20.0), size=5000)
        aw_weights = ho_weights = weights
    away = _allocate(a.astype(np.int32), aw_weights, rng)
    home = _allocate(h.astype(np.int32), ho_weights, rng)
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
        away_qdraw = np.sum(away[:, q*2:q*2+2], axis=1)
        home_qdraw = np.sum(home[:, q*2:q*2+2], axis=1)
        quarters.append({
            "quarter": q + 1,
            "away_outscores_pct": round(float(np.mean(m < 0))*100, 1)
                                   if observed else None,
            "home_outscores_pct": round(float(np.mean(m > 0))*100, 1)
                                   if observed else None,
            "tie_pct": round(float(np.mean(m == 0))*100, 1) if observed else None,
            "away_mean": round(float(np.mean(away_qdraw)), 2) if observed else None,
            "home_mean": round(float(np.mean(home_qdraw)), 2) if observed else None,
            "away_p10": round(float(np.percentile(away_qdraw, 10)), 1)
                         if observed else None,
            "away_p90": round(float(np.percentile(away_qdraw, 90)), 1)
                         if observed else None,
            "home_p10": round(float(np.percentile(home_qdraw, 10)), 1)
                         if observed else None,
            "home_p90": round(float(np.percentile(home_qdraw, 90)), 1)
                         if observed else None,
        })
    # One demonstrative path selected deterministically from these same 5k
    # final results, closest to the mean final spread. NEVER call it the mean.
    # _allocate currently has eight windows; split each of those into 3-min
    # portions without changing their summed quarter/6-min allocations.
    fractions = rng.beta(9.0, 9.0, size=(5000, 8))
    part_a = rng.binomial(away, fractions)
    part_h = rng.binomial(home, fractions)
    three_a = np.stack((part_a, away-part_a), axis=2).reshape(5000, 16)
    three_h = np.stack((part_h, home-part_h), axis=2).reshape(5000, 16)
    path_index = int(np.argmin(np.abs((h-a) - np.mean(h-a))))
    path_margin = np.r_[0, np.cumsum(three_a[path_index]-three_h[path_index])]
    sample_path = [
        {"minute": i*3, "away_minus_home": int(v)}
        for i, v in enumerate(path_margin)
    ]
    run_proxy = _neutral_run_proxy(a.astype(np.int32), h.astype(np.int32), rng)
    # Neutral scoring volatility is based on real allocated model draws;
    # it cannot be equated with verified NBA pace/possessions.
    six_min_totals = away + home
    scoring_window_sd = float(np.mean(np.std(six_min_totals, axis=1)))
    clutch = delta[:, 7]
    spread = h - a
    return {
        "available": True, "method": ("conditional_espn_quarters_v1"
                                        if observed else "conditional_neutral_6min_v1"),
        "n_sims": 5000,
        "source": ((str(evidence.get("description") or "")+
                    " Pozostałe sześciominutowe przebiegi są hipotetyczne; "+
                    "nie są to rzeczywiste NBA play-by-play.")
                   if observed else METHOD),
        "timeline": timeline, "quarters": quarters,
        "quarter_model": {
            "available": bool(observed),
            "method": "espn_regulation_quarters_v1" if observed else "unavailable",
            "source": str(evidence.get("source") or "ESPN")[:125],
            "away_sample": evidence.get("away_sample", 0),
            "home_sample": evidence.get("home_sample", 0),
            "basis": (str(evidence.get("description") or "")[:550] if observed
                      else str(evidence.get("reason") or
                      "Brak historycznych wyników kwart; nie pokazujemy sztucznych Q1–Q4.")[:250]),
        },
        "sample_path": sample_path,
        "sample_path_source": "Pojedynczy przykładowy przebieg losowy z tej samej "
                              "próby 5 000 wyników. Nie jest średnią prognozą "
                              "ani rzeczywistą chronologią punktów.",
        "run_proxy": run_proxy,
        "neutral_scoring_window_sd": round(scoring_window_sd, 1),
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
