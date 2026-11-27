"""Research-only availability calibration on genuine pregame captures.

No status is fabricated from missing reports. DNP measures actual appearance
rather than injury cause. Calibration observations must be independently
validated; this module does not consume retrospective PDF name matches.
"""
from collections import defaultdict
from math import sqrt
import pandas as pd

from player_intelligence.rotation import _time, LEAD, MAX_STATUS_AGE, STATUSES

MIN_CASES = 50
MIN_GAMES = 20


def _wilson(success,n):
    p=success/n
    z=1.959963984540054
    d=1+z*z/n
    center=(p+z*z/(2*n))/d
    half=z*sqrt(p*(1-p)/n+z*z/(4*n*n))/d
    return [max(0.,center-half),min(1.,center+half)]


def calibrate_availability(*, observations, asof):
    """Estimate historical appearance frequency, not a live probability model.

    Input rows must have verified NBA IDs and explicit pregame status,
    forecast cutoff, publication/capture clocks, final explicit played flag
    and final observation timestamp. One predeclared case per player/game.
    """
    cutoff=_time(asof)
    seen=set()
    counts=defaultdict(lambda: [0,0,set()])
    rejected=defaultdict(int)
    for r in observations:
        if r.get("evidence_mode")!="prospective" or r.get("verified") is not True:
            rejected["unverified_or_replay"]+=1
            continue
        gid,pid=r.get("game_id"),r.get("player_id")
        if not isinstance(gid,str) or not gid.startswith("nba:") or not isinstance(pid,str) or not pid.startswith("nba:"):
            raise ValueError("verified NBA identity required")
        tip,clock,pub,capture,final=(_time(r[k]) for k in
             ("start_utc","forecast_asof","published_at","captured_at","final_observed_at"))
        if not clock-MAX_STATUS_AGE<=pub<=capture<=clock<tip-LEAD or not tip+pd.Timedelta(hours=4)<=final<=cutoff:
            rejected["invalid_or_unavailable_clock"]+=1
            continue
        status=r.get("status")
        if status not in STATUSES or status=="unknown" or type(r.get("played")) is not bool:
            rejected["unresolved_status_or_outcome"]+=1
            continue
        key=(gid,pid)
        if key in seen:
            raise ValueError("duplicate availability observation")
        seen.add(key)
        cell=counts[status]
        cell[0]+=1
        cell[1]+=int(r["played"])
        cell[2].add(gid)
    result={}
    for status in sorted(STATUSES-{"unknown"}):
        n,k,games=counts[status]
        adequate=n>=MIN_CASES and len(games)>=MIN_GAMES
        result[status]={"n":n,"played":k,"distinct_games":len(games),
            "historical_play_rate":k/n if adequate else None,
            "wilson_95_descriptive":_wilson(k,n) if adequate else None,
            "status":"research_estimate" if adequate else "insufficient_evidence"}
    return {"asof":cutoff.isoformat(),"groups":result,"rejected":dict(rejected),
            "apply_to_live_model":False,
            "limitations":"Unadjusted historical frequencies; Wilson intervals assume independent rows and do not account for game/player clustering. Require held-out prospective calibration before use."}
