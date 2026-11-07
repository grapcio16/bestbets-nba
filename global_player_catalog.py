"""Lazy, cached global NBA player index for calculator search.

One row per (ESPN athlete ID, current team). Fetches all 30 roster endpoints
only when opening the calculator, with bounded concurrency; never on game cards.
Returns coverage diagnostics rather than pretending partial data is complete.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import pandas as pd

from roster_data import ESPN_TEAM_IDS, COLUMNS, team_roster


def build_global_catalog(roster_fetch=team_roster, max_workers=10):
    """Aggregate current team rosters; failed teams are explicitly reported."""
    teams=sorted(ESPN_TEAM_IDS)
    all_rosters=[]
    failed=[]
    stale=[]
    with ThreadPoolExecutor(max_workers=min(max(1,max_workers),10)) as pool:
        tasks={pool.submit(roster_fetch,team):team for team in teams}
        for future in as_completed(tasks):
            team=tasks[future]
            try:
                roster,meta=future.result()
                if roster is None or roster.empty:
                    failed.append(team)
                    continue
                valid=roster.copy()
                valid=valid[valid["TEAM_ABBREVIATION"]==team]
                if valid.empty:
                    failed.append(team)
                    continue
                all_rosters.append(valid)
                if meta.get("stale"):
                    stale.append(team)
            except Exception:
                failed.append(team)
    catalog=(pd.concat(all_rosters,ignore_index=True)
             if all_rosters else pd.DataFrame(columns=COLUMNS))
    if not catalog.empty:
        catalog["PLAYER_ID"]=catalog["PLAYER_ID"].astype(str)
        catalog=catalog.drop_duplicates(subset=["PLAYER_ID","TEAM_ABBREVIATION"])
        catalog=catalog.sort_values(["PLAYER_NAME","TEAM_ABBREVIATION"]).reset_index(drop=True)
    return catalog,{
        "teams_loaded":len(teams)-len(failed),
        "teams_total":len(teams),
        "players":len(catalog),
        "missing_teams":sorted(failed),
        "stale_teams":sorted(stale),
    }
