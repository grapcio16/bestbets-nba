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
    fields=["PLAYER_NAME","TEAM_ABBREVIATION","PTS","REB","AST"]
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
    frame=frame.dropna(subset=["PLAYER_NAME","TEAM_ABBREVIATION","PTS","REB","AST"])
    if "GAME_ID" in frame and "PLAYER_ID" in frame:
        frame=frame.drop_duplicates(["GAME_ID","PLAYER_ID"])
    frame=frame.sort_values(["PTS","REB","AST","PLAYER_NAME"],ascending=[False,False,False,True]).head(10)
    return frame[fields].reset_index(drop=True),{"requested_games":len(matches),"complete_games":ok,"failed_games":failed}
