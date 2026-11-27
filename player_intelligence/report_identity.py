"""Strict name-to-ID evidence adapter for normalized NBA report rows.

No fuzzy matching, cross-provider ID inference, live HTTP or PDF parsing.
The caller supplies independently verified complete team roster evidence.
Names are resolved only within that team's captured roster, with exact
Unicode-normalized name or explicit verified alias and unique identity.
"""
from collections import defaultdict
import unicodedata
from player_intelligence.nba_boxscore import TEAMS, _player_id, utc
from player_intelligence.rotation import STATUSES


def _name(value):
    if not isinstance(value,str) or not value.strip():
        raise ValueError("explicit player name required")
    value=" ".join(unicodedata.normalize("NFC",value).casefold().split())
    if "," in value:
        parts=value.split(",")
        if len(parts)!=2 or not all(p.strip() for p in parts):
            raise ValueError("ambiguous comma name")
        value=parts[1].strip()+" "+parts[0].strip()
    return value


def roster_index(roster):
    """Return exact normalized name candidates, never select among collisions."""
    team=roster.get("team")
    if team not in TEAMS or roster.get("complete_verified") is not True:
        raise ValueError("verified roster required")
    if utc(roster["published_at"])>utc(roster["captured_at"]):
        raise ValueError("roster published after capture")
    index=defaultdict(set)
    ids=set()
    for p in roster["players"]:
        if p.get("team")!=team or p.get("identity_verified") is not True:
            raise ValueError("unverified roster player")
        pid=_player_id(p["nba_person_id"])
        if pid in ids:
            raise ValueError("duplicate roster ID")
        ids.add(pid)
        index[_name(p["name"])].add(pid)
        for a in p.get("verified_aliases",()):
            if a.get("verified") is not True or not a.get("evidence_ref"):
                raise ValueError("unverified name alias")
            index[_name(a["name"])].add(pid)
    return index


def resolve_report(*, report, roster):
    """Normalize a whole verified team report or reject atomically.

    This adapter cannot prove completeness of an upstream PDF extractor.
    Evidence that the whole team section was extracted is mandatory.
    Output is compatible with build_snapshot.
    """
    if (report.get("verified") is not True or
            report.get("section_complete_verified") is not True or
            report.get("team")!=roster.get("team")):
        raise ValueError("verified complete matching team section required")
    report_pub,report_seen=utc(report["published_at"]),utc(report["captured_at"])
    if report_pub>report_seen or utc(roster["captured_at"])>report_seen:
        raise ValueError("invalid point-in-time identity evidence")
    index=roster_index(roster)
    submission=report.get("submission")
    if submission not in ("submitted","not_submitted"):
        raise ValueError("unknown submission status")
    raw=report["players"]
    if submission=="not_submitted" and raw:
        raise ValueError("not-submitted report contains players")
    result=[]
    seen=set()
    for row in raw:
        if row.get("team")!=report["team"]:
            raise ValueError("report player team mismatch")
        candidates=index.get(_name(row["player_name"]),set())
        if len(candidates)!=1:
            raise ValueError("unresolved or ambiguous report player")
        pid=next(iter(candidates))
        if pid in seen:
            raise ValueError("duplicate report player")
        seen.add(pid)
        status=row.get("status")
        if not isinstance(status,str) or status.strip().lower() not in STATUSES:
            raise ValueError("unknown report availability status")
        result.append({"nba_person_id":pid.removeprefix("nba:"),"team":report["team"],
                       "identity_verified":True,"status":status.strip().lower()})
    return {**{k:report[k] for k in ("game_id","home","away","start_utc","team",
             "published_at","captured_at","evidence_ref","submission")},
            "verified":True,"players":result}
