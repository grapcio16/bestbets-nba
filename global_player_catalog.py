"""Verified NBA-wide roster index for calculators and optional player picker.

ESPN rosters are requested only on demand, not on the initial Centrum page.
Retry failed or suspiciously short rosters once at lower concurrency. Never fill
missing athletes with fabricated players or pretend coverage is complete.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import pandas as pd

from roster_data import ESPN_TEAM_IDS, COLUMNS, team_roster


def build_global_catalog(roster_fetch=team_roster, max_workers=5):
    """Collect current ESPN team rosters with a bounded failed-team retry."""
    teams=sorted(ESPN_TEAM_IDS)
    loaded={}
    missing=set()
    stale=set()
    sparse=set()
    attempts={}
    def fetch_one(team, refresh=False):
        attempts[team]=attempts.get(team,0)+1
        try:
            # Custom fetchers in offline tests accept only the team argument.
            if roster_fetch is team_roster:
                roster,meta=roster_fetch(team,refresh=refresh)
            else:
                roster,meta=roster_fetch(team)
            if not isinstance(roster,pd.DataFrame) or roster.empty:
                return None,None
            required={"PLAYER_ID","PLAYER_NAME","TEAM_ABBREVIATION"}
            if not required.issubset(roster.columns):
                return None,None
            valid=roster[
                (roster["TEAM_ABBREVIATION"]==team)
                & roster["PLAYER_ID"].astype(str).str.fullmatch(r"\d+")
                & roster["PLAYER_NAME"].fillna("").astype(str).str.strip().ne("")
            ].copy()
            if valid.empty:
                return None,None
            return valid,meta if isinstance(meta,dict) else {}
        except Exception:
            return None,None

    # Keep request rate bounded; aggressive 30-at-once bursts can trigger
    # ESPN throttling and silently drop players.
    with ThreadPoolExecutor(max_workers=min(max(1,max_workers),5)) as pool:
        tasks={pool.submit(fetch_one,team):team for team in teams}
        for future in as_completed(tasks):
            team=tasks[future]
            roster,meta=future.result()
            if roster is None:
                missing.add(team)
            else:
                loaded[team]=roster
                if meta.get("stale"):stale.add(team)
                if len(roster)<8:sparse.add(team)

    # A single retry for failed and unusually small squads, without burst
    # concurrency. Retain the first verified roster if retry fails.
    for team in sorted(missing|sparse):
        roster,meta=fetch_one(team,refresh=True)
        if roster is not None and (team not in loaded or len(roster)>len(loaded[team])):
            loaded[team]=roster
            if not meta.get("stale"):stale.discard(team)
            else:stale.add(team)
        if team in loaded:
            missing.discard(team)
        if team in loaded and len(loaded[team])>=8:
            sparse.discard(team)

    catalog=(pd.concat(list(loaded.values()),ignore_index=True)
             if loaded else pd.DataFrame(columns=COLUMNS))
    if not catalog.empty:
        catalog["PLAYER_ID"]=catalog["PLAYER_ID"].astype(str)
        catalog=catalog.drop_duplicates(subset=["PLAYER_ID","TEAM_ABBREVIATION"])
        catalog=catalog.sort_values(["PLAYER_NAME","TEAM_ABBREVIATION"]).reset_index(drop=True)
    return catalog,{
        "teams_loaded":len(teams)-len(missing),
        "teams_total":len(teams),
        "players":len(catalog),
        "missing_teams":sorted(missing),
        "stale_teams":sorted(stale),
        "sparse_teams":sorted(sparse),
        "retried_teams":sorted(team for team,n in attempts.items() if n>1),
    }
