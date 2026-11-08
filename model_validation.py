"""Chronological holdout to compare opponent-aware candidate with shipped model.

Do not re-use holdout for hyperparameter selection. Only consider a model for
production after repeated independent, pregame, out-of-time validation.
"""
from __future__ import annotations
from math import erf, sqrt
import pandas as pd

from simulation_engine import completed_team_scores, legacy_matchup_means, matchup_means
from opponent_ratings import regularized_matchup_means


def score_model(model, actual_home, actual_away):
    """Comparable expected-score metrics without Monte Carlo sampling noise."""
    home=float(model['home'])
    away=float(model['away'])
    # Approximate P(home win) under legacy team's independent noise SD=11.
    # Shared pace noise cancels in the margin; result not calibrated.
    p=.5*(1+erf((home-away)/(22.)))
    result=1 if actual_home>actual_away else 0
    return {
        'total_error':abs(home+away-actual_home-actual_away),
        'team_error':(abs(home-actual_home)+abs(away-actual_away))/2,
        'winner_hit':int((home>=away)==(actual_home>actual_away)),
        'brier':(p-result)**2
    }


def evaluate_models(completed, holdout_n=40):
    cols={'game_id','start_utc','home','away','home_score','away_score','status_code'}
    if completed is None or completed.empty or not cols.issubset(completed.columns):
        return pd.DataFrame(),{}
    g=completed.copy()
    g['start_utc']=pd.to_datetime(g['start_utc'],utc=True,errors='coerce')
    g=g[(g['status_code']==3)&g['start_utc'].notna()].copy()
    g=g.drop_duplicates('game_id').sort_values(['start_utc','game_id'])
    # Use a final held-out time block; no fitting on data from the target event.
    dates=g['start_utc'].drop_duplicates().sort_values()
    if len(g)<80 or len(dates)<30:
        return pd.DataFrame(),{}
    # Hold out the latest N games, not a fixed number of calendar days:
    # some dates have one NBA game and others a full slate.
    evaluation=g.tail(max(1,int(holdout_n))).copy()
    out=[]
    for event in evaluation.to_dict('records'):
        stamp=event['start_utc']
        prior=g[g['start_utc']<stamp]
        hist=completed_team_scores(prior)
        candidates={
            'legacy':legacy_matchup_means(event['home'],event['away'],{},hist),
            'recency':matchup_means(event['home'],event['away'],{},hist),
            'opponent_ridge':regularized_matchup_means(
                event['home'],event['away'],prior,stamp)
        }
        if any(v is None for v in candidates.values()):
            continue
        h,a=float(event['home_score']),float(event['away_score'])
        for name,model in candidates.items():
            metrics=score_model(model,h,a)
            out.append({'game_id':str(event['game_id']),'start_utc':stamp,
                        'model':name,**metrics})
    frame=pd.DataFrame(out)
    if frame.empty:
        return frame,{}
    summary={}
    for name,grp in frame.groupby('model'):
        summary[name]={
            'games':len(grp),
            'total_mae':round(float(grp['total_error'].mean()),2),
            'team_mae':round(float(grp['team_error'].mean()),2),
            'winner_accuracy':round(float(grp['winner_hit'].mean()),4),
            'brier':round(float(grp['brier'].mean()),4),
        }
    return frame,summary
