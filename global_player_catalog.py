"""Verified NBA-wide roster index for calculators and optional player picker.

ESPN rosters are requested only on demand, not on the initial Centrum page.
Retry failed or suspiciously short rosters once at lower concurrency. Never fill
missing athletes with fabricated players or pretend coverage is complete.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import pandas as pd

from roster_data import ESPN_TEAM_IDS, COLUMNS, team_roster


def build_global_catalog(roster_fetch=team_roster, max_workers=5, refresh_all=False):
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
        tasks={pool.submit(fetch_one,team,refresh_all):team for team in teams}
        for future in as_completed(tasks):
            team=tasks[future]
            roster,meta=future.result()
            if roster is None:
                missing.add(team)
            else:
                loaded[team]=roster
                if meta.get("stale"):stale.add(team)
                if len(roster)<8:sparse.add(team)

    # When ESPN returns several short/failed rosters, sequential timeouts
    # previously multiplied the picker wait by the number of teams. Run the
    # SAME one retry per team at a much lower, bounded concurrency (2).
    # Consume results in team order to preserve deterministic identity checks.
    retry_teams=sorted(missing|sparse)
    with ThreadPoolExecutor(max_workers=2) as pool:
        retries={team:pool.submit(fetch_one,team,True) for team in retry_teams}
        for team in retry_teams:
            roster,meta=retries[team].result()
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
    ambiguous_ids=[]
    resolved_stale_ids=[]
    if not catalog.empty:
        catalog["PLAYER_ID"]=catalog["PLAYER_ID"].astype(str)
        catalog=catalog.drop_duplicates(subset=["PLAYER_ID","TEAM_ABBREVIATION"])
        # A trade or an older cached roster can temporarily list one athlete
        # on two clubs. An ESPN ID is unique, so never publish both as though
        # the roster assignments were independently verified.
        conflicting=catalog.groupby("PLAYER_ID")["TEAM_ABBREVIATION"].nunique()
        for player_id in conflicting[conflicting>1].index:
            matches=catalog[catalog["PLAYER_ID"]==player_id]
            fresh=matches[~matches["TEAM_ABBREVIATION"].isin(stale)]
            if len(fresh)==1:
                keep_team=fresh.iloc[0]["TEAM_ABBREVIATION"]
                catalog=catalog[(catalog["PLAYER_ID"]!=player_id) |
                                (catalog["TEAM_ABBREVIATION"]==keep_team)]
                resolved_stale_ids.append(str(player_id))
            else:
                catalog=catalog[catalog["PLAYER_ID"]!=player_id]
                ambiguous_ids.append(str(player_id))
        catalog=catalog.sort_values(["PLAYER_NAME","TEAM_ABBREVIATION"]).reset_index(drop=True)
    return catalog,{
        "teams_loaded":len(teams)-len(missing),
        "teams_total":len(teams),
        "players":len(catalog),
        "missing_teams":sorted(missing),
        "stale_teams":sorted(stale),
        "sparse_teams":sorted(sparse),
        "retried_teams":sorted(team for team,n in attempts.items() if n>1),
        "ambiguous_player_ids":sorted(ambiguous_ids),
        "stale_roster_conflicts_resolved":len(resolved_stale_ids),
        "team_counts":{team:len(roster) for team,roster in sorted(loaded.items())},
    }
