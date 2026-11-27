"""Read-only NBA CDN schedule/boxscore adapter for isolated research.

No credentials, production DB, background scheduling, or fallback fabrication.
Capture times are recorded only after a successful HTTP response. NBA source
availability and use rights are not guaranteed. No injury/roster inference
from a postgame roster.
"""
from dataclasses import dataclass
from hashlib import sha256
import json
import pandas as pd
import requests

from player_intelligence.nba_boxscore import TEAMS, NBA_GAME, _int, utc, parse_regulation_boxscore

SCHEDULE = "https://cdn.nba.com/static/json/staticData/scheduleLeagueV2.json"
BOX = "https://cdn.nba.com/static/json/liveData/boxscore/boxscore_{}.json"
MAX_BYTES = 25_000_000


@dataclass(frozen=True)
class Capture:
    payload: dict
    observed_at: str
    evidence_ref: str


def capture_json(url, *, session=None, clock=None):
    """Only approved fixed CDN endpoints; no redirected or arbitrary URLs."""
    import re
    if url != SCHEDULE and not re.fullmatch(
            r"https://cdn\.nba\.com/static/json/liveData/boxscore/boxscore_002[0-9]{7}\.json",url):
        raise ValueError("unapproved research endpoint")
    requester=session or requests
    clock=clock or (lambda:pd.Timestamp.now(tz="UTC"))
    with requester.get(url,timeout=(5,15),allow_redirects=False,stream=True,
                       headers={"Accept":"application/json","User-Agent":"Hoopzaro-research/0.1"}) as response:
        if response.status_code!=200:
            raise ValueError(f"NBA CDN HTTP {response.status_code}")
        chunks=[]
        size=0
        for chunk in response.iter_content(chunk_size=65536):
            size+=len(chunk)
            if size>MAX_BYTES:
                raise ValueError("source response too large")
            chunks.append(chunk)
        raw=b"".join(chunks)
    observed=utc(clock()).isoformat()
    payload=json.loads(raw)
    if not isinstance(payload,dict):
        raise ValueError("unexpected CDN payload")
    return Capture(payload,observed,url+"#sha256="+sha256(raw).hexdigest())


def schedule_finals(capture, *, season_prefix, asof):
    """Verified NBA regular-season fixture candidates from schedule source.

    season_prefix e.g. '00226' for 2026–27. Reject other game types,
    unfinished games, duplicate fixture IDs and missing explicit timestamps.
    """
    if not isinstance(season_prefix,str) or len(season_prefix)!=5 or not season_prefix.startswith("002") or not season_prefix.isdigit():
        raise ValueError("explicit regular season prefix required")
    cutoff=utc(asof)
    observed=utc(capture.observed_at)
    if observed>cutoff:
        raise ValueError("future schedule capture")
    root=capture.payload["leagueSchedule"]
    games={}
    for date in root["gameDates"]:
        for g in date["games"]:
            gid=g.get("gameId")
            if not isinstance(gid,str) or not NBA_GAME.fullmatch(gid) or not gid.startswith(season_prefix):
                continue
            if _int(g.get("gameStatus"),3)!=3:
                continue
            tip=utc(g["gameDateTimeUTC"])
            if tip+pd.Timedelta(hours=4)>observed:
                continue
            h,a=g["homeTeam"],g["awayTeam"]
            home,away=h["teamTricode"],a["teamTricode"]
            hs,aws=_int(h["score"],200),_int(a["score"],200)
            if home not in TEAMS or away not in TEAMS or home==away or hs==aws or min(hs,aws)<=0:
                raise ValueError("invalid schedule final")
            fixture={"provider":"nba","verified":True,"game_id":gid,"home":home,"away":away,
                     "start_utc":tip.isoformat(),"home_score":hs,"away_score":aws,
                     "schedule_observed_at":observed.isoformat(),"schedule_evidence_ref":capture.evidence_ref}
            if gid in games:
                raise ValueError("duplicate schedule fixture")
            games[gid]=fixture
    return sorted(games.values(),key=lambda g:(g["start_utc"],g["game_id"]),reverse=True)


def collect_recent(*, season_prefix, limit=1, session=None, clock=None):
    """Bounded diagnostic only; return accepted rows and explicit rejection reasons."""
    if type(limit) is not int or not 1<=limit<=10:
        raise ValueError("diagnostic limit 1–10")
    clock=clock or (lambda:pd.Timestamp.now(tz="UTC"))
    schedule=capture_json(SCHEDULE,session=session,clock=clock)
    fixtures=schedule_finals(schedule,season_prefix=season_prefix,asof=clock())[:limit]
    accepted,rejected=[],[]
    for f in fixtures:
        try:
            capture=capture_json(BOX.format(f["game_id"]),session=session,clock=clock)
            rows=parse_regulation_boxscore(capture.payload,f,capture.observed_at)
            for row in rows:
                row["boxscore_evidence_ref"]=capture.evidence_ref
                row["schedule_evidence_ref"]=schedule.evidence_ref
            accepted.extend(rows)
        except (ValueError,KeyError,TypeError,requests.RequestException) as exc:
            rejected.append({"game_id":f["game_id"],"reason":type(exc).__name__+": "+str(exc)[:180]})
    return {"selected":len(fixtures),"accepted_games":len({r["game_id"] for r in accepted}),
            "accepted_player_rows":len(accepted),"rejected":rejected,"rows":accepted}
