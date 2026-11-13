"""Fast, verified data feed for the FREE BestBets Centrum.

Only one small ESPN scoreboard range request is needed for the live ticker,
daily fixtures, latest final scores, team form and players' RECENT verified
boxscore leaders. No bookmaker odds, guessed player props or simulated tips.
"""
from __future__ import annotations

from datetime import timedelta
import math
import pandas as pd


def _value(x):
    try:
        n=float(x)
        return round(n,1) if math.isfinite(n) and n>=0 else None
    except (TypeError,ValueError,OverflowError):
        return None


def extract_recent_leaders(payload, now=None, limit=3):
    """One verified leader per PTS, REB and AST from the latest final NBA date.

    This free section is NOT a sample prop line, multi-game model or betting
    recommendation. Only ESPN scoreboard-reported individual game values count.
    """
    now=pd.Timestamp(now) if now is not None else pd.Timestamp.now(tz="Europe/Warsaw")
    if now.tzinfo is None:
        now=now.tz_localize("Europe/Warsaw")
    else:
        now=now.tz_convert("Europe/Warsaw")

    allowed={"points":"PTS","rebounds":"REB","assists":"AST"}
    aliases={"GS":"GSW","NY":"NYK","SA":"SAS","NO":"NOP",
             "PHO":"PHX","WSH":"WAS","BRK":"BKN","UTAH":"UTA"}
    max_value={"PTS":100,"REB":55,"AST":35}
    candidates=[]
    for event in (payload.get("events",[]) if isinstance(payload,dict) else []):
        if not isinstance(event,dict):
            continue
        status=(event.get("status") or {}).get("type") or {}
        comp=(event.get("competitions") or [{}])[0]
        if not isinstance(comp,dict):
            continue
        completed=bool(status.get("completed") or
                       ((comp.get("status") or {}).get("type") or {}).get("completed"))
        if not completed:
            continue
        when=pd.to_datetime(event.get("date"),utc=True,errors="coerce")
        if pd.isna(when) or when>now.tz_convert("UTC"):
            continue
        competitors=[item for item in comp.get("competitors") or [] if isinstance(item,dict)]
        if len(competitors)!=2:
            continue
        for item in competitors:
            team=str((item.get("team") or {}).get("abbreviation") or "").upper()
            if not team:
                continue
            rival=next((other for other in competitors if other is not item),None)
            opp=str(((rival or {}).get("team") or {}).get("abbreviation") or "").upper()
            team=aliases.get(team,team)
            opp=aliases.get(opp,opp)
            home_away=str(item.get("homeAway") or "").lower()
            if not opp or home_away not in ("home","away"):
                continue
            for group in item.get("leaders") or []:
                if not isinstance(group,dict):
                    continue
                label=str(group.get("name") or group.get("abbreviation") or "").lower()
                label=label.replace(" ","").replace("-","")
                market=allowed.get(label)
                if not market:
                    continue
                for leader in group.get("leaders") or []:
                    if not isinstance(leader,dict):
                        continue
                    athlete=leader.get("athlete") or {}
                    if not isinstance(athlete,dict):
                        continue
                    name=str(athlete.get("displayName") or athlete.get("fullName") or "").strip()
                    ident=str(athlete.get("id") or "").strip()
                    amount=_value(leader.get("value"))
                    if (not name or len(name)>70 or amount is None or
                            amount>max_value[market] or not amount.is_integer()):
                        continue
                    candidates.append({
                        "name":name,"team":team[:4],"opponent":opp[:4],
                        "home_away":home_away,"market":market,
                        "value":int(amount),"date":when.tz_convert("Europe/Warsaw").date().isoformat(),
                        "event_date":when.isoformat(),
                        "game_id":str(event.get("id") or "")[:20],
                        "athlete_id":ident[:20],
                    })
    if not candidates:
        return []
    # Never label several previous-day games as today's leaders.
    recent_day=max(item["date"] for item in candidates)
    winners=[]
    for market in ("PTS","REB","AST"):
        possible=[item for item in candidates if
                  item["date"]==recent_day and item["market"]==market]
        if possible:
            # Highest reported result wins; latest game wins equal values.
            winners.append(max(possible,key=lambda item:(
                item["value"],item["event_date"],item["athlete_id"])))
    return winners[:limit]


def get_free_leader_boxscore(leader):
    """Load ONE completed game's verified boxscore on click, never a season model.

    The caller must select 'leader' from the server-side snapshot, not from
    untrusted client-provided athlete names or remote URLs.
    """
    from espn_player_data import fetch_boxscore
    game_id=str(leader.get("game_id") or "")
    player_id=str(leader.get("athlete_id") or "")
    team=str(leader.get("team") or "")
    opponent=str(leader.get("opponent") or "")
    home_away=leader.get("home_away")
    if (not game_id.isdigit() or len(game_id)>10 or
            not player_id.isdigit() or len(player_id)>20 or
            not team or not opponent or home_away not in ("home","away")):
        raise ValueError("Brak zweryfikowanego identyfikatora meczu lub zawodnika.")
    game={
        "game_id":game_id,"start_utc":leader.get("event_date"),
        "away":team if home_away=="away" else opponent,
        "home":team if home_away=="home" else opponent,
    }
    rows=fetch_boxscore(game)
    found=[row for row in rows if
           str(row.get("PLAYER_ID") or "")==player_id and
           row.get("TEAM_ABBREVIATION")==team]
    if len(found)!=1:
        raise ValueError("ESPN nie udostępnił pełnego, potwierdzonego boxscore zawodnika.")
    row=found[0]
    result={"name":leader["name"],"team":team,"opponent":opponent,
            "date":leader["date"],"market":leader["market"],
            "leader_value":leader["value"],"verified":True}
    for source,target in (("PTS","PTS"),("REB","REB"),("AST","AST"),("FG3M","3PM")):
        value=_value(row.get(source))
        if value is None or not value.is_integer():
            raise ValueError("Niekompletne statystyki ESPN. Brak potwierdzonych danych.")
        result[target]=int(value)
    if result[leader["market"]] != leader["value"]:
        raise ValueError("Wartości ESPN leaderboard i boxscore nie są zgodne.")
    return result


def get_centre_live_data(now=None):
    """Fetch actual NBA dates individually: the multi-day ESPN range can fail.

    The upstream's YYYYMMDD single-day scoreboard is confirmed accessible
    from GitHub runners. Limit concurrency, cache each date separately,
    preserve source failures, and never synthesize missing matches.
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from sources import (ESPN_SCOREBOARD, NBA_CDN_SCHEDULE, memoized_json,
                         parse_espn_schedule, parse_nba_schedule)
    from team_logos import logo_data_uri
    from bestbets_centre_data import build_centre_snapshot
    from bestbets_centre_standings import fetch_season_standings, apply_season_form

    now=pd.Timestamp(now) if now is not None else pd.Timestamp.now(tz="Europe/Warsaw")
    now=now.tz_localize("Europe/Warsaw") if now.tzinfo is None else now.tz_convert("Europe/Warsaw")
    # 6 days of results plus 4 future days cover the free dashboard's
    # results, today's games and the next fixtures without huge range calls.
    offsets=list(range(-6,5))
    dates=[(now+timedelta(days=i)).strftime("%Y%m%d") for i in offsets]
    failures=[]
    season_records=None
    season_meta=None

    def fetch_day(offset, day):
        ttl=120 if offset in (-1,0,1) else 7200 if offset < -1 else 1800
        raw,meta=memoized_json(
            "bb-centre-espn-daily-r2-"+day,ESPN_SCOREBOARD,
            params={"dates":day,"limit":100},
            ttl_seconds=ttl,request_timeout=6,
        )
        if not isinstance(raw,dict) or not isinstance(raw.get("events"),list):
            raise ValueError("ESPN nie zwróciło rozpoznawalnej listy spotkań")
        return day,raw["events"],meta

    try:
        events_by_id={}
        successes=0
        succeeded_days=set()
        any_stale=False
        # Bounded parallel requests; no session state or Streamlit APIs in
        # worker threads. Each date has its own disk-cache key.
        with ThreadPoolExecutor(max_workers=5) as pool:
            # Season W-L is fetched independently from the short scoreboard.
            # A standings timeout must not block games, results or player cards.
            season_future=pool.submit(fetch_season_standings)
            futures={pool.submit(fetch_day,offset,day):day for offset,day in zip(offsets,dates)}
            for future in as_completed(futures):
                try:
                    day,events,meta=future.result()
                    successes+=1
                    succeeded_days.add(day)
                    any_stale|=bool(meta.get("stale"))
                    for event in events:
                        if not isinstance(event,dict):continue
                        event_id=str(event.get("id") or event.get("uid") or "")
                        if event_id:
                            events_by_id[event_id]=event
                except Exception as exc:
                    failures.append(type(exc).__name__)
            try:
                season_records,season_meta=season_future.result()
            except Exception:
                # Do not misrepresent the 6-day scoreboard as season-long data.
                season_records=None
                season_meta=None
        if successes:
            raw={"events":list(events_by_id.values())}
            table=parse_espn_schedule(raw)
            snap=build_centre_snapshot(
                table,{"source":"ESPN — rzeczywiste mecze NBA"},now=now,
                logo_provider=logo_data_uri,
            )
            if not events_by_id:
                # Successful empty days can be a legitimate NBA off-day.
                snap["error"]=""
            snap["players"]=extract_recent_leaders(raw,now=now,limit=3)
            snap["coverage"]="Zweryfikowane dni "+dates[0]+"–"+dates[-1]
            snap["stale"]=bool(any_stale or failures)
            snap["fetched_at"]=now.strftime("%Y-%m-%d %H:%M %Z")
            snap["coverage_days"]=successes
            apply_season_form(snap,season_records,season_meta)
            # A Warsaw day can include games belonging to the previous
            # US/ESPN scoreboard day. Mark it as covered only after BOTH
            # source dates returned successfully.
            snap["calendar_loaded_days"]=[
                (now+timedelta(days=i)).date().isoformat()
                for i in offsets
                if i > offsets[0] and dates[i-offsets[0]] in succeeded_days
                and dates[i-offsets[0]-1] in succeeded_days
            ]
            if failures:
                snap["warning"]=(
                    "Niepełne dane: pobrano "+str(successes)+"/"+str(len(dates))+
                    " dni ESPN. Brakujące dni pominięto."
                )
            return snap
        raise RuntimeError("Żaden dzienny raport ESPN nie odpowiedział")
    except Exception as exc:
        failures.append(type(exc).__name__)

    # Official CDN is a last resort: it returned HTTP 403 in GitHub CI,
    # but can still work from other networks or return a cached season.
    try:
        raw,meta=memoized_json(
            "bb-centre-nba-cdn-r1",NBA_CDN_SCHEDULE,
            ttl_seconds=600,request_timeout=7
        )
        table=parse_nba_schedule(raw)
        if table is None or table.empty:
            raise ValueError("Pusty zapasowy terminarz NBA CDN")
        meta={**meta,"source":"NBA CDN — oficjalny terminarz zapasowy"}
        snap=build_centre_snapshot(table,meta,now=now,logo_provider=logo_data_uri)
        apply_season_form(snap,season_records,season_meta)
        snap["players"]=[]
        snap["calendar_loaded_days"]=[
            (now+timedelta(days=i)).date().isoformat() for i in range(-7,8)
        ]
        snap["coverage"]="Źródło zapasowe — bez liderów zawodników"
        snap["stale"]=bool(meta.get("stale"))
        snap["fetched_at"]=meta.get("timestamp") or snap["as_of"]
        return snap
    except Exception as exc:
        failures.append(type(exc).__name__)
        empty=build_centre_snapshot(pd.DataFrame(),{"source":"NBA / ESPN"},now=now)
        apply_season_form(empty,season_records,season_meta)
        empty["players"]=[]
        empty["stale"]=True
        empty["coverage"]="Brak dostępnych danych"
        labels=("ESPN: "+failures[0], "NBA CDN: "+failures[-1])
        empty["error"]=(
            "Nie udało się pobrać danych NBA ("+", ".join(labels)+"). "
            "Spróbuj odświeżyć Centrum."
        )
        return empty



def get_centre_day_data(day):
    """Load one requested Warsaw-local calendar day via two ESPN scoreboard dates.

    Each local date can span two ESPN US match days; only confirmed games
    whose start is within that Warsaw date are displayed. Cache individual
    sources using existing memoized_json. Supports browsing beyond the
    initial 11-day snapshot without querying the entire season.
    """
    from datetime import date
    from concurrent.futures import ThreadPoolExecutor
    from sources import ESPN_SCOREBOARD, memoized_json, parse_espn_schedule
    from bestbets_centre_data import build_centre_snapshot
    from team_logos import logo_data_uri
    chosen=date.fromisoformat(str(day))
    today=pd.Timestamp.now(tz="Europe/Warsaw").date()
    if abs((chosen-today).days)>366:
        raise ValueError("Data poza obsługiwanym przedziałem")
    source_days=[(chosen-timedelta(days=1)).strftime("%Y%m%d"),
                 chosen.strftime("%Y%m%d")]
    def get_day(source_day):
        raw,meta=memoized_json(
            "bb-centre-espn-daily-r2-"+source_day,ESPN_SCOREBOARD,
            params={"dates":source_day,"limit":100},
            ttl_seconds=180 if abs((chosen-today).days)<2 else 3600,
            request_timeout=6,
        )
        if not isinstance(raw,dict) or not isinstance(raw.get("events"),list):
            raise ValueError("Niepoprawna odpowiedź ESPN")
        return raw["events"],meta
    errors=[]
    events={}
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures=[pool.submit(get_day,d) for d in source_days]
        for task in futures:
            try:
                rows,_=task.result()
                for game in rows:
                    if isinstance(game,dict) and game.get("id"):
                        events[str(game["id"])]=game
            except Exception as exc:
                errors.append(type(exc).__name__)
    if len(errors)==len(source_days):
        return {"date":chosen.isoformat(),"games":[],"error":"Źródło ESPN nie odpowiedziało.","complete":False}
    noon=pd.Timestamp(chosen.isoformat()+"T12:00:00",tz="Europe/Warsaw")
    table=parse_espn_schedule({"events":list(events.values())})
    snapshot=build_centre_snapshot(table,{"source":"ESPN"},now=noon,logo_provider=logo_data_uri)
    day_games=[g for g in snapshot["calendar_games"] if g["day"]==chosen.isoformat()]
    return {
        "date":chosen.isoformat(),
        "games":day_games[:20],
        "error":"Niepełne dane z ESPN. Spróbuj odświeżyć." if errors else "",
        "complete":not errors,
    }
