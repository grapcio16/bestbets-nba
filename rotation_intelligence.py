"""BestBets v7.16: observed playing-time trends and cautiously labeled roster risk.

No probabilities, team score adjustments, inferred starting lineups, or forecasts
of minutes redistributed to other players. All comparisons are team- and
player-specific, with historical samples bounded strictly before the matchup.
"""
from __future__ import annotations

import re
from typing import Any

import numpy as np
import pandas as pd

from core import norm_name

REPORT_COLUMNS=[
    "Drużyna","Zawodnik","Pozycja","Status ESPN","Ocena statusu",
    "Minuty modelu","Minuty ostatnie 3","Minuty ostatnie 7",
    "Zmiana 3 vs 7","Próba ostatnich minut","Próba występów",
    "PTS modelu","Sygnał rotacji",
]
TEAM_METRIC_COLUMNS=[
    "Drużyna","Zawodnicy z projekcją minut","Zawodnicy ze statusem",
    "Minuty modelu: Out/Doubtful","Minuty modelu: Questionable/DTD",
    "Zawodnicy z wahaniem minut >=4","Dane statusu aktualne",
]


def _number(value, minimum=0, maximum=None):
    try:
        n=float(value)
    except (TypeError,ValueError):
        return None
    if not np.isfinite(n) or n<minimum or (maximum is not None and n>maximum):
        return None
    return n


def status_class(value):
    """Classify explicit ESPN wording; do not interpret missing as available."""
    s=str(value or "").casefold().strip()
    if not s or s in ("nan","none","—"):
        return "Brak potwierdzenia"
    if re.search(r"\b(out|inactive|suspended|injured reserve)\b",s):
        return "Out"
    if re.search(r"\bdoubtful\b",s):
        return "Doubtful"
    if re.search(r"\bquestionable\b",s):
        return "Questionable"
    if re.search(r"\bprobable\b",s):
        return "Probable"
    if re.search(r"day[ -]?to[ -]?day|\bdtd\b",s):
        return "Day-to-day"
    return "Inny / niepotwierdzony"


def minutes_trends(logs, cutoff_utc, home=None, away=None):
    """Last 3 vs last 7 ACTUAL logged minutes by club/name, strictly pregame.

    Both n and the observed last 7 sample are returned; n<5 cannot establish
    an actionable rotation trend. DNP is not fabricated as 0 minutes.
    """
    cols=["team","player","n","avg3","avg7","delta","std7","trend"]
    mandatory={"PLAYER_NAME","TEAM_ABBREVIATION","GAME_DATE","MIN"}
    if logs is None or not isinstance(logs,pd.DataFrame) or logs.empty or not mandatory.issubset(logs.columns):
        return pd.DataFrame(columns=cols)
    cutoff=pd.to_datetime(cutoff_utc,utc=True,errors="coerce")
    if pd.isna(cutoff):
        return pd.DataFrame(columns=cols)
    df=logs.copy()
    df["GAME_DATE"]=pd.to_datetime(df["GAME_DATE"],utc=True,errors="coerce")
    df["MIN"]=pd.to_numeric(df["MIN"],errors="coerce")
    df=df[(df["GAME_DATE"]<cutoff)&df["GAME_DATE"].notna()&df["MIN"].between(0.1,48)].copy()
    if home and away:
        df=df[df["TEAM_ABBREVIATION"].isin([str(home),str(away)])]
    if df.empty:
        return pd.DataFrame(columns=cols)
    if "GAME_ID" in df:
        df=df.drop_duplicates(["TEAM_ABBREVIATION","PLAYER_NAME","GAME_ID"],keep="last")
    rows=[]
    for (team,player),grp in df.groupby(["TEAM_ABBREVIATION","PLAYER_NAME"],dropna=True):
        g=grp.sort_values("GAME_DATE").tail(7)
        vals=g["MIN"].to_numpy(dtype=float)
        avg3=round(float(np.mean(vals[-3:])),1)
        avg7=round(float(np.mean(vals)),1)
        delta=round(avg3-avg7,1) if len(vals)>=5 else None
        stdev=round(float(np.std(vals,ddof=1)),1) if len(vals)>=3 else None
        trend="Za mała próba" if delta is None else (
            "Więcej minut" if delta>=4 else "Mniej minut" if delta<=-4 else "Stabilnie")
        rows.append({"team":str(team),"player":str(player),"n":len(vals),
                     "avg3":avg3,"avg7":avg7,"delta":delta,"std7":stdev,"trend":trend})
    return pd.DataFrame(rows,columns=cols)


def _player_code(row):
    return (str(row.get("Drużyna") or "").strip(),norm_name(str(row.get("Zawodnik") or "")))


def rotation_report(player_table, injury_report, home, away, *,
                    rosters=None, trends=None, injury_meta=None, player_meta=None):
    """Return displayed research report, team summary and explicit limitations.

    Injury report is ESPN, NOT the NBA official gameday injury report. Matching
    requires *both* team and exact normalized name; missing is not 'healthy'.
    The high-risk-minute sum is only exposure in projected historical minutes,
    NOT minutes certainly absent nor an expected change in team points.
    """
    sides=[str(away),str(home)]
    raw=player_table if isinstance(player_table,pd.DataFrame) else pd.DataFrame()
    reports=injury_report if isinstance(injury_report,pd.DataFrame) else pd.DataFrame()
    trends=trends if isinstance(trends,pd.DataFrame) else pd.DataFrame()
    roster_tables=rosters if isinstance(rosters,dict) else {}
    meta=injury_meta or {}
    player_meta=player_meta or {}
    warnings=[
        "ESPN nie jest oficjalnym raportem dostępności przed meczem. Brak wpisu NIE oznacza zdrowego zawodnika.",
        "Minuty modelu to historyczna projekcja, nie potwierdzone minuty ani suma 240 minut drużyny.",
        "Ryzykownych minut nie odejmujemy od punktów drużyny: minuty i rzuty mogą przejąć inni zawodnicy.",
    ]
    if meta.get("stale"):
        warnings.append("Raport kontuzji jest nieaktualny: podsumowanie ryzyka minut wymaga świeższego źródła.")
    if player_meta.get("stale"):
        warnings.append("Nie udało się pobrać wszystkich box score dla historii minut.")
    injury_by_key={}
    if not reports.empty and {"Zawodnik","Drużyna","Status ESPN"}.issubset(reports.columns):
        for r in reports.to_dict("records"):
            key=_player_code(r)
            if key[0] not in sides or not key[1]:
                continue
            # In case of conflicting ESPN entries, do not choose a favorable status.
            injury_by_key.setdefault(key,[]).append(str(r.get("Status ESPN") or ""))
    trend_by_key={}
    if not trends.empty and {"team","player","n","avg3","avg7","delta","trend"}.issubset(trends.columns):
        for row in trends.to_dict("records"):
            key=(str(row["team"]),norm_name(str(row["player"])))
            if key[0] in sides:
                trend_by_key[key]=row
    position_by_key={}
    for team in sides:
        df=roster_tables.get(team)
        if isinstance(df,pd.DataFrame) and not df.empty and {"Zawodnik","Pozycja"}.issubset(df.columns):
            for r in df.to_dict("records"):
                p=str(r.get("Pozycja") or "—")
                if p not in ("","?","nan","None","—"):
                    position_by_key[(team,norm_name(str(r["Zawodnik"])))]=p
    rows={}
    if not raw.empty and {"Zawodnik","Drużyna"}.issubset(raw.columns):
        for p in raw.to_dict("records"):
            key=_player_code(p)
            if key[0] not in sides or not key[1]:
                continue
            if key in rows:
                continue
            minutes=_number(p.get("Minuty"),minimum=0,maximum=48)
            sample=_number(p.get("Próba występów"),minimum=0)
            if sample is None or sample<2:
                minutes=None
            points=_number(p.get("PTS"),minimum=0)
            rows[key]={
                "Drużyna":key[0],"Zawodnik":str(p.get("Zawodnik") or ""),
                "Minuty modelu":round(minutes,1) if minutes is not None else None,
                "Próba występów":int(sample) if sample is not None else None,
                "PTS modelu":round(points,1) if points is not None else None,
            }
    # Injury-only athletes must be shown even if they have no projected minutes.
    for key in injury_by_key:
        if key not in rows:
            original=next((r for r in reports.to_dict("records")
                          if _player_code(r)==key),{})
            rows[key]={"Drużyna":key[0],
                       "Zawodnik":str(original.get("Zawodnik") or ""),
                       "Minuty modelu":None,"Próba występów":None,"PTS modelu":None}
    compiled=[]
    for key,p in rows.items():
        statuses=injury_by_key.get(key,[])
        classes={status_class(s) for s in statuses}
        if len(classes)>1:
            label="Sprzeczne wpisy"
            warnings.append(f"Sprzeczne statusy ESPN: {p['Zawodnik']} ({key[0]}).")
        elif statuses:
            label=status_class(statuses[0])
        else:
            label="Brak potwierdzenia"
        item=trend_by_key.get(key,{})
        delta=_number(item.get("delta"),minimum=-100,maximum=100)
        signal=str(item.get("trend") or "Brak danych")
        compiled.append({
            **p, "Pozycja":position_by_key.get(key,"—"),
            "Status ESPN":" / ".join(statuses) if statuses else "Brak wpisu — niepotwierdzony",
            "Ocena statusu":label,
            "Minuty ostatnie 3":item.get("avg3"),
            "Minuty ostatnie 7":item.get("avg7"),
            "Zmiana 3 vs 7":round(delta,1) if delta is not None else None,
            "Próba ostatnich minut":item.get("n"),
            "Sygnał rotacji":signal,
        })
    report=pd.DataFrame(compiled,columns=REPORT_COLUMNS)
    summary=[]
    for code in sides:
        group=report[report["Drużyna"]==code] if not report.empty else report
        high=group[group["Ocena statusu"].isin(["Out","Doubtful"])] if not group.empty else group
        uncertain=group[group["Ocena statusu"].isin(["Questionable","Day-to-day"])] if not group.empty else group
        fresh=not bool(meta.get("stale")) and bool(meta.get("available")) and not reports.empty
        sum_minutes=lambda part: round(float(pd.to_numeric(part["Minuty modelu"],errors="coerce").sum()),1) if not part.empty else 0.0
        summary.append({
            "Drużyna":code,
            "Zawodnicy z projekcją minut":int(pd.to_numeric(group["Minuty modelu"],errors="coerce").notna().sum()) if not group.empty else 0,
            "Zawodnicy ze statusem":sum((code,k) in injury_by_key for k in [norm_name(str(n)) for n in group["Zawodnik"]]) if not group.empty else 0,
            "Minuty modelu: Out/Doubtful":sum_minutes(high) if fresh else None,
            "Minuty modelu: Questionable/DTD":sum_minutes(uncertain) if fresh else None,
            "Zawodnicy z wahaniem minut >=4":int((pd.to_numeric(group["Zmiana 3 vs 7"],errors="coerce").abs()>=4).sum()) if not group.empty else 0,
            "Dane statusu aktualne":bool(fresh),
        })
    if report.empty:
        warnings.append("Brak zweryfikowanych próbek zawodników lub dopasowanych wpisów ESPN dla tego meczu.")
    if not trends.empty and len(trends)<8:
        warnings.append("Mało zawodników z historią minut — nie oceniamy całej rotacji.")
    return report, pd.DataFrame(summary,columns=TEAM_METRIC_COLUMNS), list(dict.fromkeys(warnings))
