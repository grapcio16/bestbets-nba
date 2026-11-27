"""Strict offline NBA CDN final-boxscore adapter; no requests or writes.

NBA identifiers are namespaced to prevent accidental joins with ESPN IDs.
The caller must supply a separately verified NBA schedule fixture and the
actual time the response was observed, never a reconstructed capture time.
"""
import re
from math import isfinite
import pandas as pd

NBA_GAME = re.compile(r"002[0-9]{7}")
NBA_PERSON = re.compile(r"[1-9][0-9]{0,15}")
DURATION = re.compile(r"PT(?:(\d+)M)?(?:(\d+(?:\.\d+)?)S)?")
TEAMS = frozenset("ATL BOS BKN CHA CHI CLE DAL DEN DET GSW HOU IND LAC LAL MEM MIA MIL MIN NOP NYK OKC ORL PHI PHX POR SAC SAS TOR UTA WAS".split())
FIELDS = {"PTS":"points", "REB":"reboundsTotal", "AST":"assists", "FG3M":"threePointersMade"}


def utc(value):
    t = pd.Timestamp(value)
    if pd.isna(t) or t.tzinfo is None:
        raise ValueError("explicit timezone required")
    return t.tz_convert("UTC")


def _game_id(value):
    if not isinstance(value, str) or not NBA_GAME.fullmatch(value):
        raise ValueError("NBA regular-season game ID required")
    return value


def _player_id(value):
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise ValueError("invalid NBA person ID")
    raw = str(value)
    if not NBA_PERSON.fullmatch(raw):
        raise ValueError("invalid NBA person ID")
    return "nba:" + raw


def _int(value, max_value):
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        raise ValueError("missing/non-numeric boxscore count")
    x = float(value)
    if not isfinite(x) or not x.is_integer() or not 0 <= x <= max_value:
        raise ValueError("invalid boxscore count")
    return int(x)


def _seconds(value):
    if not isinstance(value, str):
        raise ValueError("explicit NBA duration required")
    m = DURATION.fullmatch(value)
    if m is None or not any(m.groups()):
        raise ValueError("malformed NBA duration")
    minutes, seconds = m.groups()
    sec = float(seconds or 0)
    total = int(minutes or 0)*60+sec
    if not 0 <= sec < 60 or not 0 <= total <= 2880:
        raise ValueError("invalid regulation player minutes")
    return total


def parse_regulation_boxscore(payload, fixture, observed_at):
    """Atomic game validation; no partial logs on inconsistent totals.

    Explicit played=0 with no statistics may be archived as a DNP only when
    a final complete boxscore passes both team point/minute reconciliations.
    """
    if fixture.get("verified") is not True or fixture.get("provider") != "nba":
        raise ValueError("independent NBA fixture evidence required")
    gid = _game_id(fixture["game_id"])
    tip, observed = utc(fixture["start_utc"]), utc(observed_at)
    if observed < tip + pd.Timedelta(hours=4):
        raise ValueError("conservative final availability delay")
    game = payload["game"]
    if game.get("gameId") != gid or _int(game.get("gameStatus"), 3) != 3:
        raise ValueError("fixture mismatch or non-final boxscore")
    if _int(game.get("period"), 20) != 4:
        raise ValueError("regulation-only history")
    if utc(game["gameTimeUTC"]) != tip:
        raise ValueError("fixture tipoff mismatch")
    if fixture["home"] not in TEAMS or fixture["away"] not in TEAMS or fixture["home"] == fixture["away"]:
        raise ValueError("invalid fixture teams")
    results, ids = [], set()
    for side in ("home", "away"):
        team = game[side+"Team"]
        code = fixture[side]
        if team.get("teamTricode") != code:
            raise ValueError("fixture team mismatch")
        score = _int(team.get("score"), 200)
        if score != _int(fixture[side+"_score"], 200):
            raise ValueError("fixture score mismatch")
        if not isinstance(team.get("players"), list) or not team["players"]:
            raise ValueError("missing player boxscores")
        points, seconds = 0, 0.
        for p in team["players"]:
            pid = _player_id(p.get("personId"))
            if pid in ids:
                raise ValueError("duplicate player ID across fixture")
            ids.add(pid)
            played = p.get("played")
            if isinstance(played, bool) or str(played) not in ("0","1"):
                raise ValueError("explicit played flag required")
            played = str(played) == "1"
            stats = p.get("statistics")
            if not played and not stats:
                values, duration = dict.fromkeys(FIELDS,0), 0.
            else:
                if not isinstance(stats, dict):
                    raise ValueError("missing player statistics")
                duration = _seconds(stats.get("minutes"))
                values = {k:_int(stats.get(v),150) for k,v in FIELDS.items()}
            if (played and duration <= 0) or (not played and (duration or any(values.values()))):
                raise ValueError("played flag inconsistent with minutes/statistics")
            if values["FG3M"]*3 > values["PTS"]:
                raise ValueError("three-point count inconsistent")
            seconds += duration
            points += values["PTS"]
            results.append({"player_id":pid,"game_id":"nba:"+gid,"team":code,
                "start_utc":tip.isoformat(),"observed_at":observed.isoformat(),
                "final_verified":True,"regulation_only":True,
                "played":played,"minutes":duration/60,**values})
        # Permit small per-player clock rounding, but not missing minutes.
        if abs(seconds-14400) > 10 or points != score:
            raise ValueError("team minutes or points do not reconcile")
    if fixture["home_score"] == fixture["away_score"]:
        raise ValueError("tied final")
    return results
