"""ESPN availability resilience for the selected upcoming NBA fixture.

Prefer the existing league-wide snapshot; fall back to both team-scoped injury
endpoints if the league request fails or contains no entries for the matchup.
All results include fetch timestamp and coverage information. Team-roster
membership and last boxscores never imply that a player is healthy.
The NBA official report is an independent future provider; do not silently
claim its verification when only ESPN was queried.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import pandas as pd

from roster_data import ESPN_TEAM_IDS
from sources import http_json, injury_rows


def _team_fetch(team: str):
    """Read a single team-specific ESPN feed; never guess a missing team ID."""
    if team not in ESPN_TEAM_IDS:
        raise ValueError("Unknown ESPN NBA team identifier")
    url = ("https://site.api.espn.com/apis/site/v2/sports/basketball/nba"
           f"/teams/{ESPN_TEAM_IDS[team]}/injuries")
    payload = http_json(url, timeout=7)
    if not isinstance(payload, dict):
        raise ValueError("Malformed team injury feed")
    items = payload.get("injuries")
    if items is None:
        items = payload.get("items")
    if not isinstance(items, list):
        raise ValueError("Team injury feed missing records list")
    # The per-team endpoint is the authority for its team identity even when
    # individual athlete entries do not include an embedded team object.
    safe = {"team": {"abbreviation": team}, "injuries": items}
    rows = injury_rows(safe)
    if not rows.empty:
        rows = rows.loc[rows["team"] == team].copy()
    return rows


def selected_matchup_availability(away: str, home: str, league_fetch=None,
                                  team_fetch=None, now=None):
    """Return (raw ESPN rows, metadata) for the selected teams.

    A successful but empty report is NOT a healthy lineup. If only one team
    endpoint works, preserve its explicit OUT entries and record incomplete
    coverage. Never silently use stale league data as current confirmation.
    """
    teams = (str(away).upper(), str(home).upper())
    if len(set(teams)) != 2 or not all(x in ESPN_TEAM_IDS for x in teams):
        return pd.DataFrame(), {"stale": True, "available": False,
                                "source": "Brak potwierdzonego meczu",
                                "coverage_teams": []}
    moment = (pd.to_datetime(now, utc=True, errors="coerce")
              if now is not None else pd.Timestamp.now(tz="UTC"))
    if league_fetch is None:
        from sources import injuries
        league_fetch = lambda: injuries(refresh=True)
    if team_fetch is None:
        team_fetch = _team_fetch

    primary = pd.DataFrame()
    provider_meta = {}
    try:
        primary, provider_meta = league_fetch()
        if not isinstance(primary, pd.DataFrame):
            primary = pd.DataFrame()
            provider_meta = {"stale": True}
        fetched = pd.to_datetime((provider_meta or {}).get("timestamp"),
                                 utc=True, errors="coerce")
        valid = bool(pd.notna(fetched) and pd.notna(moment) and
                     fetched <= moment and
                     (moment - fetched) <= pd.Timedelta(minutes=90) and
                     not (provider_meta or {}).get("stale"))
        if valid and not primary.empty and {"team", "player", "status"}.issubset(primary.columns):
            matched = primary[primary["team"].isin(teams)].copy()
            if not matched.empty:
                return matched, {**(provider_meta or {}), "source": "ESPN liga",
                                 "coverage_teams": list(teams),
                                 "available": True, "stale": False}
    except (OSError, RuntimeError, ValueError, KeyError, TypeError):
        pass

    responses, covered = [], []
    with ThreadPoolExecutor(max_workers=2) as pool:
        jobs = {team: pool.submit(team_fetch, team) for team in teams}
        for team in teams:
            try:
                table = jobs[team].result()
                if not isinstance(table, pd.DataFrame):
                    continue
                covered.append(team)
                if not table.empty:
                    responses.append(table[table["team"] == team].copy())
            except (OSError, RuntimeError, ValueError, KeyError, TypeError):
                continue
    if covered:
        result = pd.concat(responses, ignore_index=True) if responses else pd.DataFrame()
        return result, {"source": "ESPN drużyny",
                        "timestamp": moment.isoformat(),
                        "available": True, "stale": False,
                        "coverage_teams": covered,
                        "partial": len(covered) != 2}
    # Do not carry forward an unverifiable stale OUT snapshot as a fresh
    # medical clearance. The projection layer will label its data conditional.
    return pd.DataFrame(), {"source": "ESPN niedostępne",
                            "available": False, "stale": True,
                            "coverage_teams": []}
