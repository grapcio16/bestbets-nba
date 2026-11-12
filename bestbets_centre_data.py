"""Verified, conservative public NBA data for the free BestBets Centrum page.

No hard-coded scores, fixtures, injury statuses, simulated win probabilities,
market prices or betting recommendations. This module does NOT change Props.
"""
from __future__ import annotations

from datetime import datetime
from math import isfinite
from zoneinfo import ZoneInfo

import pandas as pd


def _as_score(value):
    try:
        if value is None or pd.isna(value):
            return None
        n=float(value)
        return int(n) if isfinite(n) and n.is_integer() and n >= 0 else None
    except (TypeError, ValueError, OverflowError):
        return None


def _safe_code(code):
    code=str(code or "").strip().upper()
    return code if len(code)==3 and code.isalpha() else "NBA"


def build_centre_snapshot(schedule_df, meta=None, now=None, logo_provider=None):
    """Format actual ESPN/NBA games; never turn unavailable data into fake numbers."""
    now=(now if now is not None else pd.Timestamp.now(tz="Europe/Warsaw"))
    now=pd.Timestamp(now)
    if now.tzinfo is None:
        now=now.tz_localize("Europe/Warsaw")
    else:
        now=now.tz_convert("Europe/Warsaw")
    meta=meta or {}
    empty={"as_of":now.strftime("%Y-%m-%d %H:%M %Z"),"source":str(meta.get("source") or "NBA / ESPN")[:90],
           "day_label":"Dziś","games":[],"ticker":[],"finals":[],"form":[],"error":""}
    if schedule_df is None or schedule_df.empty:
        empty["error"]="Brak dostępnego terminarza."
        return empty
    games=[]
    logos={}
    def get_logo(code):
        if code not in logos:
            try:logos[code]=logo_provider(code) if logo_provider else ""
            except (OSError,KeyError,ValueError):logos[code]=""
        return logos[code]
    for _,r in schedule_df.iterrows():
        start=pd.to_datetime(r.get("start_utc"),utc=True,errors="coerce")
        if pd.isna(start):
            continue
        start_local=start.tz_convert("Europe/Warsaw")
        away=_safe_code(r.get("away"));home=_safe_code(r.get("home"))
        try:status_code=int(r.get("status_code") or 1)
        except (ValueError,TypeError):status_code=1
        state="live" if status_code==2 else "final" if status_code==3 else "scheduled"
        game={
          "id":str(r.get("game_id") or "")[:28],
          "start":start.isoformat(),"day":start_local.date().isoformat(),
          "away":away,"home":home,"away_logo":get_logo(away),"home_logo":get_logo(home),
          "away_score":_as_score(r.get("away_score")),
          "home_score":_as_score(r.get("home_score")),
          "state":state,"status":str(r.get("status") or "")[:35],
        }
        games.append(game)
    games.sort(key=lambda g:g["start"])
    today=now.date().isoformat()
    current=[g for g in games if g["day"]==today]
    upcoming=[g for g in games if g["state"]=="scheduled" and g["start"]>=now.tz_convert("UTC").isoformat()]
    live=[g for g in games if g["state"]=="live"]
    finals=[g for g in games if g["state"]=="final"
            and g["away_score"] is not None and g["home_score"] is not None]
    # If games are not scheduled today, show the nearest real future date,
    # explicitly labeled as such, not "today".
    day_label="Dziś"
    if not current and upcoming:
        day=upcoming[0]["day"]
        current=[g for g in upcoming if g["day"]==day]
        day_label="Najbliższe: "+day
    ticker=(live+upcoming)[:5]
    if not ticker:ticker=sorted(finals,key=lambda g:g["start"],reverse=True)[:5]
    final_recent=sorted(finals,key=lambda g:g["start"],reverse=True)
    # Only the known/visible schedule subset; do not claim complete L10.
    forms={}
    for g in final_recent[:45]:
        if g["away_score"]==g["home_score"]:continue
        for side,other in (("home","away"),("away","home")):
            code=g[side]
            if code=="NBA":continue
            entry=forms.setdefault(code,{"team":code,"logo":get_logo(code),"wins":0,"losses":0,"sample":0})
            if entry["sample"]>=10:continue
            entry["sample"]+=1
            if g[side+"_score"]>g[other+"_score"]:entry["wins"]+=1
            else:entry["losses"]+=1
    form=sorted(forms.values(),key=lambda x:(-x["sample"],x["team"]))[:2]
    empty.update({"day_label":day_label,"games":current[:10],"ticker":ticker[:5],
                  "finals":final_recent[:2],"form":form})
    if bool(meta.get("stale")):
        empty["error"]="Źródło oznaczyło terminarz jako nieaktualny."
    return empty


def load_centre_snapshot():
    from sources import schedule
    from team_logos import logo_data_uri
    try:
        data,meta=schedule(refresh=False)
        return build_centre_snapshot(data,meta,logo_provider=logo_data_uri)
    except Exception:
        # No raw exception/URLs/secret-containing details shown to visitors.
        return build_centre_snapshot(pd.DataFrame(), {"source":"NBA / ESPN"})
