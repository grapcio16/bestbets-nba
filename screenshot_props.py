"""Exact manual transcription of 5 user-provided player prop screenshots, 7 Nov 2026.

Historical, user-supplied fixed snapshot: NOT live market data and NOT verified
against a bookmaker API. Do not show as actionable/current odds after screenshot
capture; calculated probabilities are uncalibrated experimental estimates.
Each tuple is (player, market, half-point line, OVER price, UNDER price).
"""
from __future__ import annotations

from datetime import date
import pandas as pd

SNAPSHOT_DATE = date(2026, 11, 7)
SNAPSHOT_ASOF_UTC = pd.Timestamp("2026-11-07T18:10:00Z")
SNAPSHOT_LABEL = "07.11.2026 — przepisane ze screenów użytkownika"
PROP_SNAPSHOT = [
    # Points: 13 paired markets
    ("Aaron Gordon","PTS",13.5,1.93,1.72),
    ("Aaron Nesmith","PTS",12.5,1.75,1.89),
    ("Andrew Nembhard","PTS",15.5,1.74,1.90),
    ("Cameron Johnson","PTS",12.5,1.84,1.79),
    ("Christian Braun","PTS",12.5,1.78,1.86),
    ("DeMar DeRozan","PTS",12.5,1.94,1.71),
    ("Ivica Zubac","PTS",10.5,1.98,1.68),
    ("Jamal Murray","PTS",22.5,1.75,1.89),
    ("Kelly Oubre Jr","PTS",9.5,1.82,1.81),
    ("Nikola Jokic","PTS",25.5,1.76,1.88),
    ("Obi Toppin","PTS",11.5,1.82,1.82),
    ("Pascal Siakam","PTS",20.5,1.78,1.86),
    ("Spencer Jones","PTS",3.5,1.81,1.83),

    # Made threes: 10 paired markets
    ("Aaron Gordon","FG3M",1.5,1.98,1.68),
    ("Aaron Nesmith","FG3M",2.5,2.22,1.54),
    ("Andrew Nembhard","FG3M",2.5,2.25,1.52),
    ("Cameron Johnson","FG3M",1.5,1.58,2.15),
    ("Christian Braun","FG3M",1.5,1.94,1.71),
    ("Jamal Murray","FG3M",2.5,1.59,2.12),
    ("Kelly Oubre Jr","FG3M",1.5,2.33,1.49),
    ("Nikola Jokic","FG3M",1.5,1.96,1.69),
    ("Obi Toppin","FG3M",1.5,1.86,1.77),
    ("Pascal Siakam","FG3M",1.5,2.00,1.66),

    # Assists: 9 paired markets
    ("Aaron Gordon","AST",2.5,1.82,1.82),
    ("Aaron Nesmith","AST",1.5,1.81,1.82),
    ("Andrew Nembhard","AST",7.5,1.93,1.72),
    ("Cameron Johnson","AST",2.5,2.17,1.56),
    ("Christian Braun","AST",2.5,2.05,1.63),
    ("DeMar DeRozan","AST",2.5,1.62,2.07),
    ("Jamal Murray","AST",6.5,1.97,1.69),
    ("Nikola Jokic","AST",9.5,1.89,1.75),
    ("Pascal Siakam","AST",3.5,1.62,2.08),

    # Rebounds: 12 paired markets
    ("Aaron Gordon","REB",5.5,1.81,1.83),
    ("Aaron Nesmith","REB",3.5,2.02,1.65),
    ("Andrew Nembhard","REB",2.5,1.77,1.87),
    ("Cameron Johnson","REB",3.5,1.56,2.17),
    ("Christian Braun","REB",4.5,1.86,1.78),
    ("DeMar DeRozan","REB",2.5,2.10,1.60),
    ("Ivica Zubac","REB",7.5,1.67,1.98),
    ("Jamal Murray","REB",4.5,1.84,1.79),
    ("Kelly Oubre Jr","REB",3.5,2.00,1.67),
    ("Nikola Jokic","REB",11.5,1.70,1.95),
    ("Obi Toppin","REB",4.5,1.91,1.73),
    ("Pascal Siakam","REB",6.5,1.86,1.78),

    # PRA points + rebounds + assists: 9 paired markets
    ("Aaron Gordon","PRA",21.5,1.81,1.79),
    ("Aaron Nesmith","PRA",18.5,1.87,1.74),
    ("Andrew Nembhard","PRA",26.5,1.87,1.74),
    ("Cameron Johnson","PRA",19.5,1.89,1.72),
    ("Christian Braun","PRA",19.5,1.73,1.88),
    ("DeMar DeRozan","PRA",17.5,1.83,1.78),
    ("Jamal Murray","PRA",34.5,1.86,1.75),
    ("Nikola Jokic","PRA",47.5,1.81,1.79),
    ("Pascal Siakam","PRA",31.5,1.83,1.77),
]


def screenshot_props():
    """Exactly 53 markets, 106 prices. No dynamically invented values."""
    df=pd.DataFrame(PROP_SNAPSHOT,columns=["player","market","line","over","under"])
    if df.duplicated(subset=["player","market"]).any():
        raise ValueError("Powtórzone rynki z archiwum screenów")
    if (df[["over","under"]]<=1).any().any() or ((df["line"]%1)!=.5).any():
        raise ValueError("Niewłaściwa linia lub kurs w ręcznym archiwum")
    return df


def market_ledger(df=None):
    """Two independent rows per offer; no odds are misrepresented as current."""
    if df is None:df=screenshot_props()
    records=[]
    for p in df.to_dict("records"):
        for side in ("OVER","UNDER"):
            records.append({
                "player":p["player"],"market":p["market"],
                "line":p["line"],"side":side,"odds":float(p[side.lower()]),
                "snapshot_date":SNAPSHOT_DATE.isoformat()
            })
    return pd.DataFrame(records)


def model_assessment(projection, line, over, under):
    """Return descriptive estimates for both sides, never a guaranteed edge."""
    from core import prop_probability
    values={}
    for side,price in (("OVER",over),("UNDER",under)):
        p=prop_probability(projection,float(line),side)
        values[side]={
            "p_model":round(100*p,1),
            "p_break_even":round(100/float(price),1),
            "edge_pp":round(100*(p-1/float(price)),1),
            "ev_pct":round(100*(p*float(price)-1),1),
            "odds":float(price)
        }
    return values



def player_snapshot(player: str):
    """Search screenshot prices by normalized name, tolerant to Jr punctuation."""
    from core import norm_name
    df=screenshot_props()
    return df[df["player"].map(norm_name)==norm_name(player)].copy()


def player_market_report(logs: pd.DataFrame, offers: pd.DataFrame):
    """Compare all markets for one athlete, never invent missing samples."""
    from core import calc_projection
    rows=[]
    if logs is not None and not logs.empty:
        logs=logs[pd.to_datetime(logs["GAME_DATE"],errors="coerce",utc=True)<SNAPSHOT_ASOF_UTC].copy()
    for offer in offers.to_dict("records"):
        rec={
            "Statystyka":offer["market"],"Linia":float(offer["line"]),
            "OVER kurs":float(offer["over"]),"UNDER kurs":float(offer["under"]),
            "Prognoza":None,"Występy":0,"OVER model %":None,
            "UNDER model %":None,"OVER EV model %":None,"UNDER EV model %":None,
            "Status":"Brak danych",
        }
        market=offer["market"]
        if logs is not None and not logs.empty and market in logs:
            valid=logs[(pd.to_numeric(logs["MIN"],errors="coerce")>2)
                       & pd.to_numeric(logs[market],errors="coerce").notna()]
            rec["Występy"]=len(valid)
            if len(valid)>=5:
                try:
                    p=calc_projection(valid,market)
                    assessment=model_assessment(p,offer["line"],offer["over"],offer["under"])
                    rec.update({
                        "Prognoza":p["prediction"],
                        "OVER model %":assessment["OVER"]["p_model"],
                        "UNDER model %":assessment["UNDER"]["p_model"],
                        "OVER EV model %":assessment["OVER"]["ev_pct"],
                        "UNDER EV model %":assessment["UNDER"]["ev_pct"],
                        "Status":"Model eksperymentalny",
                    })
                except (ValueError,TypeError,KeyError):
                    rec["Status"]="Brak poprawnych danych"
            else:
                rec["Status"]="Za mała próba (<5)"
        rows.append(rec)
    return pd.DataFrame(rows)
