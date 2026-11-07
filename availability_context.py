"""On-demand NBA player availability context from ESPN injury records.

An ESPN feed is not the official game-day injury report. Missing records never
mean healthy/available. No status is applied to team win probabilities until
accurate pregame availability, team identity, and impact have been validated.
"""
from __future__ import annotations

import pandas as pd

from core import norm_name
from teams import TEAM_MAP

ALIASES = {
    "GS":"GSW", "NY":"NYK", "SA":"SAS", "NO":"NOP",
    "PHO":"PHX", "BRK":"BKN", "UTAH":"UTA", "WSH":"WAS",
    "GSW":"GSW", "NYK":"NYK", "SAS":"SAS",
}


def team_code(value):
    label=str(value or "").strip()
    if not label:
        return ""
    upper=label.upper()
    return ALIASES.get(upper,upper) if len(upper)<=4 else TEAM_MAP.get(label,"")


def matchup_injuries(raw, home, away, metadata=None):
    """Only filter explicit team-associated entries, never guess team by name."""
    expected={str(home),str(away)}
    cols=["Zawodnik","Drużyna","Status ESPN","Informacja"]
    if raw is None or not isinstance(raw,pd.DataFrame) or raw.empty:
        return pd.DataFrame(columns=cols), {
            "source":"ESPN injuries",
            "records":0,"available":False,
            "stale":bool((metadata or {}).get("stale")),
            "warning":"Brak rozpoznanych wpisów. To NIE potwierdza zdrowia żadnego zawodnika.",
        }
    items=[]
    for row in raw.to_dict("records"):
        code=team_code(row.get("team"))
        player=str(row.get("player") or "").strip()
        status=str(row.get("status") or "").strip()
        if code not in expected or not player or not status:
            continue
        items.append({
            "Zawodnik":player,"Drużyna":code,
            "Status ESPN":status,
            "Informacja":str(row.get("note") or "")[:240],
        })
    result=pd.DataFrame(items,columns=cols)
    if not result.empty:
        result=result.drop_duplicates(subset=["Drużyna","Zawodnik","Status ESPN"])
        result=result.sort_values(["Drużyna","Zawodnik"]).reset_index(drop=True)
    stale=bool((metadata or {}).get("stale"))
    return result, {
        "source":"ESPN injuries","records":len(result),
        "available":True,"stale":stale,
        "warning":(
            "Dane ESPN mogą być nieaktualne. Nie traktuj wpisów jako aktualnej "
            "decyzji przedmeczowej." if stale else
            "Status ESPN jest orientacyjny. Potwierdź go w oficjalnym raporcie NBA "
            "przed wyciąganiem wniosków."
        )
    }


def player_minutes_brief(player_table, home, away, injury_table=None):
    """Summarize predicted minutes from *observed* player logs, not a starting five."""
    cols=["Zawodnik","Drużyna","Minuty modelu","Występy w próbce",
          "Status kontuzji"]
    if player_table is None or not isinstance(player_table,pd.DataFrame) or player_table.empty:
        return pd.DataFrame(columns=cols)
    expected={str(home),str(away)}
    raw=player_table.copy()
    if "Drużyna" not in raw or "Zawodnik" not in raw or "Minuty" not in raw:
        return pd.DataFrame(columns=cols)
    raw=raw[raw["Drużyna"].isin(expected)]
    injury_lookup={}
    if isinstance(injury_table,pd.DataFrame) and not injury_table.empty:
        for row in injury_table.to_dict("records"):
            injury_lookup[(str(row["Drużyna"]),norm_name(row["Zawodnik"]))]=str(row["Status ESPN"])
    results=[]
    for record in raw.to_dict("records"):
        mins=pd.to_numeric(record.get("Minuty"),errors="coerce")
        if pd.isna(mins) or mins<5 or mins>48:
            continue
        name=str(record["Zawodnik"])
        team=str(record["Drużyna"])
        results.append({
            "Zawodnik":name,"Drużyna":team,
            "Minuty modelu":round(float(mins),1),
            "Występy w próbce":record.get("Próba występów"),
            "Status kontuzji":injury_lookup.get(
                (team,norm_name(name)), "Brak wpisu — status NIEPOTWIERDZONY"),
        })
    if not results:
        return pd.DataFrame(columns=cols)
    return pd.DataFrame(results,columns=cols).sort_values(
        ["Drużyna","Minuty modelu"],ascending=[True,False]
    ).groupby("Drużyna",sort=False).head(6).reset_index(drop=True)
