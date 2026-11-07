"""Optional diagnostic: evaluate user screenshot lines against available pre-snapshot ESPN logs.

This script is NOT an executable trade recommendation. It never uses later games
or pretends screenshot bookmaker prices are current.
"""
from __future__ import annotations
import pandas as pd

from global_player_catalog import build_global_catalog
from roster_data import team_recent_logs
from core import norm_name, normalize_logs
from screenshot_props import screenshot_props,player_market_report,SNAPSHOT_LABEL


def evaluate_snapshot_diagnostic():
    offers=screenshot_props()
    catalog,coverage=build_global_catalog()
    name_to_player={}
    for row in catalog.to_dict("records"):
        key=norm_name(row["PLAYER_NAME"])
        name_to_player.setdefault(key,row)
    teams={}
    report=[]
    for player in sorted(offers["player"].unique()):
        offer=offers[offers["player"]==player].copy()
        mapped=name_to_player.get(norm_name(player))
        if mapped is None:
            for o in offer.to_dict("records"):
                report.append([player,o["market"],o["line"],o["over"],o["under"],
                               None,None,None,None,None,"Brak zawodnika w katalogu"])
            continue
        team=mapped["TEAM_ABBREVIATION"]
        if team not in teams:
            try:
                raw,meta=team_recent_logs(team,"2026-27",games_per_team=10)
                teams[team]=(normalize_logs(raw) if not raw.empty else pd.DataFrame(),meta)
            except Exception as exc:
                teams[team]=(pd.DataFrame(),{"warning":str(exc)[:100]})
        logs,meta=teams[team]
        if not logs.empty:
            ids=logs["PLAYER_ID"].astype(str)==str(mapped["PLAYER_ID"])
            selected=logs[ids].copy()
            if selected.empty:
                selected=logs[logs["PLAYER_NAME"].map(norm_name)==norm_name(player)].copy()
        else:
            selected=pd.DataFrame()
        summary=player_market_report(selected,offer)
        for s in summary.to_dict("records"):
            report.append([player,s["Statystyka"],s["Linia"],s["OVER kurs"],s["UNDER kurs"],
                           s["Prognoza"],s["Występy"],s["OVER model %"],
                           s["OVER EV model %"],s["UNDER EV model %"],s["Status"]])
    cols=["player","market","line","over","under","prediction","n_games",
          "over_p_model","over_ev_pct","under_ev_pct","status"]
    frame=pd.DataFrame(report,columns=cols)
    print("SOURCE:",SNAPSHOT_LABEL)
    print("NO LOOKAHEAD: game dates strictly before screenshot cutoff")
    print("ROSTER COVERAGE:",coverage)
    print("MARKETS:",len(frame),"EVALUABLE:",int(frame["prediction"].notna().sum()))
    print(frame.to_string(index=False,max_rows=60))
    return frame

if __name__=="__main__":
    evaluate_snapshot_diagnostic()
