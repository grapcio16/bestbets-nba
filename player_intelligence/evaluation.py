"""Offline paired settlement of immutable pregame player forecasts.

No actual participation is used to select a scenario. No missing player
is interpreted as a zero. Restrict comparisons to identical player keys,
report coverage separately and do not compare conditional and all-roster
cohorts interchangeably.
"""
from math import isfinite
import numpy as np
import pandas as pd

from player_intelligence.rotation import _time, _number, MARKETS, LEAD, TEAM_MINUTES

METRICS = ("minutes", *MARKETS, "PRA")


def _actual_rows(rows, cutoff):
    result={}
    for r in rows:
        if r.get("final_verified") is not True or r.get("regulation_only") is not True:
            continue
        tip,seen=_time(r["start_utc"]),_time(r["observed_at"])
        if not tip+pd.Timedelta(hours=4)<=seen<=cutoff:
            continue
        key=(r["game_id"],r["team"],r["player_id"])
        if key in result:
            raise ValueError("duplicate actual player row")
        values={m:_number(r[m],48 if m=="minutes" else 150) for m in METRICS if m!="PRA"}
        played=r.get("played")
        if type(played) is not bool or played!=(values["minutes"]>0):
            raise ValueError("unverified played status")
        if (not played and any(values.values())) or 3*values["FG3M"]>values["PTS"]:
            raise ValueError("inconsistent actual counts")
        values["PRA"]=sum(values[m] for m in ("PTS","REB","AST"))
        result[key]=(tip,values,played)
    return result


def evaluate_paired(*, forecasts, actuals, models, asof, mode="prospective"):
    """First forecast per model/game/team; conditional scenarios kept separate.

    Forecast envelope must carry start_utc, issued_at, scenario_id and model
    output. issued_at must be the actual archived time, not backdated.
    """
    if mode not in ("prospective", "captured_replay"):
        raise ValueError("invalid evaluation evidence mode")
    models=tuple(models)
    if len(models)<2 or len(set(models))!=len(models):
        raise ValueError("at least two distinct model IDs required")
    cutoff=_time(asof)
    actual=_actual_rows(actuals,cutoff)
    selected={}
    for f in forecasts:
        if f.get("evidence_mode")!=mode:
            raise ValueError("mixed or missing forecast evidence mode")
        p=f["projection"]
        model=p.get("model_id")
        if model not in models or p.get("status")!="shadow_conditional":
            continue
        tip,issued,model_clock=(_time(f["start_utc"]),_time(f["issued_at"]),_time(p["asof"]))
        if not model_clock<=issued<tip-LEAD or issued>cutoff:
            continue
        scenario=f.get("scenario_id")
        if not isinstance(scenario,str) or not scenario.strip():
            raise ValueError("explicit pregame scenario identity required")
        key=(p["game_id"],p["team"],scenario,model)
        if key in selected and issued==selected[key][0]:
            if f!=selected[key][1]:
                raise ValueError("conflicting immutable forecast")
            continue
        if key not in selected or issued<selected[key][0]:
            selected[key]=(issued,f)
    # Match only identical scenario and exact pregame model clock.
    candidates={}
    for (gid,team,scenario,model),(_,f) in selected.items():
        p=f["projection"]
        candidates.setdefault((gid,team,scenario),{})[model]=f
    errors={m:{k:[] for k in METRICS} for m in models}
    intervals={m:{k:[] for k in METRICS} for m in models}
    bias={m:{k:[] for k in METRICS} for m in models}
    coverage={m:0 for m in models}
    missing_actual=unmatched_players=matched=played_count=dnp_count=0
    paired_team_games=0
    # Do not multiply a game's weight by choosing among hypothetical scenarios.
    counts={}
    for gid,team,scenario in candidates:
        counts[(gid,team)]=counts.get((gid,team),0)+1
    excluded_multiple=sum(v>1 for v in counts.values())
    for (gid,team,scenario),fs in candidates.items():
        if counts[(gid,team)]!=1:
            continue
        if set(fs)!=set(models):
            continue
        if len({_time(f["projection"]["asof"]) for f in fs.values()})!=1:
            continue
        if len({_time(f["start_utc"]) for f in fs.values()})!=1:
            continue
        tip=_time(next(iter(fs.values()))["start_utc"])
        player_maps={}
        for m,f in fs.items():
            rows=f["projection"]["players"]
            table={r["player_id"]:r for r in rows}
            if len(table)!=len(rows):
                raise ValueError("duplicate forecast player ID")
            player_maps[m]=table
            coverage[m]+=len(table)
        common=set.intersection(*(set(x) for x in player_maps.values()))
        union=set.union(*(set(x) for x in player_maps.values()))
        unmatched_players+=len(union-common)
        contributed=False
        for pid in sorted(common):
            actual_row=actual.get((gid,team,pid))
            if actual_row is None or actual_row[0]!=tip:
                missing_actual+=1
                continue
            _,truth,played=actual_row
            validated={}
            for m,table in player_maps.items():
                row=table[pid]
                stats={}
                for k in METRICS:
                    x=row[k]
                    mean=float(x["mean"] if isinstance(x,dict) else x)
                    if not isfinite(mean) or mean<0 or (k=="minutes" and mean>48+1e-7):
                        raise ValueError("invalid forecast mean")
                    band=None
                    if isinstance(x,dict):
                        lo,hi=float(x["p10"]),float(x["p90"])
                        if not (isfinite(lo) and isfinite(hi) and 0<=lo<=hi):
                            raise ValueError("invalid forecast interval")
                        band=(lo,hi)
                    stats[k]=(mean,band)
                validated[m]=stats
            for m,stats in validated.items():
                for k,(pred,band) in stats.items():
                    err=pred-truth[k]
                    errors[m][k].append(abs(err))
                    bias[m][k].append(err)
                    if band is not None:
                        intervals[m][k].append(band[0]<=truth[k]<=band[1])
            matched+=1
            played_count+=int(played)
            dnp_count+=int(not played)
            contributed=True
        paired_team_games+=int(contributed)
    def avg(x):
        return float(np.mean(x)) if x else None
    return {"evidence_mode":mode,"status":"paired_descriptive" if matched else "no_paired_evidence",
            "paired_players":matched,"played":played_count,"dnp":dnp_count,
            "paired_team_games":paired_team_games,"missing_actual_players":missing_actual,
            "unmatched_players":unmatched_players,"excluded_multiple_scenario_team_games":excluded_multiple,
            "models":{m:{"candidate_player_rows":coverage[m],
                         "mae":{k:avg(errors[m][k]) for k in METRICS},
                         "bias":{k:avg(bias[m][k]) for k in METRICS},
                         "interval_80_coverage":{k:avg(intervals[m][k]) for k in METRICS}}
                      for m in models},
            "limitations":"One predeclared scenario per team-game; not causal, not a deployment gate or an availability probability score."}
