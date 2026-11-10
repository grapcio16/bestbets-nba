"""Verified NBA match-to-team form summaries for MVP pages.

No synthesized basketball results: each record is from an ESPN final that
predates cutoff and has two plausible real scores. These functions are pure,
quick, and can be unit tested independently from Streamlit.
"""
from __future__ import annotations

import math
import pandas as pd
from teams import TEAM_FULL


NEEDED = {"start_utc","home","away","status_code","home_score","away_score"}


def confirmed_finals(source, cutoff_utc):
    if not isinstance(source,pd.DataFrame) or not NEEDED.issubset(source.columns):
        return pd.DataFrame(columns=list(NEEDED)+["game_id"])
    rows=source.copy()
    rows["start_utc"]=pd.to_datetime(rows["start_utc"],utc=True,errors="coerce")
    for col in ("status_code","home_score","away_score"):
        rows[col]=pd.to_numeric(rows[col],errors="coerce")
    cutoff=pd.to_datetime(cutoff_utc,utc=True,errors="coerce")
    if pd.isna(cutoff):
        return rows.iloc[0:0]
    rows=rows[
        (rows["status_code"]==3) &
        (rows["start_utc"]<cutoff) &
        (rows["home_score"].between(55,200)) &
        (rows["away_score"].between(55,200)) &
        rows["home"].isin(TEAM_FULL) &
        rows["away"].isin(TEAM_FULL) &
        (rows["home"]!=rows["away"])
    ].copy()
    if "game_id" in rows:
        rows=rows.drop_duplicates("game_id",keep="last")
    return rows.sort_values("start_utc")


def team_games(finals,code):
    """One row per verified team final: scored, conceded, margin, result."""
    if finals is None or finals.empty or code not in TEAM_FULL:
        return pd.DataFrame(columns=["game_id","start_utc","opponent",
                                    "scored","allowed","margin","win","venue"])
    games=finals[(finals["home"]==code)|(finals["away"]==code)].copy()
    if games.empty:
        return pd.DataFrame(columns=["game_id","start_utc","opponent",
                                    "scored","allowed","margin","win","venue"])
    is_home=games["home"]==code
    games["opponent"]=games["away"].where(is_home,games["home"])
    games["scored"]=games["home_score"].where(is_home,games["away_score"])
    games["allowed"]=games["away_score"].where(is_home,games["home_score"])
    games["margin"]=games["scored"]-games["allowed"]
    games["win"]=games["margin"]>0
    games["venue"]=is_home.map({True:"HOME",False:"AWAY"})
    return games[["game_id","start_utc","opponent","scored",
                  "allowed","margin","win","venue"]].sort_values("start_utc")


def team_summary(finals,team,lookback=10):
    games=team_games(finals,team)
    if games.empty:
        return {
            "code":team,"name":TEAM_FULL.get(team,team),"gp":0,
            "wins":0,"losses":0,"win_pct":None,
            "scored":None,"allowed":None,"margin":None,
            "last5":None,"last10":None,"home_avg":None,"away_avg":None,
        }
    recent=games.tail(max(1,int(lookback)))
    home=games[games["venue"]=="HOME"]
    away=games[games["venue"]=="AWAY"]
    return {
        "code":team,"name":TEAM_FULL.get(team,team),
        "gp":len(games),"wins":int(games["win"].sum()),
        "losses":int((~games["win"]).sum()),
        "win_pct":float(games["win"].mean()*100),
        "scored":float(games["scored"].mean()),
        "allowed":float(games["allowed"].mean()),
        "margin":float(games["margin"].mean()),
        "last5":float(games.tail(5)["win"].mean()*100),
        "last10":float(recent["win"].mean()*100),
        "home_avg":float(home["scored"].mean()) if len(home) else None,
        "away_avg":float(away["scored"].mean()) if len(away) else None,
    }


def league_table(finals,minimum_games=5):
    records=[team_summary(finals,code) for code in sorted(TEAM_FULL)]
    df=pd.DataFrame(records)
    if minimum_games:
        df=df[df["gp"]>=int(minimum_games)]
    if df.empty:return df
    return df.sort_values(["last5","margin","gp"],ascending=False).reset_index(drop=True)


def safe_value(value,decimals=1,suffix=""):
    try:
        x=float(value)
        return f"{x:.{decimals}f}{suffix}" if math.isfinite(x) else "—"
    except (TypeError,ValueError):
        return "—"
