"""Walk-forward comparison against old mean-only NBA team-score baseline.

Each event is forecast using only games dated STRICTLY before its tipoff.
Evaluation is descriptive and should not be used as betting recommendations.
"""
from __future__ import annotations

import pandas as pd
from simulation_engine import completed_team_scores, matchup_means, simulate_game


def old_baseline(home,away,history):
    hs=sorted(history.get(home,[]),key=lambda x:x[0])[-12:]
    ass=sorted(history.get(away,[]),key=lambda x:x[0])[-12:]
    if len(hs)<4 or len(ass)<4:
        return None
    hf=sum(r[1] for r in hs)/len(hs)
    ha=sum(r[2] for r in hs)/len(hs)
    af=sum(r[1] for r in ass)/len(ass)
    aa=sum(r[2] for r in ass)/len(ass)
    return {"home":(hf+aa)/2+1.5,"away":(af+ha)/2-1.5,
            "source":"baseline","warning":""}


def walk_forward_comparison(completed: pd.DataFrame, max_games=140):
    required={"game_id","start_utc","home","away","home_score","away_score","status_code"}
    if completed is None or completed.empty or not required.issubset(completed.columns):
        return pd.DataFrame(),{}
    past=completed.copy()
    past["start_utc"]=pd.to_datetime(past["start_utc"],utc=True,errors="coerce")
    past=past[(past["status_code"]==3)&past["start_utc"].notna()].sort_values("start_utc")
    rows=[]
    for g in past.to_dict("records"):
        if len(rows)>=max_games:
            break
        stamp=g["start_utc"]
        before=past[past["start_utc"]<stamp]
        history=completed_team_scores(before)
        old=old_baseline(g["home"],g["away"],history)
        new=matchup_means(g["home"],g["away"],{},history)
        if old is None or new is None:
            continue
        try:
            true_home,true_away=float(g["home_score"]),float(g["away_score"])
            if min(true_home,true_away)<55 or max(true_home,true_away)>200:
                continue
            game={"game_id":str(g["game_id"]), "home":g["home"],
                  "away":g["away"],"start_utc":stamp}
            old_sim,*_=simulate_game(game,old)
            new_sim,*_=simulate_game(game,new)
            record={"game_id":str(g["game_id"]),"date":stamp,
                    "actual_total":true_home+true_away,
                    "actual_home":true_home,"actual_away":true_away}
            for prefix,sim in (("old",old_sim),("new",new_sim)):
                record[prefix+"_total"]=sim["total_points"]
                record[prefix+"_home"]=sim["home_points"]
                record[prefix+"_away"]=sim["away_points"]
                record[prefix+"_p_home"]=sim["home_win_pct"]/100
                record[prefix+"_winner_hit"]=(
                    (sim["home_win_pct"]>=50)==(true_home>true_away))
                record[prefix+"_team_error"]=(
                    abs(true_home-sim["home_points"])
                    +abs(true_away-sim["away_points"]))/2
                record[prefix+"_brier"]=(
                    sim["home_win_pct"]/100-(1 if true_home>true_away else 0))**2
            rows.append(record)
        except (TypeError,ValueError,KeyError):
            continue
    frame=pd.DataFrame(rows)
    if frame.empty:
        return frame,{}
    result={"games":len(frame)}
    for prefix in ("old","new"):
        result[prefix+"_total_mae"]=round(
            float((frame[prefix+"_total"]-frame["actual_total"]).abs().mean()),2)
        result[prefix+"_winner_accuracy"]=round(
            float(frame[prefix+"_winner_hit"].mean()),4)
        result[prefix+"_team_mae"]=round(
            float(frame[prefix+"_team_error"].mean()),2)
        result[prefix+"_brier"]=round(
            float(frame[prefix+"_brier"].mean()),4)
    return frame,result
