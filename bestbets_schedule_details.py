"""Verified on-demand ESPN details for a FREE NBA schedule game.

No calls are made until a visitor expands a completed/live game.  The
scoreboard owns the event identity; browser-provided IDs are never authority.
"""
from __future__ import annotations

import math
import re

from teams import TEAM_FULL

_ALIASES = {"GS":"GSW", "NY":"NYK", "SA":"SAS", "NO":"NOP",
            "PHO":"PHX", "WSH":"WAS", "BRK":"BKN"}


def _code(competitor):
    team = competitor.get("team") or {}
    name = str(team.get("abbreviation") or "").upper()
    return _ALIASES.get(name, name)


def _integer(value, max_value=300):
    try:
        value = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return int(value) if math.isfinite(value) and value.is_integer() and 0 <= value <= max_value else None


def _stat_key(value):
    return re.sub(r"[^a-z0-9]", "", str(value or "").lower())


def _stat_value(block, names, *, percent=False):
    allowed = {_stat_key(name) for name in names}
    for item in (block.get("statistics") or []):
        if not isinstance(item, dict):
            continue
        keys = {_stat_key(item.get(field)) for field in ("name", "abbreviation", "label", "shortDisplayName")}
        if not (keys & allowed):
            continue
        raw = item.get("displayValue", item.get("value"))
        try:
            value = float(str(raw).strip().rstrip("%"))
        except (TypeError, ValueError, OverflowError):
            continue
        if not math.isfinite(value) or value < 0 or value > (100 if percent else 300):
            continue
        return f"{value:.1f}%" if percent else str(int(value)) if value.is_integer() else f"{value:.1f}"
    return None



# Stable ESPN team identifiers, not NBA Stats IDs; no user-supplied team IDs.
_ESPN_TEAM_IDS = {
    "ATL":1,"BOS":2,"BKN":17,"CHA":30,"CHI":4,"CLE":5,"DAL":6,"DEN":7,
    "DET":8,"GSW":9,"HOU":10,"IND":11,"LAC":12,"LAL":13,"MEM":29,
    "MIA":14,"MIL":15,"MIN":16,"NOP":3,"NYK":18,"OKC":25,"ORL":19,
    "PHI":20,"PHX":21,"POR":22,"SAC":23,"SAS":24,"TOR":28,"UTA":26,"WAS":27
}
_TEAM_SCHEDULE = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams/{id}/schedule"


def _team_sides(comp, away, home):
    rows=comp.get("competitors") or []
    if not isinstance(rows,list) or len(rows)!=2:
        return None
    by_side={row.get("homeAway"):row for row in rows if isinstance(row,dict)}
    if (set(by_side)!={"away","home"} or _code(by_side["away"])!=away
            or _code(by_side["home"])!=home):
        return None
    return by_side


def _periods_from_sides(by_side):
    """Verified per-quarter scores from a matched ESPN event (summary or scoreboard)."""
    if not by_side:
        return []
    aa=by_side["away"].get("linescores") or []
    hh=by_side["home"].get("linescores") or []
    if not isinstance(aa,list) or not isinstance(hh,list):
        return []
    quarters=[]
    for i in range(min(len(aa),len(hh),8)):
        a=aa[i] if isinstance(aa[i],dict) else {}
        h=hh[i] if isinstance(hh[i],dict) else {}
        av=_integer(a.get("value",a.get("displayValue")),90)
        hv=_integer(h.get("value",h.get("displayValue")),90)
        if av is None or hv is None:
            break
        quarters.append({"period": "Q"+str(i+1) if i<4 else "OT"+str(i-3),
                         "away":av,"home":hv})
    return quarters


def _periods_from_plays(payload):
    """Derive quarter deltas from ESPN-confirmed cumulative play scores only.

    A play's raw running totals are never interpreted as points *in* a quarter.
    For final games require their last play to match the official boxscore totals
    when both are known. Incomplete period data is not charted as a full period.
    """
    raw=payload.get("plays") if isinstance(payload,dict) else None
    if isinstance(raw,dict):
        raw=raw.get("plays") or raw.get("items")
    if not isinstance(raw,list):
        return []
    periods={}
    for play in raw:
        if not isinstance(play,dict):
            continue
        period=play.get("period")
        if isinstance(period,dict):
            period=period.get("number")
        try:
            period=int(period)
        except (ValueError,TypeError):
            continue
        if period<1 or period>8:
            continue
        a=_integer(play.get("awayScore"),300)
        h=_integer(play.get("homeScore"),300)
        if a is not None and h is not None:
            periods[period]=(a,h)
    if not periods:
        return []
    out=[]
    prev_a=prev_h=0
    for period in range(1,min(max(periods),8)+1):
        if period not in periods:
            break
        a,h=periods[period]
        if a<prev_a or h<prev_h:
            return []
        out.append({"period":"Q"+str(period) if period<=4 else "OT"+str(period-4),
                    "away":a-prev_a,"home":h-prev_h})
        prev_a,prev_h=a,h
    return out


def _verified_scoreboard_quarters(game_id, away, home, game_start):
    """One cached on-demand ESPN scoreboard date, anchored in US/Eastern."""
    from datetime import datetime
    from zoneinfo import ZoneInfo
    from sources import ESPN_SCOREBOARD, memoized_json
    if not isinstance(game_start,str) or not game_start:
        return []
    try:
        when=datetime.fromisoformat(game_start.replace("Z","+00:00"))
        if when.tzinfo is None:
            return []
        day=when.astimezone(ZoneInfo("America/New_York")).strftime("%Y%m%d")
    except (ValueError,TypeError):
        return []
    payload,_=memoized_json("bb-free-game-scoreboard-quarters-v1-"+day,
                             ESPN_SCOREBOARD,params={"dates":day,"limit":100},
                             ttl_seconds=180 if day == datetime.now(ZoneInfo("America/New_York")).strftime("%Y%m%d") else 86400,
                             request_timeout=6)
    for event in (payload.get("events") or []) if isinstance(payload,dict) else []:
        if not isinstance(event,dict) or str(event.get("id") or "")!=game_id:
            continue
        for comp in event.get("competitions") or []:
            if isinstance(comp,dict) and str(comp.get("id") or game_id)==game_id:
                matched=_team_sides(comp,away,home)
                if matched:
                    return _periods_from_sides(matched)
    return []


def _verified_schedule_event(event):
    """One genuinely final ESPN schedule result, with both teams and scores."""
    if not isinstance(event,dict):
        return None
    comps=event.get("competitions") or []
    comp=comps[0] if isinstance(comps,list) and comps and isinstance(comps[0],dict) else None
    if not comp:
        return None
    eid=str(event.get("id") or "")
    if not re.fullmatch(r"\d{6,15}",eid) or str(comp.get("id") or eid)!=eid:
        return None
    status=(event.get("status") or {}).get("type") or (comp.get("status") or {}).get("type") or {}
    if not (status.get("completed") is True or status.get("state")=="post"):
        return None
    sides={c.get("homeAway"):c for c in comp.get("competitors") or [] if isinstance(c,dict)}
    if set(sides)!={"away","home"}:
        return None
    ac=_code(sides["away"]);hc=_code(sides["home"])
    if ac not in TEAM_FULL or hc not in TEAM_FULL or ac==hc:
        return None
    def score(side):
        value=sides[side].get("score")
        if isinstance(value,dict):
            value=value.get("value",value.get("displayValue"))
        return _integer(value,300)
    a=score("away");h=score("home")
    start=str(event.get("date") or comp.get("date") or "")
    if a is None or h is None or not start:
        return None
    return {"id":eid,"start":start,"away":ac,"home":hc,
            "away_score":a,"home_score":h,"state":"final"}


def fetch_game_history(away, home, selected_start, selected_id):
    """Only on demand: up to two ESPN seasons for H2H, current for both teams.

    History is not inferred from the short daily Centrum cache. Each returned
    event is verified as completed with a score, two team identities and date.
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from datetime import datetime
    from sources import memoized_json
    if away not in _ESPN_TEAM_IDS or home not in _ESPN_TEAM_IDS:
        return {"h2h":[],"recent":[],"coverage":[],"error":"Brak rozpoznanych drużyn ESPN"}
    try:
        when=datetime.fromisoformat(str(selected_start).replace("Z","+00:00"))
        if when.tzinfo is None:
            raise ValueError("no timezone")
    except (ValueError,TypeError):
        return {"h2h":[],"recent":[],"coverage":[],"error":"Brak daty spotkania"}
    season=when.year+1 if when.month>=7 else when.year
    cutoff=when.timestamp()
    requests=[(away,season),(home,season),(away,season-1)]
    def fetch(team,year):
        url=_TEAM_SCHEDULE.format(id=_ESPN_TEAM_IDS[team])
        response,_=memoized_json(
            "bb-free-team-history-v1-"+team+"-"+str(year),url,
            params={"season":year,"limit":150},
            ttl_seconds=7200 if year==season else 86400,
            request_timeout=7)
        if not isinstance(response,dict) or not isinstance(response.get("events"),list):
            raise ValueError("Nieprawidłowa historia ESPN")
        return response["events"]
    by_id={}
    successful=[]
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures={pool.submit(fetch,*req):req for req in requests}
        for future in as_completed(futures):
            team,year=futures[future]
            try:
                events=future.result()
                successful.append({"team":team,"season":year})
                for event in events:
                    game=_verified_schedule_event(event)
                    if game is None or game["id"]==selected_id:
                        continue
                    try:
                        ts=datetime.fromisoformat(game["start"].replace("Z","+00:00")).timestamp()
                    except (ValueError,TypeError):
                        continue
                    if ts<cutoff and (team in (game["away"],game["home"])):
                        by_id[game["id"]]=game
            except Exception:
                continue
    games=list(by_id.values())
    games.sort(key=lambda g:g["start"],reverse=True)
    head=[g for g in games if {g["away"],g["home"]}=={away,home}][:6]
    recent={team:[g for g in games if team in (g["away"],g["home"])][:4] for team in (away,home)}
    return {"h2h":head,"recent":recent,"coverage":successful,
            "error":"" if successful else "Historia spotkań ESPN jest chwilowo niedostępna"}

def parse_game_details(payload, game_id, away, home):
    """Parse only teams and statistics verified against the selected event."""
    if not isinstance(payload, dict) or away not in TEAM_FULL or home not in TEAM_FULL or away == home:
        raise ValueError("Nieprawidłowy mecz")
    header = payload.get("header") or {}
    competitions = header.get("competitions") or []
    comp = competitions[0] if isinstance(competitions, list) and competitions else {}
    if str(header.get("id") or "") != game_id or str(comp.get("id") or "") != game_id:
        raise ValueError("ESPN zwrócił inny mecz")
    competitors = comp.get("competitors") or []
    if not isinstance(competitors, list) or len(competitors) != 2:
        raise ValueError("Brak potwierdzonych drużyn")
    by_side = {c.get("homeAway"): c for c in competitors if isinstance(c, dict)}
    if set(by_side) != {"home", "away"} or _code(by_side["away"]) != away or _code(by_side["home"]) != home:
        raise ValueError("Niezgodne drużyny meczu")
    quarters = _periods_from_sides(by_side)
    if not quarters:
        quarters = _periods_from_plays(payload)
    boxscore = payload.get("boxscore") or {}
    team_blocks = {}
    for block in boxscore.get("teams") or []:
        if not isinstance(block, dict):
            continue
        code = _code(block)
        if code in (away, home):
            team_blocks[code] = block
    metrics = [
        ("Celne z gry %", ("fieldGoalPct", "fieldGoalPercentage", "FG%"), True),
        ("Za 3 punkty %", ("threePointFieldGoalPct", "threePointFieldGoalPercentage", "3P%"), True),
        ("Rzuty wolne %", ("freeThrowPct", "freeThrowPercentage", "FT%"), True),
        ("Zbiórki", ("totalRebounds", "rebounds", "REB"), False),
        ("Zbiórki w ataku", ("offensiveRebounds", "offRebounds", "OREB"), False),
        ("Asysty", ("assists", "AST"), False),
        ("Bloki", ("blocks", "BLK"), False),
        ("Przechwyty", ("steals", "STL"), False),
        ("Straty", ("totalTurnovers", "turnovers", "TO"), False),
        ("Faule", ("fouls", "personalFouls", "PF"), False),
    ]
    team_stats = []
    if away in team_blocks and home in team_blocks:
        for label, names, percent in metrics:
            a = _stat_value(team_blocks[away], names, percent=percent)
            h = _stat_value(team_blocks[home], names, percent=percent)
            if a is not None and h is not None:
                team_stats.append({"label":label, "away":a, "home":h})
    # Reuse the established parser; it rejects DNP and incomplete PTS/REB/AST.
    from espn_player_data import parse_summary
    rows = parse_summary(payload, {"game_id":game_id, "away":away, "home":home, "start_utc":comp.get("date") or ""})
    leaders = {}
    for side, code in (("away", away), ("home", home)):
        athletes = [row for row in rows if row.get("TEAM_ABBREVIATION") == code
                    and all(_integer(row.get(stat), 150) is not None for stat in ("PTS", "REB", "AST"))]
        athletes.sort(key=lambda row: (-int(row["PTS"]), -int(row["REB"]), str(row.get("PLAYER_NAME") or "")))
        leaders[side] = [{"name":str(p["PLAYER_NAME"])[:75],
                          "pts":int(p["PTS"]), "reb":int(p["REB"]), "ast":int(p["AST"])}
                         for p in athletes[:3]]
    # Arena is only displayed when confirmed in the matching ESPN summary.
    venue = comp.get("venue") or (payload.get("gameInfo") or {}).get("venue") or {}
    arena = str(venue.get("fullName") or "").strip()[:110] if isinstance(venue, dict) else ""
    return {"id":game_id, "away":away, "home":home,
            "quarters":quarters, "team_stats":team_stats, "leaders":leaders,
            "arena":arena, "source":"ESPN"}



def load_scheduled_game_history(game_id, away, home, game_start):
    """A scheduled fixture has no box score; only its verified history is fetched.

    The caller first verifies the event ID, date, teams and scheduled state against
    its trusted server-side ESPN fixture. This function accepts no arbitrary URL.
    """
    from datetime import datetime
    if not re.fullmatch(r"\\d{6,15}", str(game_id)):
        raise ValueError("Nieobsługiwany mecz")
    if away not in TEAM_FULL or home not in TEAM_FULL or away == home:
        raise ValueError("Nieprawidłowe drużyny")
    try:
        start=datetime.fromisoformat(str(game_start).replace("Z","+00:00"))
        if start.tzinfo is None:
            raise ValueError("Brak strefy czasowej")
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("Nieprawidłowa data meczu") from exc
    try:
        history=fetch_game_history(away,home,str(game_start),str(game_id))
    except Exception:
        history={"h2h":[],"recent":{},"coverage":[],
                 "error":"Historia spotkań ESPN jest chwilowo niedostępna"}
    return {"id":str(game_id),"away":away,"home":home,"pregame":True,
            "quarters":[],"team_stats":[],"leaders":{"away":[],"home":[]},
            "history":history,"source":"ESPN"}


def load_game_details(game_id, away, home, state):
    """Fetch a single, already-verified scoreboard event after explicit click."""
    if not re.fullmatch(r"\d{6,15}", str(game_id)) or state not in ("live", "final"):
        raise ValueError("Nieobsługiwany mecz")
    if away not in TEAM_FULL or home not in TEAM_FULL or away == home:
        raise ValueError("Nieprawidłowe drużyny")
    from espn_player_data import ESPN_SUMMARY
    from sources import memoized_json
    payload, meta = memoized_json("bb-free-schedule-summary-v1-"+game_id,
                                  ESPN_SUMMARY,params={"event":game_id},
                                  ttl_seconds=45 if state=="live" else 3600,
                                  request_timeout=7)
    result = parse_game_details(payload, game_id, away, home)
    if not result["quarters"]:
        try:
            game_start=((payload.get("header") or {}).get("competitions") or [{}])[0].get("date")
            result["quarters"]=_verified_scoreboard_quarters(game_id,away,home,game_start)
        except Exception:
            pass
    try:
        game_start=((payload.get("header") or {}).get("competitions") or [{}])[0].get("date")
        result["history"]=fetch_game_history(away,home,game_start,game_id)
    except Exception:
        result["history"]={"h2h":[],"recent":{},"coverage":[],"error":"Historia ESPN jest chwilowo niedostępna"}
    result["stale"] = bool(meta.get("stale"))
    return result
