"""Daily NBA Center: verified ESPN event IDs and actual completed box scores."""
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import timedelta

import pandas as pd

from viewer_time import games_on_day


def fill_missing_positions(frame, roster_fetcher=None):
    """Resolve nominal positions via the live ESPN team roster only when boxscore
    didn't supply them. Match both exact ESPN athlete ID and club; do not guess.
    This happens AFTER ranking, at most one fetch per missing club, cached 12h.
    """
    if frame is None or frame.empty or "PLAYER_ID" not in frame:
        return frame
    if roster_fetcher is None:
        from roster_data import team_roster
        roster_fetcher = team_roster
    from roster_data import ESPN_TEAM_IDS

    missing = frame["POSITION"].fillna("").astype(str).str.strip().isin(["", "nan", "None", "?"])
    teams = sorted({str(team) for team in frame.loc[missing,"TEAM_ABBREVIATION"] if str(team) in ESPN_TEAM_IDS})
    if not teams:
        return frame
    by_team = {}
    def lookup(team):
        try:
            roster, metadata = roster_fetcher(team)
            # Stale roster or mismatched ESPN identity must not override boxscore.
            if roster is not None and not roster.empty and not metadata.get("stale"):
                return team, roster
        except Exception:
            pass
        return team, None
    with ThreadPoolExecutor(max_workers=3) as pool:
        for team, roster in pool.map(lookup, teams):
            if roster is not None:
                by_team[team] = {
                    str(r["PLAYER_ID"]): str(r["POSITION"])
                    for r in roster.to_dict("records")
                    if str(r.get("POSITION") or "").strip() not in ("", "?", "nan", "None")
                }
    result = frame.copy()
    for idx, rec in result.loc[missing].iterrows():
        code = str(rec.get("TEAM_ABBREVIATION") or "")
        pid = str(rec.get("PLAYER_ID") or "")
        actual = by_team.get(code, {}).get(pid)
        if actual:
            result.at[idx, "POSITION"] = actual
    return result


def previous_day_ranking(completed, today, zone, fetch=None, roster_fetcher=None):
    """Only ESPN summaries of final matches on the viewer's *previous local day*.

    ESPN event IDs are NOT NBA Stats game IDs; never join the two namespaces.
    Reports partial coverage instead of inventing missing player performances.
    """
    fetch_is_real = fetch is None
    if fetch is None:
        from espn_player_data import fetch_boxscore
        fetch = fetch_boxscore
    fields=["PLAYER_NAME","TEAM_ABBREVIATION","PTS","REB","AST","MIN","POSITION","OPPONENT","MATCHUP"]
    empty=pd.DataFrame(columns=fields)
    matches=games_on_day(completed,today-timedelta(days=1),zone)
    if matches.empty:
        return empty,{"requested_games":0,"complete_games":0,"failed_games":0}
    matches=matches[pd.to_numeric(matches["status_code"], errors="coerce")==3]
    rows=[]; ok=0; failed=0
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures=[pool.submit(fetch, game) for game in matches.to_dict("records")]
        for future in as_completed(futures):
            try:
                players=future.result()
                if players:
                    rows.extend(players)
                    ok+=1
                else:
                    failed+=1
            except Exception:
                failed+=1
    if not rows:
        return empty,{"requested_games":len(matches),"complete_games":ok,"failed_games":failed}
    frame=pd.DataFrame(rows)
    for col in ["PTS","REB","AST"]:
        frame[col]=pd.to_numeric(frame[col],errors="coerce")
    # Minutes, opponent and position are optional ESPN boxscore fields.
    # Preserve unknowns instead of inventing a value or removing a top scorer.
    if "MIN" not in frame.columns:
        frame["MIN"]=float("nan")
    frame["MIN"]=pd.to_numeric(frame["MIN"],errors="coerce")
    if "POSITION" not in frame.columns:
        frame["POSITION"]=""
    if "OPPONENT" not in frame.columns:
        frame["OPPONENT"]=""
    if "MATCHUP" not in frame.columns:
        frame["MATCHUP"]=""
    # Derive the opponent exclusively from the game ID and actual team's schedule.
    # The match lookup is useful when an older cached ESPN record omitted OPPONENT.
    schedule_by_id={
        str(game.get("game_id")): game for game in matches.to_dict("records")
    }
    def opponent_for(record):
        listed=str(record.get("OPPONENT") or "").strip()
        if listed and listed.lower() not in ("nan","none","—"):
            return listed
        game=schedule_by_id.get(str(record.get("GAME_ID") or ""))
        if not game:
            return ""
        club=str(record.get("TEAM_ABBREVIATION") or "")
        if club==str(game.get("away")):
            return str(game.get("home") or "")
        if club==str(game.get("home")):
            return str(game.get("away") or "")
        return ""
    frame["OPPONENT"]=frame.apply(opponent_for,axis=1)
    def verified_matchup(record):
        game=schedule_by_id.get(str(record.get("GAME_ID") or ""))
        club=str(record.get("TEAM_ABBREVIATION") or "")
        if game:
            away=str(game.get("away") or "")
            home=str(game.get("home") or "")
            if club in (away,home) and away and home:
                return f"{away} @ {home}"
        return ""
    frame["MATCHUP"]=frame.apply(verified_matchup,axis=1)
    frame=frame.dropna(subset=["PLAYER_NAME","TEAM_ABBREVIATION","PTS","REB","AST"])
    if "GAME_ID" in frame and "PLAYER_ID" in frame:
        frame=frame.drop_duplicates(["GAME_ID","PLAYER_ID"])
    frame=frame.sort_values(["PTS","REB","AST","PLAYER_NAME"],ascending=[False,False,False,True]).head(10)
    # Fake/injected boxscore clients in tests or research should not make
    # hidden external roster requests. Production can resolve missing positions.
    if fetch_is_real or roster_fetcher is not None:
        frame=fill_missing_positions(frame, roster_fetcher=roster_fetcher)
    return frame[fields].reset_index(drop=True),{"requested_games":len(matches),"complete_games":ok,"failed_games":failed}
