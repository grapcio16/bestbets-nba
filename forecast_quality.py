"""Explain limitations and cross-model disagreement for each BestBets forecast.

This is an AUDIT of model sensitivity and recent data coverage, NOT a
probability calibration and NOT a betting recommendation. No API requests.
"""
from __future__ import annotations
import pandas as pd


def quality_report(game, primary, alternative, history_by_team):
    """Assess two uncalibrated models, recent ESPN samples, and missing data."""
    home,away=str(game["home"]),str(game["away"])
    kickoff=pd.to_datetime(game.get("start_utc"),utc=True,errors="coerce")
    flags=[]
    counts={}
    age={}
    for code in (away,home):
        sample=[]
        for rec in history_by_team.get(code,[]):
            date=pd.to_datetime(rec[0],utc=True,errors="coerce")
            if pd.notna(date) and (pd.isna(kickoff) or date<kickoff):
                sample.append(date)
        counts[code]=len(sample)
        if counts[code]<8:
            flags.append(f"{code}: tylko {counts[code]} zakończonych spotkań w danych")
        if sample and pd.notna(kickoff):
            days=max(0,(kickoff-max(sample)).days)
            age[code]=days
            if days>14:
                flags.append(f"{code}: ostatni znany mecz sprzed {days} dni")
        else:
            age[code]=None
            if not sample:
                flags.append(f"{code}: brak historii wyników")
    primary_margin=float(primary["home"])-float(primary["away"])
    primary_total=float(primary["home"])+float(primary["away"])
    result={
        "home":home,"away":away,
        "history_games":counts,"history_age_days":age,
        "modeled_margin":round(primary_margin,1),
        "modeled_total":round(primary_total,1),
        "alternate_available":False,
        "favorite_flip":False,
        "margin_disagreement":None,
        "total_disagreement":None,
        "alternate_home":None,
        "alternate_away":None,
        "alerts":flags,
    }
    if alternative is None:
        result["alerts"].append("Brak danych do niezależnego wariantu modelu")
    else:
        other_margin=float(alternative["home"])-float(alternative["away"])
        other_total=float(alternative["home"])+float(alternative["away"])
        margin_gap=abs(primary_margin-other_margin)
        total_gap=abs(primary_total-other_total)
        flips=(primary_margin*other_margin<0 and
               max(abs(primary_margin),abs(other_margin))>=2.0)
        result.update({
            "alternate_available":True,
            "favorite_flip":bool(flips),
            "margin_disagreement":round(margin_gap,1),
            "total_disagreement":round(total_gap,1),
            "alternate_home":round(float(alternative["home"]),1),
            "alternate_away":round(float(alternative["away"]),1),
        })
        if flips:
            result["alerts"].append("Modele wskazują innych faworytów")
        if margin_gap>=6:
            result["alerts"].append(
                f"Różnica prognozowanych handicapów: {margin_gap:.1f} pkt")
        if total_gap>=12:
            result["alerts"].append(
                f"Różnica prognozowanych sum: {total_gap:.1f} pkt")
    result["risk_level"]=("Ograniczone dane lub niestabilna prognoza"
                          if result["alerts"] else "Brak dodatkowych alertów")
    return result
