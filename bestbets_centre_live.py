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
    """Read explicitly reported NBA match leaders, never manufacture stats."""
    now=pd.Timestamp(now) if now is not None else pd.Timestamp.now(tz="Europe/Warsaw")
    if now.tzinfo is None:now=now.tz_localize("Europe/Warsaw")
    else:now=now.tz_convert("Europe/Warsaw")
    candidates=[]
    allowed={"points":"PTS","rebounds":"REB","assists":"AST",
             "threepointfieldgoalsmade":"3PM","threes":"3PM"}
    for event in (payload.get("events",[]) if isinstance(payload,dict) else []):
        if not isinstance(event,dict):continue
        game_status=(event.get("status") or {}).get("type") or {}
        comp=(event.get("competitions") or [{}])[0]
        if not isinstance(comp,dict):continue
        c_status=(comp.get("status") or {}).get("type") or {}
        completed=bool(game_status.get("completed") or c_status.get("completed"))
        if not completed:continue
        when=pd.to_datetime(event.get("date"),utc=True,errors="coerce")
        if pd.isna(when) or when>now.tz_convert("UTC"):continue
        for team in comp.get("competitors") or []:
            if not isinstance(team,dict):continue
            team_code=str((team.get("team") or {}).get("abbreviation") or "NBA").upper()
            for group in team.get("leaders") or []:
                if not isinstance(group,dict):continue
                label=str(group.get("name") or group.get("abbreviation") or "").lower().replace(" ","").replace("-","")
                market=allowed.get(label)
                if not market:continue
                for leader in group.get("leaders") or []:
                    if not isinstance(leader,dict):continue
                    athlete=leader.get("athlete") or {}
                    if not isinstance(athlete,dict):continue
                    name=str(athlete.get("displayName") or athlete.get("fullName") or "").strip()
                    if not name or len(name)>70:continue
                    amount=_value(leader.get("value"))
                    if amount is None:continue
                    candidates.append({
                        "name":name,"team":team_code[:4],"market":market,
                        "value":amount,"date":when.date().isoformat(),
                        "athlete_id":str(athlete.get("id") or "")[:20]
                    })
    # Keep the most recent confirmed result per player, and diversify names
    candidates.sort(key=lambda c:(c["date"],c["value"]),reverse=True)
    dedup=[];seen=set()
    for row in candidates:
        key=row["athlete_id"] or row["name"].casefold()
        if key in seen:continue
        seen.add(key)
        dedup.append(row)
        if len(dedup)>=limit:break
    return dedup


def get_centre_live_data(now=None):
    """Fetch a bounded real scoreboard window with disk-cache and one fallback."""
    from sources import ESPN_SCOREBOARD, memoized_json, parse_espn_schedule, schedule
    from team_logos import logo_data_uri
    from bestbets_centre_data import build_centre_snapshot

    now=pd.Timestamp(now) if now is not None else pd.Timestamp.now(tz="Europe/Warsaw")
    now=now.tz_localize("Europe/Warsaw") if now.tzinfo is None else now.tz_convert("Europe/Warsaw")
    start=(now-timedelta(days=9)).strftime("%Y%m%d")
    end=(now+timedelta(days=8)).strftime("%Y%m%d")
    key="bb-centre-espn-r1-"+start+"-"+end
    errors=[]
    try:
        raw,metadata=memoized_json(
            key,ESPN_SCOREBOARD,
            params={"dates":start+"-"+end,"limit":350},
            ttl_seconds=150,request_timeout=8
        )
        table=parse_espn_schedule(raw)
        if table is None or table.empty:
            raise ValueError("ESPN: brak spotkań w wybranym zakresie dat")
        snap=build_centre_snapshot(
            table,{"source":"ESPN — rzeczywiste mecze NBA","stale":metadata.get("stale",False)},
            now=now,logo_provider=logo_data_uri
        )
        snap["players"]=extract_recent_leaders(raw,now=now,limit=3)
        snap["coverage"]="Mecze z okresu "+start+"–"+end
        snap["stale"]=bool(metadata.get("stale"))
        snap["fetched_at"]=metadata.get("timestamp") or snap["as_of"]
        return snap
    except Exception as exc:
        errors.append(type(exc).__name__)
    # Use the existing NBA CDN/ESPN backup already shipped in BestBets.
    # Preserve the source and stale disclosure, never synthesize game IDs.
    try:
        table,meta=schedule(refresh=False)
        snap=build_centre_snapshot(table,meta,now=now,logo_provider=logo_data_uri)
        snap["players"]=[]
        snap["coverage"]="Źródło zapasowe — bez weryfikacji liderów zawodników"
        snap["stale"]=bool(meta.get("stale"))
        snap["fetched_at"]=meta.get("timestamp") or snap["as_of"]
        return snap
    except Exception:
        empty=build_centre_snapshot(pd.DataFrame(),{"source":"NBA / ESPN"},now=now)
        empty["players"]=[]
        empty["stale"]=True
        empty["coverage"]="Brak dostępnych danych"
        empty["error"]="Nie udało się pobrać potwierdzonych danych NBA. Ponowimy próbę automatycznie."
        return empty
