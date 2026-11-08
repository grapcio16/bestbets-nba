"""Daily NBA Center: verified ESPN event IDs and actual completed box scores."""
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import timedelta

import pandas as pd

from viewer_time import games_on_day


def previous_day_ranking(completed, today, zone, fetch=None):
    """Only ESPN summaries of final matches on the viewer's *previous local day*.

    ESPN event IDs are NOT NBA Stats game IDs; never join the two namespaces.
    Reports partial coverage instead of inventing missing player performances.
    """
    if fetch is None:
        from espn_player_data import fetch_boxscore
        fetch = fetch_boxscore
    fields=["PLAYER_NAME","TEAM_ABBREVIATION","PTS","REB","AST","MIN","POSITION","OPPONENT"]
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
    frame=frame.dropna(subset=["PLAYER_NAME","TEAM_ABBREVIATION","PTS","REB","AST"])
    if "GAME_ID" in frame and "PLAYER_ID" in frame:
        frame=frame.drop_duplicates(["GAME_ID","PLAYER_ID"])
    frame=frame.sort_values(["PTS","REB","AST","PLAYER_NAME"],ascending=[False,False,False,True]).head(10)
    return frame[fields].reset_index(drop=True),{"requested_games":len(matches),"complete_games":ok,"failed_games":failed}
