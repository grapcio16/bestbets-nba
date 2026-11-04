"""Historical completed NBA scores for a transparent fallback scoring model."""
from datetime import datetime, timezone
import pandas as pd
from sources import ESPN_SCOREBOARD, memoized_json, parse_espn_schedule


def historical_espn_results(season: str, refresh=False):
    """Read current & prior month; do not fetch a different season by accident.

    At 2026/27 season start the month-window covers October and November, and
    grows as the season progresses. Maximum 3 months to minimize live API calls.
    """
    start=int(str(season).split('-')[0])
    now=pd.Timestamp.now(tz='UTC')
    season_start=pd.Timestamp(year=start,month=10,day=1,tz='UTC')
    season_end=pd.Timestamp(year=start+1,month=7,day=1,tz='UTC')
    if not (season_start<=now<season_end):
        return pd.DataFrame(), 'ESPN: dane historyczne tej wersji tylko dla aktualnego sezonu.'
    months=pd.period_range((now-pd.DateOffset(months=2)).strftime('%Y-%m'),now.strftime('%Y-%m'),freq='M')
    chunks=[];errors=[]
    for period in months:
        if period.to_timestamp().tz_localize('UTC')<season_start:continue
        key=period.strftime('%Y%m')
        try:
            raw,meta=memoized_json('sim-finished-scoreboard-'+key,ESPN_SCOREBOARD,
                params={'dates':key,'limit':500},ttl_seconds=45*60,refresh=refresh)
            chunk=parse_espn_schedule(raw)
            if not chunk.empty:chunks.append(chunk)
            if meta.get('stale'):errors.append(f'{key}: zapis z pamięci')
        except Exception as exc:errors.append(f'{key}: {str(exc)[:130]}')
    if not chunks:return pd.DataFrame(),'ESPN nie dostarczył wyników zakończonych spotkań. '+'; '.join(errors)
    games=pd.concat(chunks,ignore_index=True).drop_duplicates(subset=['game_id'])
    games=games[(games['status_code']==3)&(games['start_utc']<now)]
    games=games[(games['start_utc']>=season_start)].sort_values('start_utc')
    return games, ('ESPN: '+'; '.join(errors)) if errors else ''
