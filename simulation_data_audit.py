"""Pregame analytical depth from verified *past* NBA final scores.

No network calls, no fabricated possessions, no injury multipliers. Optional
research-only venue signal must be validated on a later, disjoint game window
before it can influence BestBets' shipped simulator.
"""
from __future__ import annotations
from datetime import timedelta
import numpy as np
import pandas as pd

REQUIRED={"start_utc","away","home","away_score","home_score","status_code"}
MODEL_MIN_VENUE_GAMES=4


def verified_history(completed, cutoff_utc):
    """Unique final events strictly earlier than tipoff. Discard corrupt scores."""
    empty=pd.DataFrame(columns=[
        "game_id","start_utc","away","home","away_score","home_score","status_code"
    ])
    if completed is None or completed.empty or not REQUIRED.issubset(completed.columns):
        return empty
    cutoff=pd.to_datetime(cutoff_utc,utc=True,errors="coerce")
    if pd.isna(cutoff):
        return empty
    df=completed.copy()
    df["start_utc"]=pd.to_datetime(df["start_utc"],utc=True,errors="coerce")
    df["away_score"]=pd.to_numeric(df["away_score"],errors="coerce")
    df["home_score"]=pd.to_numeric(df["home_score"],errors="coerce")
    df["status_code"]=pd.to_numeric(df["status_code"],errors="coerce")
    df=df[(df["status_code"]==3)&df["start_utc"].notna()&
          (df["start_utc"]<cutoff)&
          df["away_score"].between(55,200)&df["home_score"].between(55,200)]
    if "game_id" in df.columns:
        df=df.drop_duplicates("game_id",keep="last")
    return df.sort_values("start_utc").reset_index(drop=True)


def team_snapshot(verified, team, opponent=None, venue="home", window=20):
    """Observed last 5/10/20, opponent, and home/away splits; sample sizes shown."""
    own=verified[(verified["away"]==team)|(verified["home"]==team)].copy()
    if own.empty:
        return {"team":team,"sample":0,"venue_sample":0,"h2h_sample":0,
                "warnings":[f"{team}: brak zweryfikowanych wcześniejszych meczów"]}
    own["is_home"]=own["home"]==team
    own["scored"]=np.where(own["is_home"],own["home_score"],own["away_score"])
    own["allowed"]=np.where(own["is_home"],own["away_score"],own["home_score"])
    own["margin"]=own["scored"]-own["allowed"]
    own=own.tail(window)
    result={"team":team,"sample":len(own),"venue":venue,
            "last_game":own["start_utc"].iloc[-1],
            "warnings":[]}
    for n in (5,10,20):
        subset=own.tail(n)
        result[f"n{n}"]=len(subset)
        result[f"pts{n}"]=round(float(subset["scored"].mean()),1)
        result[f"allowed{n}"]=round(float(subset["allowed"].mean()),1)
        result[f"margin{n}"]=round(float(subset["margin"].mean()),1)
        result[f"total_sd{n}"]=round(float((subset["scored"]+subset["allowed"]).std(ddof=1)),1) if len(subset)>1 else None
    subset=own[own["is_home"] == (venue=="home")]
    result["venue_sample"]=len(subset)
    result["venue_scored"]=round(float(subset["scored"].mean()),1) if len(subset) else None
    result["venue_allowed"]=round(float(subset["allowed"].mean()),1) if len(subset) else None
    other=np.where(own["is_home"],own["away"],own["home"])
    h2h=own[other==opponent] if opponent else own.iloc[0:0]
    result["h2h_sample"]=len(h2h)
    result["h2h_margin"]=round(float(h2h["margin"].mean()),1) if len(h2h) else None
    if len(own)<8:
        result["warnings"].append(f"{team}: tylko {len(own)} spotkań historii")
    if len(subset)<MODEL_MIN_VENUE_GAMES:
        result["warnings"].append(f"{team}: za mało meczów {'u siebie' if venue=='home' else 'na wyjeździe'} ({len(subset)})")
    if 0<len(h2h)<3:
        result["warnings"].append(f"{team}: H2H to tylko {len(h2h)} spotkanie/-a")
    return result


def matchup_audit(completed, game, advanced=None):
    """Compare historical sample depth, rest and advanced metrics at game tipoff."""
    from match_context import matchup_schedule_context
    from simulation_engine import advanced_ratings

    verified=verified_history(completed,game.get("start_utc"))
    home=str(game.get("home") or "")
    away=str(game.get("away") or "")
    h=team_snapshot(verified,home,opponent=away,venue="home")
    a=team_snapshot(verified,away,opponent=home,venue="away")
    context=matchup_schedule_context(verified,game)
    ratings=advanced_ratings(advanced if isinstance(advanced,pd.DataFrame) else pd.DataFrame())
    rows=[]
    for code,side,item in ((away,"away",a),(home,"home",h)):
        rest=context.get(side,{})
        rate=ratings.get(code)
        last=item.get("last_game")
        start=pd.to_datetime(game.get("start_utc"),utc=True,errors="coerce")
        age=round((start-last).total_seconds()/86400,1) if pd.notna(start) and last is not None else None
        rows.append({
            "Drużyna":code,
            "Historia 5":f"{item.get('n5',0)}/5",
            "Historia 10":f"{item.get('n10',0)}/10",
            "Historia 20":f"{item.get('n20',0)}/20",
            "Zdobyte / 10":item.get("pts10"),
            "Stracone / 10":item.get("allowed10"),
            "Różnica / 10":item.get("margin10"),
            "Odch. sumy / 10":item.get("total_sd10"),
            "U siebie / wyjazd":item.get("venue_sample",0),
            "Punkty venue":item.get("venue_scored"),
            "Odpoczynek dni":rest.get("rest_days") if rest.get("available") else None,
            "Back-to-back":rest.get("back_to_back") if rest.get("available") else None,
            "Pace oficjalne":round(float(rate["pace"]),1) if rate else None,
            "OFF Rating":round(float(rate["off"]),1) if rate else None,
            "DEF Rating":round(float(rate["def"]),1) if rate else None,
            "Wiek ostatniej gry (dni)":age,
        })
    flags=list(a.get("warnings",[]))+list(h.get("warnings",[]))
    if not ratings:
        flags.append("Brak aktualnych NBA Advanced: tempo/OFF/DEF nie są automatycznie odtwarzane z punktów")
    for code in (away,home):
        if code not in ratings and ratings:
            flags.append(f"{code}: brak pełnych zweryfikowanych Pace/OFF/DEF")
    if any(x["Historia 10"]!="10/10" for x in rows):
        flags.append("Próba historii jest mniejsza niż 10 spotkań")
    return pd.DataFrame(rows), flags


def venue_research_candidate(completed, game, minimum=MODEL_MIN_VENUE_GAMES):
    """Experimental split-adjusted version of SAME legacy expectations.

    Only shrink toward legacy means by 25%, cap shift to 3 pts/team;
    return None if either relevant venue sample is too small.
    Never substitute for production, never claim calibrated probability.
    """
    from simulation_engine import completed_team_scores, legacy_matchup_means
    verified=verified_history(completed,game.get("start_utc"))
    home=str(game.get("home") or "")
    away=str(game.get("away") or "")
    hist=completed_team_scores(verified)
    baseline=legacy_matchup_means(home,away,{},hist)
    if baseline is None:
        return None
    h=team_snapshot(verified,home,opponent=away,venue="home")
    a=team_snapshot(verified,away,opponent=home,venue="away")
    if min(h["venue_sample"],a["venue_sample"])<minimum:
        return None
    # Same season, same model baseline; venue effect uses only earlier real scores.
    home_delta=np.clip(.25*(h["venue_scored"]-h["pts20"]),-3,3)
    away_delta=np.clip(.25*(a["venue_scored"]-a["pts20"]),-3,3)
    return {
        **baseline,
        "home":float(baseline["home"]+home_delta),
        "away":float(baseline["away"]+away_delta),
        "source":"BADAWCZY — 25% korekty splitu dom/wyjazd (bez potwierdzonej przewagi)",
        "venue_samples":(h["venue_sample"],a["venue_sample"]),
        "warning":"Nie włączać do produkcji bez niezależnego backtestingu",
    }
