"""Pregame quarter profiles from ACTUAL, completed ESPN Q1–Q4 line scores.

No score is created by dividing a predicted full-game total into quarters.
Only real four-quarter finals strictly before the selected tipoff enter the
profile. The existing main Monte Carlo result remains authoritative; these
observed profiles shape CONDITIONAL allocations of its final-score draws.

This is an experimental historical conditional model, not a separately
backtested or calibrated forecast of quarter betting lines.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

QCOLS = tuple(f"{side}_q{q}" for side in ("home", "away") for q in range(1, 5))
MIN_GAMES = 6
LAST_GAMES = 15


def _profile(rows: pd.DataFrame, team: str, *, allowed=False, venue=None):
    """Recent real per-quarter points: offense or conceded points."""
    related = rows[(rows["home"] == team) | (rows["away"] == team)]
    if venue == "home":
        related = related[related["home"] == team]
    elif venue == "away":
        related = related[related["away"] == team]
    related = related.sort_values("start_utc").tail(LAST_GAMES)
    if related.empty:
        return None, 0
    vectors = []
    for _, game in related.iterrows():
        side = "home" if game["home"] == team else "away"
        if allowed:
            side = "away" if side == "home" else "home"
        vectors.append([float(game[f"{side}_q{q}"]) for q in range(1, 5)])
    scores = np.asarray(vectors, dtype=float)
    # Each historical event remains a complete box score; avoid weighting
    # a single blowout/OT as more events. Modest recency reflects team form.
    recency = np.linspace(.75, 1.25, len(scores))
    average = np.average(scores, weights=recency, axis=0)
    total = float(np.sum(average))
    if not (np.all(np.isfinite(average)) and total > 0):
        return None, len(related)
    return (average / total), len(related)


def pregame_quarter_evidence(history: pd.DataFrame, game: dict) -> dict:
    """Return JSON-safe matchup-specific Q shares, or unavailable with reason.

    For a team Q1 share, blend its historical Q1 scoring distribution with
    the opponent's historical Q1 conceded distribution. A small, optional
    same-venue adjustment is supported only with at least 4 observations.
    Shrink all signals toward OBSERVED season league quarter shapes.
    No future fixture may be used even when history comes from today's cache.
    """
    from simulation_data_audit import verified_history

    invalid = lambda reason, a=0, h=0: {
        "available": False, "method": "espn_regulation_quarters_v1",
        "reason": reason, "away_sample": a, "home_sample": h,
        "source": "ESPN · wyłącznie potwierdzone kwarty zakończonych meczów"
    }
    if history is None or history.empty or not set(QCOLS).issubset(history.columns):
        return invalid("Brak kompletnych historycznych wyników Q1–Q4 ESPN.")
    earlier = verified_history(history, game.get("start_utc"))
    if earlier.empty:
        return invalid("Brak historycznych spotkań przed rozpoczęciem tego meczu.")
    for col in QCOLS:
        earlier[col] = pd.to_numeric(earlier[col], errors="coerce")
    complete = earlier[list(QCOLS)].notna().all(axis=1)
    for side in ("home", "away"):
        summed = earlier[[f"{side}_q{q}" for q in range(1,5)]].sum(axis=1)
        complete &= (summed == earlier[f"{side}_score"])
        complete &= earlier[[f"{side}_q{q}" for q in range(1,5)]].ge(0).all(axis=1)
        complete &= earlier[[f"{side}_q{q}" for q in range(1,5)]].le(75).all(axis=1)
    earlier = earlier[complete].drop_duplicates(subset=["game_id"]).copy()
    if earlier.empty:
        return invalid("ESPN nie dostarczył czterech zweryfikowanych kwart regulaminowych.")

    away, home = str(game.get("away") or ""), str(game.get("home") or "")
    if not away or not home or away == home:
        return invalid("Nieprawidłowy skład spotkania.")
    a_off,n_a = _profile(earlier, away)
    h_off,n_h = _profile(earlier, home)
    if n_a < MIN_GAMES or n_h < MIN_GAMES or a_off is None or h_off is None:
        return invalid(
            f"Za mało potwierdzonych kwart ESPN: {away} {n_a}/{MIN_GAMES}, "
            f"{home} {n_h}/{MIN_GAMES}.", n_a, n_h
        )

    home_allow,n_ha = _profile(earlier, home, allowed=True)
    away_allow,n_aa = _profile(earlier, away, allowed=True)
    # League prior is also observed, not the arbitrary 25%-per-quarter split.
    scored = earlier[[f"{side}_q{q}" for side in ("home","away")
                      for q in range(1,5)]].to_numpy(dtype=float).reshape(-1, 2, 4)
    league_mean = scored.mean(axis=(0,1))
    league = league_mean / league_mean.sum()

    def estimate(off, n, defending, ndef, team, venue):
        mix = off.copy()
        if defending is not None and ndef >= MIN_GAMES:
            mix = .65 * mix + .35 * defending
        vshare, vn = _profile(earlier, team, venue=venue)
        if vshare is not None and vn >= 4:
            mix = .85 * mix + .15 * vshare
        # Short season samples are shrunken to the league's OBSERVED
        # quarter shape; the shrinkage does not manufacture additional wins.
        reliability = n / (n + 8.0)
        mix = reliability * mix + (1 - reliability) * league
        mix = np.clip(mix, .10, .40)
        return (mix / mix.sum()).tolist(), vn

    a_share, n_venue_a = estimate(a_off, n_a, home_allow, n_ha, away, "away")
    h_share, n_venue_h = estimate(h_off, n_h, away_allow, n_aa, home, "home")
    return {
        "available": True,
        "method": "espn_regulation_quarters_v1",
        "source": "ESPN · rzeczywiste Q1–Q4 wyłącznie przed tip-off",
        "away": [round(float(v), 7) for v in a_share],
        "home": [round(float(v), 7) for v in h_share],
        "away_sample": int(n_a), "home_sample": int(n_h),
        "away_venue_sample": int(n_venue_a),
        "home_venue_sample": int(n_venue_h),
        "league_games": int(len(earlier)),
        "description": (
            "Warunkowa prognoza podziału punktów: historyczne kwartalne punkty "
            "zdobywane przez drużynę, dopuszczane przez rywala, split dom/wyjazd "
            "i skurcz do rzeczywistego profilu kwart ligi. "
            "Rozkład jest dopasowany do 5 000 końcowych wyników modelu, "
            "nie jest osobno skalibrowaną prognozą kwart."
        ),
    }
