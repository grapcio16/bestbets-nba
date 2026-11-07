"""Lightweight NBA team roster catalog and on-demand player-game samples.

A roster is NOT a boxscore: athletes are listed even when they have not played.
ESPN APIs are unofficial and may be delayed, blocked, or unsuitable for
commercial redistribution without an appropriate data license.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import pandas as pd

from teams import TEAM_FULL
from sources import memoized_json, read_cache, store_cache, now_utc

ROSTER_API = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams/{team_id}/roster"
# Numeric IDs are ESPN team IDs, NOT official NBA franchise IDs.
ESPN_TEAM_IDS = {
    "ATL":1,"BOS":2,"BKN":17,"CHA":30,"CHI":4,"CLE":5,
    "DAL":6,"DEN":7,"DET":8,"GSW":9,"HOU":10,"IND":11,
    "LAC":12,"LAL":13,"MEM":29,"MIA":14,"MIL":15,"MIN":16,
    "NOP":3,"NYK":18,"OKC":25,"ORL":19,"PHI":20,"PHX":21,
    "POR":22,"SAC":23,"SAS":24,"TOR":28,"UTA":26,"WAS":27,
}
COLUMNS = ["PLAYER_ID", "PLAYER_NAME", "TEAM_ABBREVIATION", "POSITION", "ROSTER_STATUS"]


def parse_team_roster(payload: dict, team: str) -> pd.DataFrame:
    """Accept both NBA flat athletes and position-grouped athlete schemas."""
    if team not in TEAM_FULL:
        raise ValueError("Nieznana drużyna NBA")
    rows = []
    groups = payload.get("athletes") or payload.get("roster") or []
    if isinstance(groups,dict):
        groups = groups.get("items") or groups.get("athletes") or []
    for group in groups:
        # Some provider responses group athletes by position.
        candidates = (group.get("items") or group.get("athletes") or [group]) if isinstance(group,dict) else []
        for item in candidates:
            if not isinstance(item,dict):
                continue
            athlete = item.get("athlete") if isinstance(item.get("athlete"),dict) else item
            name = str(athlete.get("displayName") or athlete.get("fullName") or "").strip()
            ident = str(athlete.get("id") or "").strip()
            if not name or not ident:
                continue
            position = athlete.get("position") or {}
            status = athlete.get("status") or {}
            rows.append({
                "PLAYER_ID": ident,
                "PLAYER_NAME": name,
                "TEAM_ABBREVIATION": team,
                "POSITION": str(position.get("abbreviation") or "?") if isinstance(position,dict) else str(position),
                "ROSTER_STATUS": str(status.get("name") or "Niepotwierdzony") if isinstance(status,dict) else "Niepotwierdzony",
            })
    return (pd.DataFrame(rows,columns=COLUMNS)
            .drop_duplicates(subset=["PLAYER_ID"])
            .sort_values("PLAYER_NAME")
            .reset_index(drop=True))


def team_roster(team: str, refresh: bool = False):
    """Fetch ONE selected team's roster, memoized on disk for 12 hours."""
    if team not in ESPN_TEAM_IDS:
        raise ValueError("Nieznana drużyna NBA")
    payload, meta = memoized_json(
        "espn-roster-v7-"+team,
        ROSTER_API.format(team_id=ESPN_TEAM_IDS[team]),
        ttl_seconds=12*3600, refresh=refresh, request_timeout=7,
    )
    df = parse_team_roster(payload,team)
    if df.empty:
        raise RuntimeError("ESPN zwróciło pusty lub nierozpoznany skład "+team)
    meta["source"] = "ESPN — skład drużyny "+team
    return df,meta


def team_recent_logs(team: str, season: str, games_per_team: int = 10):
    """Actual completed boxscores for a single team, only when user opens data.

    Uses shared per-event disk cache from the simulation view. Missing individual
    games are never filled with estimates or counted as complete observations.
    """
    if team not in TEAM_FULL:
        raise ValueError("Nieznana drużyna NBA")
    from simulation_sources import historical_espn_results
    from espn_player_data import fetch_boxscore

    history, warning = historical_espn_results(season)
    if history is None or history.empty:
        return pd.DataFrame(),{
            "source": "ESPN — zakończone mecze",
            "coverage": "0/"+str(games_per_team),
            "warning": warning or "Brak zakończonych meczów",
        }
    h = history.copy()
    h["start_utc"] = pd.to_datetime(h["start_utc"],utc=True,errors="coerce")
    now = pd.Timestamp.now(tz="UTC")
    games = h[
        (pd.to_numeric(h["status_code"],errors="coerce")==3)
        & (h["start_utc"]<now)
        & ((h["away"]==team)|(h["home"]==team))
    ].sort_values("start_utc",ascending=False)
    selected = []
    for g in games.to_dict("records"):
        eid = str(g.get("game_id") or "")
        if eid.isdigit() and len(eid)<=10:
            selected.append(g)
        if len(selected)>=games_per_team:
            break
    if not selected:
        return pd.DataFrame(),{"source":"ESPN","coverage":"0/"+str(games_per_team),
                               "warning":"Brak zakończonych meczów wybranej drużyny"}
    rows = []
    covered = 0
    def one(game):
        eid = str(game["game_id"])
        failure,_ = read_cache("espn-roster-logs-failed-"+eid,20*60)
        if failure is not None:
            return []
        try:
            result = fetch_boxscore(game)
            if not result:
                store_cache("espn-roster-logs-failed-"+eid,{"empty":True})
            return result
        except Exception as exc:
            store_cache("espn-roster-logs-failed-"+eid,{"reason":str(exc)[:100]})
            return []
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(one,g) for g in selected]
        for future in as_completed(futures):
            result = future.result()
            if result:
                rows.extend(r for r in result if r.get("TEAM_ABBREVIATION")==team)
                covered += 1
    if not rows:
        return pd.DataFrame(),{"source":"ESPN — boxscore","coverage":"0/"+str(len(selected)),
                               "warning":"Nie udało się pobrać rzeczywistych statystyk tej drużyny"}
    df = pd.DataFrame(rows).drop_duplicates(subset=["GAME_ID","PLAYER_ID"])
    return df,{"source":"ESPN — zakończone mecze "+team,
               "timestamp":now_utc().isoformat(),
               "coverage":str(covered)+"/"+str(len(selected))+" spotkań",
               "stale":covered<len(selected),
               "warning":"Próbka częściowa, nie pełne statystyki sezonu."}
