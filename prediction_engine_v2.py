"""BestBets Prediction Engine 2.0 — candidate, NEVER a production replacement.

Pregame-only, reproducible count distributions. Separates playing-time
uncertainty from per-minute player production, uses exponential recency weighting,
retains same-game correlation for PRA and observed shooting attempts for 3PM.

This is a model HYPOTHESIS, NOT probability calibration, bookmaker advantage,
profit estimate or automatically deployable recommendation. Backtest on later
matches before considering it for production.
"""
from __future__ import annotations

from hashlib import sha256
import math

import numpy as np
import pandas as pd

from core import STAT_NAMES, norm_name

MIN_GAMES = 10
LAST_GAMES = 28
N_DRAWS = 2048
FIELDS = {"GAME_DATE", "PLAYER_NAME", "TEAM_ABBREVIATION",
          "MIN", "PTS", "REB", "AST", "FG3M"}


def _pregame_rows(logs, cutoff_utc, market, min_games=MIN_GAMES):
    if market not in STAT_NAMES:
        raise ValueError("Nieobsługiwany rynek zawodnika")
    if logs is None or not isinstance(logs, pd.DataFrame):
        raise ValueError("Brak historii zawodnika")
    if not FIELDS.issubset(logs.columns):
        raise ValueError("Brak pełnych statystyk wymaganych do modelu 2.0")
    cutoff = pd.to_datetime(cutoff_utc, utc=True, errors="coerce")
    if pd.isna(cutoff):
        raise ValueError("Brak prawidłowej daty odniesienia")
    data = logs.copy()
    data["GAME_DATE"] = pd.to_datetime(data["GAME_DATE"], utc=True, errors="coerce")
    data["MIN"] = pd.to_numeric(data["MIN"], errors="coerce")
    for field in ("PTS", "REB", "AST", "FG3M", "FG3A"):
        if field in data:
            data[field] = pd.to_numeric(data[field], errors="coerce")
    data = data[(data["GAME_DATE"] < cutoff) &
                data["GAME_DATE"].notna() &
                data["MIN"].between(3, 48)].copy()
    if data.empty:
        raise ValueError("Brak występów sprzed meczu")
    # Only the most recently represented club. Traded players' old-club
    # production is not automatically interpreted as their new role.
    data = data.sort_values("GAME_DATE")
    team = str(data.iloc[-1]["TEAM_ABBREVIATION"])
    player = str(data.iloc[-1]["PLAYER_NAME"])
    data = data[
        (data["TEAM_ABBREVIATION"].astype(str) == team) &
        (data["PLAYER_NAME"].map(norm_name) == norm_name(player))
    ]
    if "PLAYER_ID" in data and str(data.iloc[-1].get("PLAYER_ID") or "") not in ("", "nan", "None"):
        pid = str(data.iloc[-1]["PLAYER_ID"])
        data = data[data["PLAYER_ID"].astype(str) == pid]
    if "GAME_ID" in data:
        data = data.drop_duplicates(subset=["GAME_ID"], keep="last")
    data = data.sort_values("GAME_DATE").tail(LAST_GAMES).copy()
    required = ("PTS", "REB", "AST") if market == "PRA" else (market,)
    data = data.dropna(subset=list(required))
    if len(data) < min_games:
        raise ValueError(f"Za mało występów aktualnego klubu ({len(data)}/{min_games})")
    if market == "PRA":
        data["VALUE"] = data[["PTS", "REB", "AST"]].sum(axis=1)
    else:
        data["VALUE"] = data[market]
    if (data["VALUE"] < 0).any():
        data = data[data["VALUE"] >= 0]
    if len(data) < min_games:
        raise ValueError("Za mało poprawnych statystyk")
    return data, cutoff, player, team


def forecast_v2(logs, market, line, cutoff_utc, *,
                min_games=MIN_GAMES, draws=N_DRAWS):
    """Return a bounded stochastic distribution with uncalibrated P(over).

    Calls only past completed player logs. No sportsbook line is used to fit
    the distribution; line changes only the exceedance threshold.
    """
    line = float(line)
    if not math.isfinite(line) or line < 0:
        raise ValueError("Niepoprawna linia")
    if not 256 <= int(draws) <= 8192:
        raise ValueError("Liczba losowań poza limitem")
    past, cutoff, name, team = _pregame_rows(logs, cutoff_utc, market, min_games)
    n = len(past)
    observed_mins = past["MIN"].to_numpy(dtype=float)
    ages = np.arange(n - 1, -1, -1, dtype=float)
    weights = np.exp(-ages / 8.)
    weights /= weights.sum()
    recent_m = float(np.mean(observed_mins[-5:]))
    medium_m = float(np.mean(observed_mins[-min(10,n):]))
    long_m = float(np.average(observed_mins, weights=weights))
    mu_minutes = float(np.clip(.55*recent_m + .30*medium_m + .15*long_m, 3, 42))
    minute_sd = max(2.5, float(np.std(observed_mins[-min(10,n):], ddof=1)))
    seed_txt = "|".join([
        "BestBets-v2.0", norm_name(name), team, str(market),
        cutoff.isoformat(), str(past["GAME_DATE"].iloc[-1].isoformat()),
        str(n), f"{float(past['VALUE'].sum()):.2f}",
    ])
    seed = int.from_bytes(sha256(seed_txt.encode("utf-8")).digest()[:8], "big")
    rng = np.random.default_rng(seed)
    indexes = rng.choice(n, size=int(draws), replace=True, p=weights)
    # Time projection independent of shots/minutes from a different season.
    sampled_m = observed_mins[indexes]
    minutes = np.clip(
        rng.normal(mu_minutes + .40 * (sampled_m - long_m),
                   max(1.5, .65*minute_sd), int(draws)),
        3, 48)
    explanation = "ważone stawki produkcji na minutę + rozkład minut + Poisson"
    if (market == "FG3M"
            and "FG3A" in past
            and past["FG3A"].notna().sum() >= max(8, min_games)
            and (past["FG3A"].fillna(0) >= past["FG3M"]).all()):
        attempts = past["FG3A"].to_numpy(dtype=float)
        per_minute_att = attempts / observed_mins
        av = float(np.average(per_minute_att, weights=weights))
        lam = np.maximum(0.0, minutes *
                         (.65*per_minute_att[indexes] + .35*av))
        shot_attempts = np.minimum(rng.poisson(lam), 32)
        recent_count = min(n, 10)
        make = float(past["FG3M"].tail(recent_count).sum())
        attempt = float(past["FG3A"].tail(recent_count).sum())
        # Bayesian smoothing prevents tiny shooting streaks from implying 0/100%.
        alpha = 2.5 + make
        beta = 4.0 + max(0.0, attempt - make)
        shooting_pct = rng.beta(alpha, beta, size=int(draws))
        outcomes = rng.binomial(shot_attempts, shooting_pct).astype(float)
        explanation = "rzuty za trzy: liczba prób na minutę + Beta-Binomial"
    else:
        names = ("PTS", "REB", "AST") if market == "PRA" else (market,)
        outcomes = np.zeros(int(draws), dtype=float)
        for name_stat in names:
            actual = past[name_stat].to_numpy(dtype=float)
            per_minute = np.maximum(0, actual / observed_mins)
            rate = float(np.average(per_minute, weights=weights))
            # Same sampled game index for all PRA components: retains positive
            # or negative within-game rate comovement, unlike independent L10 averages.
            rate_draw = .65*per_minute[indexes] + .35*rate
            lam = np.clip(rate_draw*minutes, 0, 130)
            outcomes += rng.poisson(lam)
        if market == "PRA":
            explanation += " (wspólny indeks meczowy PTS/REB/AST)"
    p_over = float(np.mean(outcomes > line))
    warnings = [
        "Wariant BADAWCZY, prawdopodobieństwa NIEKALIBROWANE.",
        "Brak potwierdzenia statusu przedmeczowego i aktualnych minut.",
    ]
    last = past["GAME_DATE"].iloc[-1]
    days_idle = (cutoff - last).total_seconds()/86400
    if days_idle > 21:
        warnings.append(f"Ostatni mecz tego zawodnika sprzed {days_idle:.0f} dni.")
    if n < 20:
        warnings.append(f"Niewielka próba ({n}) — wysokie ryzyko zmienności.")
    if minute_sd > 7:
        warnings.append(f"Niestabilne minuty (SD={minute_sd:.1f}).")
    return {
        "model": "Prediction Engine 2.0 / BADAWCZY",
        "player":name,"team":team,"market":market,
        "sample":n,"minutes":round(mu_minutes,1),
        "minutes_sd":round(minute_sd,1),
        "mean":round(float(outcomes.mean()),2),
        "p_over":p_over,"p_under":1-p_over,
        "p10":float(np.percentile(outcomes,10)),
        "p90":float(np.percentile(outcomes,90)),
        "last10_hits":int((past["VALUE"].tail(10)>line).sum()),
        "last10_n":min(10,n),
        "method":explanation,"warnings":warnings,
    }
