"""Offline pregame snapshot contract; no provider fetching or identity guesses.

Inputs are normalized, independently verified source records, not raw PDF
rows. A future adapter must resolve source names to NBA person IDs with
auditable evidence, and capture publication and retrieval times separately.
A whole newer team report supersedes the previous one, including omissions.
"""
from hashlib import sha256
import json

from player_intelligence.nba_boxscore import TEAMS, _game_id, _player_id, utc
from player_intelligence.rotation import MAX_ROSTER_AGE, MAX_STATUS_AGE, LEAD, STATUSES


def _fixture(fixture, asof):
    if fixture.get("provider") != "nba" or fixture.get("verified") is not True:
        raise ValueError("verified NBA fixture required")
    gid = _game_id(fixture["game_id"])
    home, away = fixture["home"], fixture["away"]
    if home not in TEAMS or away not in TEAMS or home == away:
        raise ValueError("invalid fixture teams")
    tip, cutoff = utc(fixture["start_utc"]), utc(asof)
    if cutoff + LEAD >= tip:
        raise ValueError("pregame cutoff expired")
    return {"game_id":"nba:"+gid,"home":home,"away":away,"start_utc":tip.isoformat()}, cutoff


def _source_times(record, cutoff):
    published, captured = utc(record["published_at"]), utc(record["captured_at"])
    if published > captured:
        raise ValueError("publication after capture")
    if captured > cutoff:
        return None
    return published, captured


def _ref(record):
    ref = record.get("evidence_ref")
    if not isinstance(ref,str) or not ref.strip():
        raise ValueError("source evidence reference required")
    return ref


def _match(record, game):
    return (record.get("game_id") == game["game_id"] and
            record.get("home") == game["home"] and record.get("away") == game["away"]
            and utc(record["start_utc"]) == utc(game["start_utc"]))


def _roster(record, team, cutoff):
    if record.get("team") != team or record.get("complete_verified") is not True:
        raise ValueError("complete verified team roster required")
    times = _source_times(record,cutoff)
    if times is None or times[0] < cutoff-MAX_ROSTER_AGE:
        raise ValueError("stale or future roster")
    players = []
    for p in record["players"]:
        if p.get("team") != team or p.get("identity_verified") is not True:
            raise ValueError("unverified roster identity")
        players.append({"player_id":_player_id(p["nba_person_id"])})
    ids = [p["player_id"] for p in players]
    if len(ids) != len(set(ids)) or not 5 <= len(ids) <= 25:
        raise ValueError("invalid roster size or duplicate identity")
    return {"team":team,"complete_verified":True,"observed_at":times[1].isoformat(),
            "players":sorted(players,key=lambda p:p["player_id"])}


def build_snapshot(*, fixture, asof, rosters, reports):
    """Both team rosters, latest known whole reports, explicit status rows.

    No listed injury is equivalent to no observation, never available.
    A not-submitted or stale latest report supplies no resolved statuses.
    No raw medical details are retained in the research snapshot.
    """
    game,cutoff = _fixture(fixture,asof)
    teams = (game["home"],game["away"])
    if set(rosters) != set(teams):
        raise ValueError("both fixture rosters required")
    normalized = {t:_roster(rosters[t],t,cutoff) for t in teams}
    roster_ids = {t:{p["player_id"] for p in normalized[t]["players"]} for t in teams}
    if roster_ids[teams[0]] & roster_ids[teams[1]]:
        raise ValueError("player assigned to both teams")
    availability, diagnostics = [], {}
    for team in teams:
        candidates = []
        for r in reports:
            if r.get("team") != team or r.get("game_id") != game["game_id"]:
                continue
            if not _match(r,game):
                raise ValueError("report fixture identity mismatch")
            if r.get("verified") is not True:
                continue
            times = _source_times(r,cutoff)
            if times is not None:
                candidates.append((times[0],times[1],r))
        status, latest_ref, rows = "missing_report",None,[]
        if candidates:
            latest_pub=max(c[0] for c in candidates)
            latest=[c for c in candidates if c[0]==latest_pub]
            # Two independent interpretations of the same release must agree.
            signatures={json.dumps({"submission":c[2].get("submission"),
                                    "players":sorted(c[2].get("players",[]),
                                    key=lambda p:str(p.get("nba_person_id")) )},
                                   sort_keys=True) for c in latest}
            if len(signatures)!=1:
                raise ValueError("conflicting same-publication team reports")
            published,captured,r=max(latest,key=lambda c:c[1])
            latest_ref=_ref(r)
            submission=r.get("submission")
            if submission not in ("submitted","not_submitted"):
                raise ValueError("unknown report submission state")
            if submission=="not_submitted" and r.get("players"):
                raise ValueError("not-submitted report contains statuses")
            if published < cutoff-MAX_STATUS_AGE:
                status="stale_report"
            elif submission=="not_submitted":
                status="not_submitted"
            else:
                status="submitted"
                seen=set()
                for p in r["players"]:
                    if p.get("identity_verified") is not True or p.get("team")!=team:
                        raise ValueError("unverified report player identity")
                    pid=_player_id(p["nba_person_id"])
                    if pid not in roster_ids[team] or pid in seen:
                        raise ValueError("report player absent from roster or duplicated")
                    seen.add(pid)
                    value=p.get("status")
                    if value not in STATUSES:
                        raise ValueError("unsupported report player status")
                    rows.append({"player_id":pid,"team":team,"game_id":game["game_id"],
                                 "status":value,"observed_at":captured.isoformat(),
                                 "published_at":published.isoformat(),"verified":True})
        availability.extend(rows)
        resolved={p["player_id"] for p in rows if p["status"] in ("available","out")}
        diagnostics[team]={"report_state":status,"evidence_ref":latest_ref,
                           "roster_evidence_ref":_ref(rosters[team]),
                           "explicit_status_count":len(rows),
                           "unresolved_player_ids":sorted(roster_ids[team]-resolved)}
    result={"game":game,"asof":cutoff.isoformat(),"rosters":normalized,
            "availability":sorted(availability,key=lambda r:(r["team"],r["player_id"])),
            "diagnostics":diagnostics}
    result["snapshot_sha256"]=sha256(json.dumps(result,sort_keys=True,separators=(",",":")).encode()).hexdigest()
    return result
