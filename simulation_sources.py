"""Historical completed NBA scores for a transparent fallback scoring model."""
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor
import pandas as pd
from sources import ESPN_SCOREBOARD, memoized_json, parse_espn_schedule


def _score_int(value):
    """Strict observed quarter score; not any synthetic or missing display value."""
    try:
        numeric = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    if not (numeric.is_integer() and 0 <= numeric <= 75):
        return None
    return int(numeric)


def parse_espn_quarter_linescores(payload):
    """Accept only COMPLETE, regulation, final, verified ESPN quarter scores.

    Do not infer quarters from the final score. Do not merge overtime totals
    into Q4. The scoreboard's team order is NOT the home/away order.
    """
    if not isinstance(payload, dict):
        return []
    result = []
    for event in payload.get("events") or []:
        if not isinstance(event, dict):
            continue
        competition = (event.get("competitions") or [None])[0]
        if not isinstance(competition, dict):
            continue
        state = ((competition.get("status") or event.get("status")
                  or {}).get("type") or {})
        if not (state.get("completed") is True or state.get("state") == "post"):
            continue
        competitors = {
            item.get("homeAway"): item
            for item in competition.get("competitors") or []
            if isinstance(item, dict)
            and item.get("homeAway") in ("away", "home")
        }
        if set(competitors) != {"home", "away"}:
            continue
        line = {}
        for side in ("home", "away"):
            team = competitors[side]
            items = team.get("linescores")
            if not isinstance(items, list) or len(items) != 4:
                break  # No full Q1–Q4 evidence, or an overtime game.
            periods = {}
            for n, item in enumerate(items, start=1):
                if not isinstance(item, dict):
                    break
                period = item.get("period", n)
                try:
                    period = int(period)
                except (ValueError, TypeError, OverflowError):
                    break
                if period not in (1, 2, 3, 4) or period in periods:
                    break
                val = _score_int(item.get("value", item.get("displayValue")))
                if val is None:
                    break
                periods[period] = val
            if len(periods) != 4:
                break
            try:
                final = int(team.get("score"))
            except (TypeError, ValueError, OverflowError):
                break
            if sum(periods.values()) != final or final < 55 or final > 200:
                break
            for q in range(1, 5):
                line[f"{side}_q{q}"] = periods[q]
        if len(line) != 8:
            continue
        eid = str(event.get("id") or competition.get("id") or "")
        if not eid.isdigit():
            continue
        result.append({"game_id": eid, **line})
    return result


def _season_scoreboard_months(periods, refresh=False):
    """Fetch independent ESPN calendar months concurrently, preserving month order."""
    def one(period):
        key=period.strftime('%Y%m')
        raw,meta=memoized_json('sim-finished-scoreboard-'+key,ESPN_SCOREBOARD,
            params={'dates':key,'limit':500},ttl_seconds=45*60,refresh=refresh)
        # Extend the model's existing cached scoreboard response with real
        # Q1–Q4; the public schedule parser remains unchanged.
        games = parse_espn_schedule(raw)
        quarters = parse_espn_quarter_linescores(raw)
        if quarters and not games.empty:
            games = games.merge(pd.DataFrame(quarters), how="left",
                                on="game_id", validate="one_to_one")
        return games,meta

    chunks=[];errors=[]
    if not periods:return chunks,errors
    # Month API calls may each take several seconds. Start them together,
    # keeping the existing per-month disk cache and data validation.
    with ThreadPoolExecutor(max_workers=min(len(periods),4)) as pool:
        futures=[pool.submit(one,period) for period in periods]
        for period,future in zip(periods,futures):
            key=period.strftime('%Y%m')
            try:
                chunk,meta=future.result()
                if not chunk.empty:chunks.append(chunk)
                if meta.get('stale'):errors.append(f'{key}: zapis z pamięci')
            except Exception as exc:errors.append(f'{key}: {str(exc)[:130]}')
    return chunks,errors


def historical_espn_results(season: str, refresh=False, lookback_months=3):
    """Season-scoped completed games from ESPN, with configurable cached depth.

    Default stays at 3 months for fast startup. The research/audit option can
    load up to 8 calendar months of THIS season, never past-season matches.
    On November 2026 the season has only October/November available: larger
    lookback cannot invent more season data.
    """
    start=int(str(season).split('-')[0])
    now=pd.Timestamp.now(tz='UTC')
    season_start=pd.Timestamp(year=start,month=10,day=1,tz='UTC')
    season_end=pd.Timestamp(year=start+1,month=7,day=1,tz='UTC')
    if not (season_start<=now<season_end):
        return pd.DataFrame(), 'ESPN: dane historyczne tej wersji tylko dla aktualnego sezonu.'
    try:
        window=max(1,min(8,int(lookback_months)))
    except (ValueError,TypeError):
        window=3
    months=pd.period_range((now-pd.DateOffset(months=window-1)).strftime('%Y-%m'),now.strftime('%Y-%m'),freq='M')
    periods=[p for p in months if p.to_timestamp().tz_localize('UTC')>=season_start]
    chunks,errors=_season_scoreboard_months(periods,refresh=refresh)
    if not chunks:return pd.DataFrame(),'ESPN nie dostarczył wyników zakończonych spotkań. '+'; '.join(errors)
    games=pd.concat(chunks,ignore_index=True).drop_duplicates(subset=['game_id'])
    games=games[(games['status_code']==3)&(games['start_utc']<now)]
    games=games[(games['start_utc']>=season_start)].sort_values('start_utc')
    return games, ('ESPN: '+'; '.join(errors)) if errors else ''
