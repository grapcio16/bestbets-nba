"""Research-only empirical rotation scenarios, player draws and impact audit.

No live provider, public UI, V7/V8 integration or database operations.
DNP is evidence of non-participation, not evidence of a specific injury.
"""
from collections import defaultdict
from hashlib import sha256
import numpy as np
import pandas as pd

from player_intelligence.rotation import (
    project_rotation, _allocate_minutes, _time, _number, MARKETS,
    MAX_PLAYER_MINUTES, TEAM_MINUTES,
)

MODEL = "player_intelligence_empirical_shadow_v02"
MIN_MATCHED = 3
PRIOR_GAMES = 8
MAX_GAMES = 30
MAX_DRAWS = 5000


def complete_history(logs, *, team, asof, exclude_game_id):
    """Only complete, observed regulation team games with explicit played flags."""
    cutoff = _time(asof)
    groups = defaultdict(list)
    for row in logs:
        if row.get("team") != team or row.get("game_id") == exclude_game_id:
            continue
        tip, observed = _time(row["start_utc"]), _time(row["observed_at"])
        if (row.get("final_verified") is not True or row.get("regulation_only") is not True
                or tip >= cutoff or observed > cutoff
                or observed < tip + pd.Timedelta(hours=4)):
            continue
        groups[row["game_id"]].append(row)
    result = []
    for gid, rows in groups.items():
        ids = [r.get("player_id") for r in rows]
        if (any(not isinstance(p,str) or not p for p in ids) or len(ids)!=len(set(ids))
                or len({_time(r["start_utc"]) for r in rows})!=1
                or not 5<=len(ids)<=25):
            continue
        try:
            parsed = {}
            for r in rows:
                m = _number(r["minutes"],48)
                stats = np.asarray([_number(r[k],150) for k in MARKETS])
                if (type(r.get("played")) is not bool or r["played"]!=(m>0)
                        or (m==0 and stats.any()) or stats[3]*3>stats[0]):
                    raise ValueError("invalid player outcome")
                parsed[r["player_id"]]=(m,stats)
            if abs(sum(m for m,_ in parsed.values())-TEAM_MINUTES)>10/60:
                continue
        except (KeyError,TypeError,ValueError):
            continue
        result.append({"game_id":gid,"tip":_time(rows[0]["start_utc"]),"players":parsed})
    return sorted(result,key=lambda g:(g["tip"],g["game_id"]))[-MAX_GAMES:]


def _scenario_games(history, active, inactive):
    required=set(active)|set(inactive)
    comparable=[g for g in history if required<=set(g["players"])]
    matched=[g for g in comparable if all(g["players"][p][0]==0 for p in inactive)]
    return comparable,matched


def simulate_players(*, game, team, asof, roster, logs, availability,
                     assume_active_ids=(), assume_out_ids=(), n=MAX_DRAWS):
    """Conditional empirical draws. Joint minute budget; no V8 score coupling."""
    if type(n) is not int or not 100<=n<=MAX_DRAWS:
        raise ValueError("research draws must be 100–5000")
    logs=list(logs)
    baseline=project_rotation(game=game,team=team,asof=asof,roster=roster,
                              logs=logs,availability=availability,
                              assume_active_ids=assume_active_ids,
                              assume_out_ids=assume_out_ids)
    if baseline["status"]!="shadow_conditional":
        return {"status":baseline["status"],"model_id":MODEL,"baseline":baseline}
    ids=[p["player_id"] for p in baseline["players"]]
    active=[p["player_id"] for p in baseline["players"] if p["minutes"]>0]
    inactive=[p for p in ids if p not in active]
    history=complete_history(logs,team=team,asof=asof,exclude_game_id=game["game_id"])
    comparable, matched=_scenario_games(history,active,inactive)
    if len(comparable)<MIN_MATCHED:
        return {"status":"insufficient_complete_rotation_history","model_id":MODEL,
                "comparable_games":len(comparable),"baseline":baseline}
    # Prefer observed same-absence games only when support is sufficient.
    use_matched=bool(inactive) and len(matched)>=MIN_MATCHED
    pool=matched if use_matched else comparable
    rates={}
    for pid in active:
        rows=[g["players"][pid] for g in comparable if g["players"][pid][0]>0]
        if len(rows)<MIN_MATCHED:
            return {"status":"insufficient_complete_player_history","model_id":MODEL,
                    "player_id":pid,"baseline":baseline}
        # Separate points from threes: coherent counting stats in every draw.
        rate=[]
        for minutes,stats in rows:
            p,r,a,t=stats
            rate.append(np.asarray([p-3*t,r,a,t])/minutes)
        rates[pid]=np.stack(rate)
    base=np.array([p["minutes"] for p in baseline["players"]],float)
    empirical=[]
    for g in pool:
        w=np.array([g["players"][p][0] if p in active else 0. for p in ids])
        if np.count_nonzero(w)*48>=240:
            empirical.append(_allocate_minutes(w))
    if len(empirical)<MIN_MATCHED:
        return {"status":"insufficient_feasible_historical_rotations","model_id":MODEL,
                "baseline":baseline}
    empirical=np.stack(empirical)
    shrink=len(empirical)/(len(empirical)+PRIOR_GAMES)
    # Stable seed from canonical IDs, clock and model. No final game result.
    key="|".join([MODEL,game["game_id"],team,_time(asof).isoformat(),*active,str(n)])
    rng=np.random.default_rng(int.from_bytes(sha256(key.encode()).digest()[:8],"big"))
    minutes=(1-shrink)*base+shrink*empirical[rng.integers(len(empirical),size=n)]
    # Rates are sampled as whole observed stat vectors to retain within-player dependence.
    draws=np.zeros((n,len(ids),5),dtype=np.int64)
    for j,pid in enumerate(ids):
        if pid not in rates:
            continue
        values=rates[pid][rng.integers(len(rates[pid]),size=n)]*minutes[:,j,None]
        rounded=np.floor(values).astype(np.int64)+(rng.random(values.shape)<(values%1))
        draws[:,j,0]=rounded[:,0]+3*rounded[:,3]
        draws[:,j,1:4]=rounded[:,1:4]
        draws[:,j,4]=draws[:,j,0]+draws[:,j,1]+draws[:,j,2]
    if not np.allclose(minutes.sum(axis=1),TEAM_MINUTES,atol=1e-7) or (minutes>48+1e-7).any():
        raise AssertionError("rotation budget violated")
    players=[]
    for j,pid in enumerate(ids):
        row={"player_id":pid,"availability":baseline["players"][j]["availability"]}
        for market,x in zip(("minutes",*MARKETS,"PRA"),(minutes[:,j],*draws[:,j,:].T)):
            row[market]={"mean":float(x.mean()),"p10":float(np.quantile(x,.1)),
                         "p50":float(np.quantile(x,.5)),"p90":float(np.quantile(x,.9))}
        players.append(row)
    return {"status":"shadow_conditional","model_id":MODEL,"game_id":game["game_id"],
            "team":team,"asof":_time(asof).isoformat(),"n":n,"players":players,
            "assumptions_used":baseline["assumptions_used"],
            "comparable_games":len(comparable),"same_absence_games":len(matched),
            "rotation_pool_games":len(empirical),"same_absence_used":use_matched,
            "empirical_weight":shrink,"team_minutes":float(minutes.sum(axis=1).mean()),
            "limitations":"Conditional, not calibrated play probabilities; historical DNP is not injury causality; no joint team-score or pace adjustment."}


def absence_impact(*, logs, team, player_id, asof, exclude_game_id):
    """Descriptive within-team scoring difference; never an automatic V8 adjustment."""
    games=complete_history(logs,team=team,asof=asof,exclude_game_id=exclude_game_id)
    present, absent=[],[]
    for g in games:
        if player_id not in g["players"]:
            continue
        points=float(sum(v[1][0] for v in g["players"].values()))
        (present if g["players"][player_id][0]>0 else absent).append(points)
    result={"team":team,"player_id":player_id,"played_games":len(present),
            "dnp_games":len(absent),"causal":False,"apply_to_v8":False}
    if min(len(present),len(absent))<MIN_MATCHED:
        return dict(result,status="insufficient_evidence")
    return dict(result,status="descriptive_only",
                played_mean_pts=float(np.mean(present)),dnp_mean_pts=float(np.mean(absent)),
                raw_dnp_minus_played_pts=float(np.mean(absent)-np.mean(present)),
                warning="Unadjusted scoring association; opponent, pace, concurrent absences and context are confounders.")
