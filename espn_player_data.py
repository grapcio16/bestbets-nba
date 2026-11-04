"""ESPN player-log fallback: current-season partial game samples + individual gamelog.
ESPN event IDs differ from official NBA game IDs. Never silently call the data complete.
"""
from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import math
import re
import pandas as pd

ESPN_SUMMARY='https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary'
ESPN_GAMELOG='https://site.web.api.espn.com/apis/common/v3/sports/basketball/nba/athletes/{athlete_id}/gamelog'
ALIASES={'GS':'GSW','NY':'NYK','SA':'SAS','NO':'NOP','PHO':'PHX','WSH':'WAS','BRK':'BKN'}

def num(v,default=None):
    try:
        if v is None or str(v).strip() in ('','--','DNP','None'):return default
        x=float(str(v).replace(',','.'))
        return x if math.isfinite(x) else default
    except (ValueError,TypeError):return default

def made_attempt(v):
    m=re.match(r'^\s*(\d+)\s*[-/]\s*(\d+)\s*$',str(v or ''))
    if m:return float(m.group(1)),float(m.group(2))
    return num(v),None

def minutes(v):
    if ':' in str(v or ''):
        try:
            m,s=str(v).split(':',1)
            return float(m)+float(s)/60
        except (ValueError,TypeError):return None
    return num(v)

def parse_summary(payload,game):
    rows=[]
    for block in (payload.get('boxscore') or {}).get('players',[]):
        team_obj=block.get('team') or {}
        code=str(team_obj.get('abbreviation') or '').upper()
        team=ALIASES.get(code,code)
        away=str(game.get('away') or '');home=str(game.get('home') or '')
        if not team or team not in (away,home):continue
        opponent=home if team==away else away
        matchup=f'{team} @ {opponent}' if team==away else f'{team} vs. {opponent}'
        for group in block.get('statistics',[]):
            names=[str(s).upper() for s in (group.get('names') or group.get('labels') or [])]
            for item in group.get('athletes',[]):
                if item.get('didNotPlay') or item.get('active') is False:continue
                stats=item.get('stats') or []
                if not isinstance(stats,list) or len(names)!=len(stats):continue
                data=dict(zip(names,stats))
                athlete=item.get('athlete') or {}
                name=athlete.get('displayName') or athlete.get('fullName')
                mins=minutes(data.get('MIN') or data.get('MINUTES'))
                if not name or mins is None or mins<=0:continue
                three,three_att=made_attempt(data.get('3PT',data.get('3PM')))
                _,fga=made_attempt(data.get('FG'))
                row={'PLAYER_NAME':name,'PLAYER_ID':str(athlete.get('id') or ''),
                    'TEAM_ABBREVIATION':team,'GAME_ID':str(game.get('game_id') or ''),
                    'GAME_DATE':str(game.get('start_utc') or ''),'MATCHUP':matchup,
                    'MIN':mins,'PTS':num(data.get('PTS')),'REB':num(data.get('REB')),
                    'AST':num(data.get('AST')),'FG3M':three,'FG3A':three_att,
                    'FGA':fga,'OREB':num(data.get('OREB')),'DREB':num(data.get('DREB')),
                    'TOV':num(data.get('TO',data.get('TOV')))}
                if all(row[k] is not None for k in ('PTS','REB','AST','FG3M')):
                    rows.append(row)
    return rows

def fetch_boxscore(game):
    from sources import memoized_json
    eid=str(game['game_id'])
    payload,_=memoized_json('espn-final-summary-'+eid,ESPN_SUMMARY,
        params={'event':eid},ttl_seconds=100*86400,request_timeout=6)
    return parse_summary(payload,game)

def recent_espn_logs(season,max_games=18):
    """Use a limited recent sample for the player index, not all-season statistics."""
    from sources import ESPN_SCOREBOARD,memoized_json,parse_espn_schedule
    now=datetime.now(timezone.utc)
    sy=now.year if now.month>=9 else now.year-1
    current=f'{sy}-{(sy+1)%100:02d}'
    if season!=current:raise RuntimeError(f'ESPN fallback obsługuje tylko bieżący sezon {current}.')
    months=[];year,month=now.year,now.month
    for _ in range(1):
        if (year>sy) or month>=10:months.append((year,month))
        if month==1:year,month=year-1,12
        else:month-=1
    games=[];failures=[]
    for year,month in months:
        ym=f'{year}{month:02d}'
        try:
            raw,_=memoized_json('espn-sample-calendar-'+ym,ESPN_SCOREBOARD,
                params={'dates':ym,'limit':500},ttl_seconds=4*3600,request_timeout=7)
            parsed=parse_espn_schedule(raw)
            if not parsed.empty:
                parsed=parsed[(parsed['status_code']==3)&
                    (parsed['start_utc']<=pd.Timestamp.now(tz='UTC'))&
                    (parsed['start_utc']>=pd.Timestamp(f'{sy}-10-01',tz='UTC'))]
                games.extend(parsed.to_dict(orient='records'))
        except Exception as ex:failures.append(str(ex)[:100])
    unique=[];seen=set()
    for game in sorted(games,key=lambda g:g['start_utc'],reverse=True):
        eid=str(game.get('game_id'))
        if eid not in seen and eid.isdigit() and len(eid)<=10:
            unique.append(game);seen.add(eid)
        if len(unique)>=max_games:break
    if not unique:raise RuntimeError('ESPN nie udostępnił niedawnych zakończonych spotkań. '+'; '.join(failures))
    rows=[];complete=0
    with ThreadPoolExecutor(max_workers=3) as pool:
        for future in as_completed([pool.submit(fetch_boxscore,g) for g in unique]):
            try:
                parsed=future.result()
                if parsed:rows.extend(parsed);complete+=1
            except Exception as ex:failures.append(str(ex)[:100])
    if not rows:raise RuntimeError('ESPN ma terminarz, ale nie udostępnia boxscore graczy. '+'; '.join(failures[:2]))
    df=pd.DataFrame(rows).drop_duplicates(subset=['GAME_ID','PLAYER_ID'])
    return df,{'source':'ESPN — ostatnie zakończone spotkania (NIEPEŁNA historia)',
        'timestamp':datetime.now(timezone.utc).isoformat(),'age_min':0,
        'stale':complete<len(unique),
        'coverage':f'{complete}/{len(unique)} niedawnych spotkań; {df["PLAYER_NAME"].nunique()} graczy',
        'warning':'ESPN nie jest NBA Stats; wyniki nie obejmują całego sezonu. Prognozy wymagają ostrożności.'}

def parse_gamelog(payload,player_id,name,team):
    labels=[str(x).upper() for x in payload.get('labels',[])]
    stat_labels=[x for x in labels if x not in ('DATE','OPP','RESULT')]
    events=payload.get('events') or []
    if isinstance(events,dict):events=list(events.values())
    rows=[]
    for event in events:
        if not isinstance(event,dict):continue
        vals=event.get('stats') or []
        if not stat_labels or len(vals)!=len(stat_labels):continue
        d=event.get('date') or event.get('gameDate')
        info=dict(zip(stat_labels,vals))
        mins=minutes(info.get('MIN'))
        if not d or mins is None or mins<=0:continue
        raw_opponent=event.get('opponent') or {}
        opp=raw_opponent.get('abbreviation','') if isinstance(raw_opponent,dict) else ''
        _,fga=made_attempt(info.get('FG'))
        three,three_att=made_attempt(info.get('3PT',info.get('3PM')))
        row={'PLAYER_NAME':name,'PLAYER_ID':str(player_id),
             'TEAM_ABBREVIATION':team,'GAME_DATE':d,
             'GAME_ID':str(event.get('id') or event.get('eventId') or ''),
             'MATCHUP':f'{team} vs. {opp}' if opp else team,
             'MIN':mins,'PTS':num(info.get('PTS')),'REB':num(info.get('REB')),
             'AST':num(info.get('AST')),'FG3M':three,'FG3A':three_att,'FGA':fga}
        if all(row[k] is not None for k in ('PTS','REB','AST','FG3M')):rows.append(row)
    if not rows:raise ValueError('ESPN nie zwrócił rozpoznawalnych występów zawodnika.')
    return pd.DataFrame(rows).drop_duplicates(subset=['GAME_ID','PLAYER_ID'])

def detailed_espn_gamelog(player_id,name,team,season):
    from sources import memoized_json
    if not str(player_id).isdigit():raise ValueError('Brak poprawnego ID zawodnika ESPN.')
    season_end=2000+int(season.split('-')[1])
    payload,meta=memoized_json('espn-player-gamelog-'+str(player_id)+'-'+season,
        ESPN_GAMELOG.format(athlete_id=player_id),
        params={'season':season_end,'seasontype':2},
        ttl_seconds=6*3600,request_timeout=7)
    df=parse_gamelog(payload,player_id,name,team)
    meta['source']='ESPN — historia wybranego zawodnika'
    return df,meta
