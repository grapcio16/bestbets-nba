"""Real schedule-based NBA rest and recent-form context.

The NBA schedule uses North American local dates; America/New_York provides a
consistent league date boundary, not a team's exact travel location. Context is
descriptive, not a model multiplier until walk-forward calibration succeeds.
"""
from __future__ import annotations
import pandas as pd

REQUIRED={"start_utc","home","away","home_score","away_score","status_code"}


def team_schedule_context(history,team,start_utc):
    if history is None or history.empty or not REQUIRED.issubset(history.columns):
        return {"available":False,"reason":"Brak pełnego terminarza"}
    target=pd.to_datetime(start_utc,utc=True,errors="coerce")
    if pd.isna(target):
        return {"available":False,"reason":"Brak daty meczu"}
    x=history.copy()
    x["start_utc"]=pd.to_datetime(x["start_utc"],utc=True,errors="coerce")
    x=x[(x["status_code"]==3)&x["start_utc"].notna()&
        (x["start_utc"]<target)&
        ((x["home"]==team)|(x["away"]==team))].sort_values("start_utc")
    if x.empty:
        return {"available":False,"reason":"Brak wcześniejszych meczów"}
    dates=x["start_utc"].dt.tz_convert("America/New_York").dt.date
    today=target.tz_convert("America/New_York").date()
    previous=dates.iloc[-1]
    days_between=(today-previous).days
    # Zero scheduled days off between calendar dates. Prevent negative values.
    rest=max(0,days_between-1)
    last5=x.tail(5)
    wins=0;differentials=[]
    for g in last5.to_dict("records"):
        home=g["home"]==team
        try:
            mine=float(g["home_score"] if home else g["away_score"])
            other=float(g["away_score"] if home else g["home_score"])
        except (ValueError,TypeError):
            continue
        if 55<=min(mine,other)<=200 and max(mine,other)<=200:
            wins+=int(mine>other)
            differentials.append(mine-other)
    if not differentials:
        return {"available":False,"reason":"Niepełne wyniki"}
    recent_dates=[d for d in dates.tolist() if 0<(today-d).days<=3]
    return {
        "available":True,
        "team":team,
        "last_game":previous.isoformat(),
        "rest_days":rest,
        "back_to_back":rest==0,
        "games_in_4_days":len(recent_dates)+1,
        "wins_last5":wins,
        "played_last5":len(differentials),
        "margin_last5":round(sum(differentials)/len(differentials),1),
        "source":"ESPN — zakończone mecze, daty NBA ET",
    }


def matchup_schedule_context(history,game):
    return {
        "away":team_schedule_context(history,str(game["away"]),game["start_utc"]),
        "home":team_schedule_context(history,str(game["home"]),game["start_utc"]),
    }
