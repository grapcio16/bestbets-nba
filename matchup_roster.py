"""Display current NBA rosters alongside *available* simulated player estimates.

The ESPN roster identifies who is listed with a team. It is not a confirmed
game-day lineup. No forecast numbers are synthesized for absent sample data.
"""
from __future__ import annotations

import pandas as pd

from core import norm_name

ESTIMATE_COLUMNS = ("PTS", "REB", "AST", "3PM", "Minuty", "Status ESPN", "Próba występów")
DISPLAY_COLUMNS = ("Zawodnik", "Drużyna", "Pozycja", "PTS", "REB", "AST", "3PM",
                   "Minuty", "Status ESPN", "Próba występów", "Dane prognozy")


def roster_projection_table(roster: pd.DataFrame | None,
                            modeled: pd.DataFrame | None, team: str):
    """Roster-first table, with empty forecast cells for athletes without logs.

    Only players currently returned by the ESPN roster endpoint are matched.
    Discard older log-only records for this roster-first view, while explicitly
    reporting their count. The raw simulation stays unchanged.
    """
    available = modeled if isinstance(modeled,pd.DataFrame) else pd.DataFrame()
    if not available.empty and "Drużyna" in available:
        available = available[available["Drużyna"]==team].copy()
    else:
        available = pd.DataFrame(columns=["Zawodnik", "Drużyna", *ESTIMATE_COLUMNS])
    selected = roster if isinstance(roster,pd.DataFrame) else pd.DataFrame()
    selected = selected.copy()
    if not selected.empty and "TEAM_ABBREVIATION" in selected:
        selected = selected[selected["TEAM_ABBREVIATION"]==team]
    else:
        selected = pd.DataFrame()
    if selected.empty:
        return available, {
            "roster_available": False,
            "roster_count": 0,
            "projected": len(available),
            "missing": 0,
            "not_on_roster": 0,
        }
    predicted = {}
    for row in available.to_dict("records"):
        key = norm_name(row.get("Zawodnik"))
        if key and key not in predicted:
            predicted[key] = row

    rows = []
    seen = set()
    with_projection = 0
    for row in selected.to_dict("records"):
        name = str(row.get("PLAYER_NAME") or "").strip()
        identity = norm_name(name)
        if not identity or identity in seen:
            continue
        seen.add(identity)
        pred = predicted.get(identity)
        item = {
            "Zawodnik": name,
            "Drużyna": team,
            "Pozycja": str(row.get("POSITION") or "—"),
            **{column: pred.get(column) if pred is not None else None
               for column in ESTIMATE_COLUMNS},
            "Dane prognozy": ("Próba: "+str(pred.get("Próba występów","?"))+" meczów")
                              if pred is not None
                              else "Brak wystarczających występów",
        }
        if pred is not None:
            with_projection += 1
        rows.append(item)

    result = pd.DataFrame(rows,columns=DISPLAY_COLUMNS)
    result = result.sort_values(
        by=["Dane prognozy","Zawodnik"],
        key=lambda col: col.map(lambda x: 0 if str(x).startswith("Próba:") else 1)
        if col.name=="Dane prognozy" else col,
    ).reset_index(drop=True)
    return result, {
        "roster_available": True,
        "roster_count": len(result),
        "projected": with_projection,
        "missing": len(result)-with_projection,
        "not_on_roster": sum(key not in seen for key in predicted),
    }
