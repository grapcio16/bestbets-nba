"""Opponent-aware, shrinkage-regularized NBA score candidate.

Research only. Fit each matchup strictly on completed games before the target
tipoff. No bookmaker prices, injuries, future scores or claimed calibration.
"""
from __future__ import annotations
import numpy as np
import pandas as pd

from simulation_engine import TEAM_IDS


def regularized_matchup_means(home, away, historical_games, cutoff_utc,
                             prior_games=8., half_life_days=45.):
    """Estimate team offense/defense with ridge and recency weighting.

    A completed NBA game produces two observations:
      home points = league avg + attack(home) + defense(away) + 1.5
      away points = league avg + attack(away) + defense(home) - 1.5
    The offense and defense are shrunk toward 0, avoiding wild early-season
    assumptions. Opponent effects are learned only from prior completed games.
    """
    if historical_games is None or historical_games.empty:
        return None
    required={'home','away','home_score','away_score','status_code','start_utc'}
    if not required.issubset(historical_games.columns):
        return None
    cutoff=pd.to_datetime(cutoff_utc,utc=True,errors='coerce')
    if pd.isna(cutoff):
        return None
    past=historical_games.copy()
    past['start_utc']=pd.to_datetime(past['start_utc'],utc=True,errors='coerce')
    past=past[(past['status_code']==3)&(past['start_utc']<cutoff)]
    past=past[past['home'].isin(TEAM_IDS)&past['away'].isin(TEAM_IDS)]
    for col in ('home_score','away_score'):
        past[col]=pd.to_numeric(past[col],errors='coerce')
    past=past[past['home_score'].between(55,200)&past['away_score'].between(55,200)]
    past=past.dropna(subset=['start_utc','home_score','away_score'])
    if past.empty:
        return None
    # Ensure enough prior games for BOTH teams, not just league-wide data.
    counts=(past['home'].value_counts().add(
            past['away'].value_counts(),fill_value=0))
    if counts.get(home,0)<4 or counts.get(away,0)<4:
        return None
    codes=list(TEAM_IDS)
    idx={team:i for i,team in enumerate(codes)}
    m=len(codes)
    X=np.zeros((len(past)*2,2*m),dtype=float)
    y=np.zeros(2*len(past),dtype=float)
    age=np.zeros(2*len(past),dtype=float)
    league_avg=float(pd.concat([past['home_score'],past['away_score']]).mean())
    for i,rec in enumerate(past.itertuples(index=False)):
        h=idx[rec.home];a=idx[rec.away]
        # +1 coefficient in opponent defense means more points allowed.
        X[2*i,h]=1;X[2*i,m+a]=1
        X[2*i+1,a]=1;X[2*i+1,m+h]=1
        y[2*i]=rec.home_score-league_avg-1.5
        y[2*i+1]=rec.away_score-league_avg+1.5
        age[2*i:2*i+2]=max(0.,(cutoff-rec.start_utc).total_seconds()/86400)
    weights=2.0**(-age/float(half_life_days))
    # prior_games=8 means ~8 neutral pseudo games per coefficient.
    reg=float(prior_games)*np.eye(2*m)
    lhs=X.T@(weights[:,None]*X)+reg
    rhs=X.T@(weights*y)
    beta=np.linalg.solve(lhs,rhs)
    # Cap any remaining low-sample extremes without handpicking team favorites.
    beta=np.clip(beta,-18,18)
    mu_home=league_avg+float(beta[idx[home]])+float(beta[m+idx[away]])+1.5
    mu_away=league_avg+float(beta[idx[away]])+float(beta[m+idx[home]])-1.5
    if not 65<mu_home<165 or not 65<mu_away<165:
        return None
    return {
        'home':mu_home,'away':mu_away,
        'source':'NBA ESPN • opponent-adjusted ridge (badawczy)',
        'samples':(int(counts[home]),int(counts[away])),
        'warning':'Badawczy model ataku/obrony z regresją do średniej, '
                  'bez uwzględnienia potwierdzonych kontuzji. '
                  'Szanse zwycięstwa pozostają niekalibrowane.',
        'league_mean':league_avg,
    }
