"""Offline orchestration of verified pregame snapshot and both research models."""
from copy import deepcopy
from hashlib import sha256
import json

from player_intelligence.pregame_snapshot import build_snapshot
from player_intelligence.rotation import project_rotation, _time, LEAD
from player_intelligence.empirical import simulate_players, absence_impact


def run_research(*, fixture, asof, rosters, reports, logs, assumptions, n=5000):
    """One predeclared scenario per team; no actual outcomes or live writes."""
    snap=build_snapshot(fixture=fixture,asof=asof,rosters=rosters,reports=reports)
    logs=list(logs)
    game=snap["game"]
    if set(assumptions)!=set(snap["rosters"]):
        raise ValueError("explicit scenario inputs for both teams required")
    results={}
    for team,roster in snap["rosters"].items():
        a=assumptions[team]
        active=sorted(a.get("assume_active_ids",()))
        out=sorted(a.get("assume_out_ids",()))
        key={"snapshot":snap["snapshot_sha256"],"team":team,"active":active,"out":out}
        scenario=sha256(json.dumps(key,sort_keys=True).encode()).hexdigest()
        args=dict(game=game,team=team,asof=snap["asof"],roster=roster,
                  logs=logs,availability=snap["availability"],
                  assume_active_ids=active,assume_out_ids=out)
        baseline=project_rotation(**args)
        empirical=simulate_players(**args,n=n)
        absence_ids=[p["player_id"] for p in baseline.get("players",[]) if p["minutes"]==0]
        results[team]={"scenario_id":scenario,"baseline":baseline,"empirical":empirical,
                       "absence_audit":[absence_impact(logs=logs,team=team,player_id=pid,
                             asof=snap["asof"],exclude_game_id=game["game_id"]) for pid in absence_ids]}
    return {"snapshot":snap,"teams":results,"deployment":"research_only"}


def forecast_envelopes(bundle, *, issued_at):
    """Return serializable records for a future append-only research archive.

    The caller must supply actual observed issue time; this function does
    not attest its authenticity or persist any records.
    """
    issued=_time(issued_at)
    snap=bundle["snapshot"]
    tip=_time(snap["game"]["start_utc"])
    if not _time(snap["asof"])<=issued<tip-LEAD:
        raise ValueError("forecast issuance outside pregame window")
    records=[]
    for team, result in bundle["teams"].items():
        for name in ("baseline","empirical"):
            p=result[name]
            if p.get("status")!="shadow_conditional":
                continue
            if (p.get("team")!=team or p.get("game_id")!=snap["game"]["game_id"]
                    or _time(p["asof"])!=_time(snap["asof"])):
                raise ValueError("projection identity mismatch")
            envelope={"start_utc":tip.isoformat(),"issued_at":issued.isoformat(),
                      "scenario_id":result["scenario_id"],"snapshot_sha256":snap["snapshot_sha256"],
                      "projection":deepcopy(p)}
            envelope["record_sha256"]=sha256(json.dumps(envelope,sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest()
            records.append(envelope)
    return records
