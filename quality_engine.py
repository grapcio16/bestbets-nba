"""Transparent, conservative diagnostics for NBA player-prop predictions.

No source calls. The indicators are DATA QUALITY checks, NOT trained confidence
probabilities, not independent calibration, and not betting advice.
"""
from __future__ import annotations
from datetime import datetime, timezone
import math
import numpy as np
import pandas as pd
from core import calc_projection


def _utc(value):
    try:
        timestamp = pd.to_datetime(value, utc=True, errors='coerce')
        return timestamp if pd.notna(timestamp) else None
    except (TypeError, ValueError, OverflowError):
        return None


def walkforward_error(player_logs, market, max_eval=10, min_prior=5):
    """Measure errors on previous completed appearances with strictly past inputs."""
    if player_logs is None or player_logs.empty or market not in player_logs:
        return {'n':0, 'mae':None, 'bias':None, 'mean_actual':None}
    df = player_logs.sort_values('GAME_DATE').reset_index(drop=True)
    errors=[]; actuals=[]
    for i in range(max(min_prior, len(df)-max_eval), len(df)):
        prior=df.iloc[:i]
        target=df.iloc[i]
        if i<min_prior or pd.isna(target.get(market)) or float(target.get('MIN',0))<=2:
            continue
        try:
            prediction=calc_projection(prior,market)['prediction']
        except (ValueError,TypeError,KeyError):
            continue
        actual=float(target[market])
        errors.append(prediction-actual)
        actuals.append(actual)
    if not errors:return {'n':0, 'mae':None, 'bias':None, 'mean_actual':None}
    return {'n':len(errors), 'mae':round(float(np.mean(np.abs(errors))),2),
            'bias':round(float(np.mean(errors)),2),
            'mean_actual':round(float(np.mean(actuals)),2)}


def cautious_probability(raw_p, sample_size, prior_strength=25):
    """Conservative shrinkage towards 50%, explicitly NOT statistical calibration.

    Used for a *stress test* only. Must never be labeled validated probability.
    """
    p=float(raw_p); n=max(0, int(sample_size))
    if not math.isfinite(p) or not 0<=p<=1:raise ValueError('Prob must be between 0 and 1')
    return 0.5+(p-0.5)*(n/(n+prior_strength))


def quality_check(logs, market, status='', updated='', starts='', now=None, diag=None):
    """Quality tier and flags. Does not claim future predictive certainty.

    'WERYFIKUJ' means relatively better diagnostics among available data, not
    a recommendation, calibrated edge, or verified profitability.
    """
    moment=_utc(now) if now is not None else pd.Timestamp.now(tz='UTC')
    n=len(logs) if logs is not None else 0
    diag=diag if diag is not None else walkforward_error(logs,market)
    flags=[]; blocked=False
    s=str(status).lower().strip()
    if any(x in s for x in ('out','inactive','suspended','injured reserve')):
        flags.append('Zawodnik wykluczony z gry');blocked=True
    elif any(x in s for x in ('questionable','doubtful','day-to-day','day to day','gtd','game-time decision')):
        flags.append('Niepewny występ / status kontuzji')
    elif not s or 'brak wpisu' in s:
        flags.append('Brak potwierdzenia dostępności zawodnika')
    if n<5:
        flags.append('Za mało wcześniejszych meczów');blocked=True
    elif n<15:
        flags.append(f'Mała próba ({n} meczów)')
    if diag['n']<5:
        flags.append('Za mało sprawdzonych prognoz walk-forward')
    elif diag['mae'] is not None:
        avg=abs(float(diag['mean_actual'] or 0))
        if avg>1 and diag['mae']/avg>.4:
            flags.append('Duży wcześniejszy błąd prognoz')
    if n>=6 and 'MIN' in logs:
        minutes=pd.to_numeric(logs.sort_values('GAME_DATE')['MIN'],errors='coerce').dropna()
        if len(minutes)>=6:
            recent=minutes.tail(5)
            if abs(float(recent.mean())-float(minutes.iloc[:-5].tail(10).mean())) > 6:
                flags.append('Wyraźna zmiana liczby minut')
    start=_utc(starts)
    upd=_utc(updated)
    if start is None:
        flags.append('Brak potwierdzonej godziny meczu')
    elif moment is not None and start<=moment:
        flags.append('Mecz już się rozpoczął');blocked=True
    if upd is None:
        flags.append('Brak godziny aktualizacji kursu')
    elif moment is not None:
        age=(moment-upd).total_seconds()/60
        if age>120:
            flags.append('Nieaktualny kurs (>120 min)');blocked=True
        if age< -15:
            flags.append('Nielogiczny czas aktualizacji kursu');blocked=True
    if blocked:level='WSTRZYMAJ';rank=2
    elif flags:level='OSTROŻNIE';rank=1
    else:level='WERYFIKUJ';rank=0
    return {'level':level,'rank':rank,'flags':flags,'diagnostics':diag,
            'timestamp_checked':moment.isoformat() if moment is not None else ''}
