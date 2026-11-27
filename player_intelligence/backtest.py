"""Offline chronological replay of *captured* pregame evidence.

A replay is not a prospective archived forecast and must not be pooled with
prospective results. Caller-provided captures cannot independently establish
source authenticity; their times and provenance must be audited.
"""
from copy import deepcopy
from player_intelligence.pipeline import run_research, forecast_envelopes
from player_intelligence.evaluation import evaluate_paired
from player_intelligence.rotation import VERSION, _time, LEAD
from player_intelligence.empirical import MODEL


def replay(*, cases, historical_logs, actuals, evaluation_asof, n=5000):
    """Freeze each case to original capture cutoff; no postgame scenario selection.

    Cases must contain fixture, asof, rosters, reports, assumptions and
    captured_at (when the complete pregame case was fixed). At most one
    case per game. Cases are supplied, not inferred from actual lineups.
    """
    cutoff=_time(evaluation_asof)
    cases=list(cases)
    history=list(historical_logs)
    actuals=list(actuals)
    ids=set()
    records=[]
    diagnostics=[]
    for c in sorted(cases,key=lambda x:_time(x["asof"])):
        f=c["fixture"]
        gid=f["game_id"]
        if gid in ids:
            raise ValueError("one predeclared case per game required")
        ids.add(gid)
        clock,captured,tip=_time(c["asof"]),_time(c["captured_at"]),_time(f["start_utc"])
        if not clock<=captured<tip-LEAD or captured>cutoff:
            raise ValueError("invalid captured replay case timing")
        # No retrospective roster/report resolution and no actual outcome input.
        # Filter the source observations *before* passing them to either model.
        available=[r for r in history if _time(r["observed_at"])<=clock
                   and _time(r["start_utc"])<clock]
        bundle=run_research(fixture=deepcopy(f),asof=clock,rosters=deepcopy(c["rosters"]),
              reports=deepcopy(c["reports"]),logs=available,assumptions=deepcopy(c["assumptions"]),n=n)
        # Replay envelope clocks simulate the captured case, not a real issuance.
        records.extend(forecast_envelopes(bundle,issued_at=captured,mode="captured_replay"))
        diagnostics.append({"game_id":gid,"asof":clock.isoformat(),"historical_rows":len(available),
              "teams":{t:{"baseline":v["baseline"]["status"],"empirical":v["empirical"]["status"]}
                       for t,v in bundle["teams"].items()}})
    results=evaluate_paired(forecasts=records,actuals=actuals,models=[VERSION,MODEL],asof=cutoff,mode="captured_replay")
    return {"evaluation_mode":"historical_captured_replay_not_prospective",
            "case_count":len(cases),"forecast_count":len(records),
            "diagnostics":diagnostics,"metrics":results,
            "limitations":"Replay only; source capture authenticity and parameter holdout must be audited independently."}
