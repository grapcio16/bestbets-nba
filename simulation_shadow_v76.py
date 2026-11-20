"""Isolated V7.6 research hypotheses; never change the public simulator.

The shadow model tests two independently measurable ideas:
1. Reduce half of the hard-coded 3-point home-court margin in V7.2--V7.5.
2. Let *observed* recent changes in minutes modestly affect player minutes.

These are hypotheses, not improvements proven by the first 16/4 fixtures.
All inputs must be frozen before the event; no injury or starter status is
inferred from missing ESPN logs.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from core import minutes_projection


SHADOW_TEAM_MODEL_ID = "auto_shadow_home_v76"
SHADOW_PLAYER_MODEL_ID = "auto_player_minutes_v76"
HOME_POINTS_REDUCTION = 0.75


def shadow_home_means(v75_means: dict) -> dict:
    """Keep the total unchanged while testing a smaller home-court prior.

    Both existing versions add +1.5 at home and -1.5 away. Shifting 0.75
    per side reduces this historical *prior* by half, without touching other
    V7.5 context adjustments. The 5,000 draws are then rerun independently.
    """
    if not isinstance(v75_means, dict):
        raise ValueError("Shadow V7.6 wymaga średnich V7.5")
    try:
        home = float(v75_means["home"])
        away = float(v75_means["away"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("Brak obliczonych punktów obu drużyn") from exc
    if not (np.isfinite(home) and np.isfinite(away)):
        raise ValueError("Nieprawidłowe średnie V7.5")
    return {
        **v75_means,
        "home": home - HOME_POINTS_REDUCTION,
        "away": away + HOME_POINTS_REDUCTION,
        "source": str(v75_means.get("source") or "ESPN") + " • V7.6 shadow (parkiet)",
        "warning": "BADAWCZY V7.6: połowa stałej korekty parkietu; "
                   "bez potwierdzonej poprawy i bez wpływu na model publiczny.",
    }


def shadow_minutes_projection(history: pd.DataFrame) -> float:
    """Small, bounded recent-rotation adjustment to the unchanged baseline.

    The existing predictor weighs L5/L10/career. Testing L3 versus L10 is
    deliberately modest, because sudden minutes shifts can be noisy or due
    to game-specific events that cannot be known before tip-off.
    """
    baseline = float(minutes_projection(history))
    if not np.isfinite(baseline):
        raise ValueError("Brak historii minut")
    minutes = pd.to_numeric(
        history.sort_values("GAME_DATE")["MIN"], errors="coerce")
    minutes = minutes[(minutes > 2) & np.isfinite(minutes)]
    if len(minutes) < 6:
        return round(baseline, 1)
    trend = float(minutes.tail(3).mean() - minutes.tail(10).mean())
    correction = float(np.clip(0.4 * trend, -3.0, 3.0))
    return round(float(np.clip(baseline + correction, 0, 42)), 1)


def shadow_roster_minutes(roster: pd.DataFrame, logs: pd.DataFrame,
                          *, captured_at, tipoff) -> pd.DataFrame:
    """Copy roster and change only minute-dependent projections.

    Logs are cut off at the earlier of capture time and tip-off, so adding
    any after-capture boxscore cannot affect an earlier shadow prediction.
    Missing or unusable rows retain the existing V7.4 projection.
    """
    result = roster.copy(deep=True)
    if result.empty or logs is None or logs.empty:
        return result
    cap = pd.to_datetime(captured_at, utc=True, errors="coerce")
    start = pd.to_datetime(tipoff, utc=True, errors="coerce")
    if pd.isna(cap) or pd.isna(start) or cap >= start:
        raise ValueError("V7.6 wymaga poprawnej prognozy przed meczem")
    required = {"PLAYER_NAME", "TEAM_ABBREVIATION", "GAME_DATE", "MIN"}
    if not required.issubset(logs.columns):
        return result
    # A roster can originate from integer-valued test/ESPN tables. Coerce
    # only adjusted numeric columns so fractional projections remain valid.
    for column in ("minutes", "PTS", "REB", "AST", "FG3M"):
        if column in result:
            result[column] = pd.to_numeric(result[column], errors="coerce").astype(float)
    dates = pd.to_datetime(logs["GAME_DATE"], utc=True, errors="coerce")
    prior = logs.loc[dates.lt(cap) & dates.lt(start)].copy()
    for index, row in result.iterrows():
        player = str(row.get("player") or "")
        team = str(row.get("team") or "")
        past = prior[(prior["PLAYER_NAME"] == player) &
                     (prior["TEAM_ABBREVIATION"] == team)]
        if past.empty:
            continue
        try:
            old = float(row["minutes"])
            revised = shadow_minutes_projection(past)
            if not (np.isfinite(old) and old >= 5):
                continue
            ratio = float(np.clip(revised / old, 0.8, 1.2))
            for market in ("PTS", "REB", "AST", "FG3M"):
                current = float(row[market])
                if np.isfinite(current) and current >= 0:
                    result.at[index, market] = current * ratio
            result.at[index, "minutes"] = round(old * ratio, 1)
        except (KeyError, TypeError, ValueError, OverflowError):
            continue
    return result
