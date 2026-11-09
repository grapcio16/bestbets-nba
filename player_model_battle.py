"""Fair walk-forward battle: legacy vs Candidate v2 on the SAME NBA outcomes.

Forecast each actual player game using earlier appearances only. A synthetic
line derived from PRIOR game logs permits Brier/accuracy research without
claiming that any historical bookmaker ever offered that line or price.
No tuning on the evaluation period; no odds, no ROI, no staking advice.
"""
from __future__ import annotations

import math
import numpy as np
import pandas as pd

from core import STAT_NAMES, calc_projection, norm_name, prop_probability
from prediction_engine_v2 import forecast_v2

REQUIRED = {"PLAYER_NAME", "TEAM_ABBREVIATION", "GAME_DATE",
            "MIN", "PTS", "REB", "AST", "FG3M"}
FIELDS = [
    "date", "player", "team", "season", "market", "line", "actual",
    "p_legacy", "p_v2", "pred_legacy", "pred_v2", "hit",
]


def _season(date):
    timestamp=pd.Timestamp(date)
    return timestamp.year if timestamp.month>=10 else timestamp.year-1


def _identifiers(logs):
    if "PLAYER_ID" not in logs:
        return logs["PLAYER_NAME"].map(norm_name)
    ids=logs["PLAYER_ID"].fillna("").astype(str)
    return pd.Series(
        [v if v not in ("","None","nan") else norm_name(name)
         for v,name in zip(ids,logs["PLAYER_NAME"])],
        index=logs.index)


def chronological_battle(logs, market="PTS", *, max_cases=300, min_games=10):
    """Chronological, no-lookahead comparisons over multiple independent seasons."""
    if market not in STAT_NAMES:
        raise ValueError("Nieobsługiwany rynek")
    if logs is None or not isinstance(logs,pd.DataFrame) or not REQUIRED.issubset(logs.columns):
        return pd.DataFrame(columns=FIELDS),{}
    src=logs.copy()
    src["GAME_DATE"]=pd.to_datetime(src["GAME_DATE"],errors="coerce",utc=True)
    for k in ("PTS","REB","AST","FG3M","MIN","FG3A"):
        if k in src:
            src[k]=pd.to_numeric(src[k],errors="coerce")
    if "PRA" not in src:
        src["PRA"]=src[["PTS","REB","AST"]].sum(axis=1,min_count=3)
    src=src[src["GAME_DATE"].notna() &
            src["MIN"].between(3,48) &
            src[market].notna() &
            (src[market]>=0)].copy()
    if src.empty:
        return pd.DataFrame(columns=FIELDS),{}
    src["season_key"]=src["GAME_DATE"].map(_season)
    src["id_key"]=_identifiers(src)
    src=src.sort_values("GAME_DATE")
    if "GAME_ID" in src:
        src=src.drop_duplicates(["id_key","GAME_ID"],keep="last")
    candidates=[]
    groups={}
    for (player,team,year), g in src.groupby(
            ["id_key","TEAM_ABBREVIATION","season_key"],sort=False):
        # Only within-season, same-team roles. Previous seasons provide independent
        # tests, NOT future information or post-trade role substitutions.
        g=g.sort_values("GAME_DATE").reset_index(drop=True)
        key=(player,team,year)
        groups[key]=g
        if len(g)<=min_games:
            continue
        for i in range(min_games,len(g)):
            target=g.iloc[i]
            stamp=target["GAME_DATE"]
            prior=g[g["GAME_DATE"]<stamp]
            if len(prior)<min_games:
                continue
            if (stamp - prior["GAME_DATE"].iloc[-1]).days>30:
                continue
            if not np.isfinite(target[market]):
                continue
            # Store only the row index, NOT a full prior DataFrame per game;
            # the full NBA seasons can contain tens of thousands of outcomes.
            candidates.append((stamp,key,i))
    # Select recent observations FROM EACH season (capped overall). This tests
    # earlier seasons too, without pooling their player roles during training.
    candidates=sorted(candidates,key=lambda x:x[0])
    cap=max(1,min(int(max_cases),1500))
    years=sorted({key[2] for _,key,_ in candidates})
    per_year=max(1,cap//max(1,len(years)))
    chosen=set()
    for year in years:
        options=[i for i,(_,key,_) in enumerate(candidates) if key[2]==year]
        chosen.update(options[-per_year:])
    for i in range(len(candidates)-1,-1,-1):
        if len(chosen)>=cap:break
        chosen.add(i)
    cases=[candidates[i] for i in sorted(chosen,key=lambda j:candidates[j][0])][:cap]
    rows=[]
    for stamp,key,index in cases:
        g=groups[key]
        target=g.iloc[index]
        prior=g[g["GAME_DATE"]<stamp]
        year=key[2]
        line=max(.5,math.floor(float(prior[market].tail(10).mean()))+.5)
        try:
            legacy=calc_projection(prior,market)
            baseline=prop_probability(legacy,line,"OVER")
            other=forecast_v2(prior,market,line,stamp,min_games=min_games,
                              draws=1024)
        except (KeyError,ValueError,TypeError,OverflowError):
            continue
        actual=float(target[market])
        if actual==line:
            continue
        rows.append({
            "date":stamp,"player":str(target["PLAYER_NAME"]),
            "team":str(target["TEAM_ABBREVIATION"]),
            "season":f"{year}-{(year+1)%100:02}",
            "market":market,"line":line,"actual":actual,
            "p_legacy":float(baseline),"p_v2":float(other["p_over"]),
            "pred_legacy":float(legacy["prediction"]),
            "pred_v2":float(other["mean"]),
            "hit":int(actual>line),
        })
    frame=pd.DataFrame(rows,columns=FIELDS)
    if frame.empty:
        return frame,{}
    frame=frame.sort_values(["date","player","team"],kind="stable").reset_index(drop=True)
    split=max(1,int(math.floor(len(frame)*.7)))
    summary={"all":_metrics(frame),
             "later_30pct":_metrics(frame.iloc[split:]),
             "training_or_tuning_performed":False,
             "line_source":"SYMULOWANA z wcześniejszych 10 występów — NIE kurs bukmachera",
             "n_players":int(frame["player"].nunique()),
             "n_seasons":int(frame["season"].nunique())}
    return frame,summary


def _metrics(table):
    if table.empty:
        return {"n":0}
    hit=table["hit"].to_numpy(dtype=float)
    actual=table["actual"].to_numpy(dtype=float)
    m={"n":len(table)}
    for key,pcol,ycol in (("legacy","p_legacy","pred_legacy"),
                          ("v2","p_v2","pred_v2")):
        p=np.clip(table[pcol].to_numpy(dtype=float),.001,.999)
        forecast=table[ycol].to_numpy(dtype=float)
        m[key]={
            "brier":round(float(np.mean((p-hit)**2)),4),
            "logloss":round(float(np.mean(-(hit*np.log(p)+(1-hit)*np.log(1-p)))),4),
            "mae":round(float(np.mean(np.abs(forecast-actual))),2),
            "over_under_accuracy":round(float(np.mean((p>=.5)==(hit>=.5))),4),
            "bias":round(float(np.mean(forecast-actual)),2),
        }
    return m
