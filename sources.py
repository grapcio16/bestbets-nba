"""External data adapters for BestBets.

NBA Stats endpoints may respond with 403/timeout on cloud hosting. No bypasses.
Caches are timestamped; stale data is labeled and not silently presented as live.
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from functools import lru_cache
from importlib import import_module
from pathlib import Path
import os
import json
import time
import requests
import pandas as pd

ROOT=Path(__file__).resolve().parent
CACHE=ROOT / 'data'
CACHE.mkdir(exist_ok=True)
HEADERS={'User-Agent':'BestBetsAnalytics/5.0 (educational app; nba data)'}
NBA_CDN_SCHEDULE='https://cdn.nba.com/static/json/staticData/scheduleLeagueV2.json'
NBA_CDN_SCOREBOARD='https://cdn.nba.com/static/json/liveData/scoreboard/todaysScoreboard_00.json'
ESPN_SCOREBOARD='https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard'
ESPN_INJURIES='https://site.api.espn.com/apis/site/v2/sports/basketball/nba/injuries'
OFFICIAL_INJURIES='https://official.nba.com/nba-injury-report-2026-27-season/'
ODDS_API='https://api.the-odds-api.com/v4/sports/basketball_nba/odds/'

# Only call the advanced sets on user demand: expensive, can be blocked.
DATASETS={
 'Zawodnicy • podstawowe':('leaguedashplayerstats','LeagueDashPlayerStats',{'measure_type_detailed_defense':'Base','per_mode_detailed':'PerGame'}),
 'Zawodnicy • advanced':('leaguedashplayerstats','LeagueDashPlayerStats',{'measure_type_detailed_defense':'Advanced','per_mode_detailed':'PerGame'}),
 'Zawodnicy • shooting zones':('leaguedashplayershotlocations','LeagueDashPlayerShotLocations',{}),
 'Zawodnicy • typ rzutów':('leaguedashplayerptshot','LeagueDashPlayerPtShot',{}),
 'Zawodnicy • catch-and-shoot':('leaguedashptstats','LeagueDashPtStats',{'player_or_team':'Player','pt_measure_type':'CatchShoot','per_mode_simple':'PerGame'}),
 'Zawodnicy • transition':('synergyplaytypes','SynergyPlayTypes',{'player_or_team_abbreviation':'P','play_type_nullable':'Transition','type_grouping_nullable':'offensive'}),
 'Zawodnicy • defense':('leaguedashptdefend','LeagueDashPtDefend',{'defense_category':'Overall'}),
 'Zawodnicy • tracking (passes)':('leaguedashptstats','LeagueDashPtStats',{'player_or_team':'Player','pt_measure_type':'Passing','per_mode_simple':'PerGame'}),
 'Zawodnicy • tracking (drives)':('leaguedashptstats','LeagueDashPtStats',{'player_or_team':'Player','pt_measure_type':'Drives','per_mode_simple':'PerGame'}),
 'Drużyny • podstawowe':('leaguedashteamstats','LeagueDashTeamStats',{'measure_type_detailed_defense':'Base','per_mode_detailed':'PerGame'}),
 'Drużyny • advanced (pace/def)':('leaguedashteamstats','LeagueDashTeamStats',{'measure_type_detailed_defense':'Advanced','per_mode_detailed':'PerGame'}),
 'Drużyny • shooting zones':('leaguedashteamshotlocations','LeagueDashTeamShotLocations',{}),
 'Drużyny • typ rzutów':('leaguedashteamptshot','LeagueDashTeamPtShot',{}),
 'Drużyny • opponent shooting':('leaguedashoppptshot','LeagueDashOppPtShot',{}),
 'Drużyny • catch-and-shoot':('leaguedashptstats','LeagueDashPtStats',{'player_or_team':'Team','pt_measure_type':'CatchShoot','per_mode_simple':'PerGame'}),
 'Drużyny • transition':('synergyplaytypes','SynergyPlayTypes',{'player_or_team_abbreviation':'T','play_type_nullable':'Transition','type_grouping_nullable':'offensive'}),
 'Drużyny • defense':('leaguedashptteamdefend','LeagueDashPtTeamDefend',{'defense_category':'Overall'}),
 'Drużyny • hustle':('leaguehustlestatsteam','LeagueHustleStatsTeam',{}),
 'Drużyny • lineups (5)':('leaguedashlineups','LeagueDashLineups',{'group_quantity':5}),
}

def now_utc():return datetime.now(timezone.utc)

def cache_file(key):
    import hashlib
    digest=hashlib.sha1(key.encode()).hexdigest()[:16]
    return CACHE / (digest+'.json')

def store_cache(key,obj):
    fp=cache_file(key)
    try:
        fp.write_text(json.dumps({'at':now_utc().isoformat(),'payload':obj},ensure_ascii=False,default=str),encoding='utf8')
    except OSError:pass

def read_cache(key,ttl_seconds=3600):
    fp=cache_file(key)
    if not fp.exists():return None, None
    try:
        cached=json.loads(fp.read_text(encoding='utf8'))
        at=datetime.fromisoformat(cached['at'])
        age=(now_utc()-at).total_seconds()
        return cached['payload'], {'timestamp':at.isoformat(),'age_min':round(age/60,1),'stale':age>ttl_seconds}
    except (ValueError,KeyError,TypeError,OSError):return None,None

def http_json(url,params=None,timeout=16):
    response=requests.get(url,params=params,headers={'User-Agent':'Mozilla/5.0 (BestBets data consumer)','Accept':'application/json'},timeout=timeout)
    response.raise_for_status()
    return response.json()

def memoized_json(key,url,params=None,ttl_seconds=1800,refresh=False,request_timeout=16):
    cache,meta=read_cache(key,ttl_seconds)
    if cache is not None and not refresh and not meta['stale']:
        return cache, {'source':'cache',**meta}
    try:
        data=http_json(url,params=params,timeout=request_timeout)
        store_cache(key,data)
        return data,{'source':'live','timestamp':now_utc().isoformat(),'age_min':0,'stale':False}
    except Exception as exc:
        if cache is not None:
            return cache,{'source':'stale cache','warning':str(exc),**meta,'stale':True}
        raise RuntimeError(f'Źródło nie odpowiada: {url} — {exc}') from exc


def nba_stats(module, cls, kwargs, cache_key, ttl_seconds=4*3600, refresh=False):
    cache,meta=read_cache(cache_key,ttl_seconds)
    if cache is not None and not refresh and not meta['stale']:
        return pd.DataFrame(cache), {'source':'cache',**meta}
    # Avoid a 25-second timeout on every rerun when stats.nba.com blocks cloud IPs.
    failure,_=read_cache('nba-failure-'+cache_key,20*60)
    if failure is not None and not refresh:
        if cache is not None:
            return pd.DataFrame(cache),{'source':'stale cache','warning':'NBA Stats chwilowo niedostępne',**meta,'stale':True}
        raise RuntimeError('NBA Stats tymczasowo niedostępne z hostingu; ponowna próba po 20 minutach.')
    try:
        module_obj=import_module('nba_api.stats.endpoints.'+module)
        endpoint=getattr(module_obj,cls)(timeout=7,**kwargs)
        result=endpoint.get_data_frames()[0]
        if result.empty:raise RuntimeError('Pusty zestaw danych')
        store_cache(cache_key,result.to_dict(orient='records'))
        return result,{'source':'NBA Stats','timestamp':now_utc().isoformat(),'age_min':0,'stale':False}
    except Exception as exc:
        store_cache('nba-failure-'+cache_key,{'reason':str(exc)[:120]})
        if cache is not None:
            return pd.DataFrame(cache),{'source':'stale cache','warning':str(exc),**meta,'stale':True}
        raise RuntimeError(f'NBA Stats ({cls}) niedostępne: {exc}') from exc


def game_logs(season,refresh=False):
    # Preferred source: official NBA Stats; second: official NBA CDN; third:
    # ESPN publicly reported completed box scores, clearly labeled PARTIAL.
    failures=[]
    try:
        return nba_stats('playergamelogs','PlayerGameLogs',
            {'season_nullable':season,'season_type_nullable':'Regular Season','league_id_nullable':'00'},
            f'player_game_logs-{season}',ttl_seconds=3*3600,refresh=refresh)
    except Exception as exc:
        failures.append('NBA Stats: '+str(exc)[:160])
    try:
        return partial_cdn_logs(season,max_new_games=10)
    except Exception as exc:
        failures.append('NBA CDN: '+str(exc)[:160])
    failed,_=read_cache('espn-sample-failed-'+season,10*60)
    if failed is not None and not refresh:
        raise RuntimeError('Historia zawodników chwilowo niedostępna (NBA Stats / NBA CDN / ESPN). Kolejna automatyczna próba za 10 minut.')
    try:
        from espn_player_data import recent_espn_logs
        return recent_espn_logs(season,max_games=12)
    except Exception as exc:
        store_cache('espn-sample-failed-'+season,{'reason':str(exc)[:160]})
        failures.append('ESPN: '+str(exc)[:160])
        raise RuntimeError('Nie udało się pobrać prawdziwych danych zawodników. '+'; '.join(failures)) from exc


def extended_set(name,season,refresh=False):
    module,cls,extra=DATASETS[name]
    kwargs={'season':season,**extra}
    return nba_stats(module,cls,kwargs,'extended-'+name+'-'+season,ttl_seconds=12*3600,refresh=refresh)


def parse_nba_schedule(raw):
    """Parse official NBA CDN schedule into the common timetable schema."""
    root=raw.get('leagueSchedule',raw)
    rows=[]
    for block in root.get('gameDates',[]):
        for g in block.get('games',[]):
            away=g.get('awayTeam') or {};home=g.get('homeTeam') or {}
            rows.append({'game_id':str(g.get('gameId','')),
              'start_utc':g.get('gameDateTimeUTC') or g.get('gameTimeUTC') or '',
              'day_label':block.get('gameDate',''),
              'away':away.get('teamTricode',''),'home':home.get('teamTricode',''),
              'away_name':(away.get('teamCity','')+' '+away.get('teamName','')).strip(),
              'home_name':(home.get('teamCity','')+' '+home.get('teamName','')).strip(),
              'away_score':away.get('score'),'home_score':home.get('score'),
              'status':g.get('gameStatusText',''), 'status_code':g.get('gameStatus',1)})
    return normalized_schedule(rows)


def normalized_schedule(rows):
    columns=['game_id','start_utc','day_label','away','home','away_name','home_name',
             'away_score','home_score','status','status_code']
    df=pd.DataFrame(rows,columns=columns)
    df['start_utc']=pd.to_datetime(df['start_utc'],errors='coerce',utc=True)
    df=df.dropna(subset=['start_utc'])
    return df.sort_values('start_utc').drop_duplicates(subset=['game_id']).reset_index(drop=True)


def parse_espn_schedule(payload):
    """ESPN scoreboard -> NBA-tricode timetable; ESPN game IDs aren't NBA IDs."""
    from teams import TEAM_MAP
    aliases={'GS':'GSW','NY':'NYK','SA':'SAS','NO':'NOP','UTAH':'UTA','UT':'UTA',
             'PHO':'PHX','WSH':'WAS','WSA':'WAS','BRK':'BKN'}
    rows=[]
    for e in payload.get('events',[]):
        competitions=e.get('competitions') or []
        if not competitions:continue
        game=competitions[0]
        sides={c.get('homeAway'):c for c in game.get('competitors',[])}
        if 'home' not in sides or 'away' not in sides:continue
        home=sides['home'];away=sides['away']
        def team_fields(comp):
            t=comp.get('team') or {}
            fullname=t.get('displayName') or t.get('name') or ''
            short=TEAM_MAP.get(fullname) or aliases.get(t.get('abbreviation',''),t.get('abbreviation',''))
            return short,fullname
        home_code,home_name=team_fields(home)
        away_code,away_name=team_fields(away)
        if not home_code or not away_code:continue
        state=(game.get('status') or e.get('status') or {}).get('type') or {}
        st=state.get('state','pre')
        status_code=3 if state.get('completed') or st=='post' else 2 if st=='in' else 1
        rows.append({'game_id':str(e.get('id') or game.get('id') or ''),
          'start_utc':e.get('date') or game.get('date') or '',
          'day_label':(e.get('date') or game.get('date') or '')[:10],
          'away':away_code,'home':home_code,'away_name':away_name,'home_name':home_name,
          'away_score':away.get('score') or None,'home_score':home.get('score') or None,
          'status':state.get('shortDetail') or state.get('description') or ('Scheduled' if st=='pre' else st),
          'status_code':status_code})
    return normalized_schedule(rows)


def next_calendar_month(year,month):
    return (year + (month==12), month%12+1)


def espn_schedule(refresh=False):
    """Fallback using the date-filtered ESPN scoreboard (not an official NBA feed).

    Request this month and next month to cover upcoming games even at month end.
    Partial coverage is explicitly flagged instead of treated as complete.
    """
    current=now_utc()
    months=[(current.year,current.month),next_calendar_month(current.year,current.month)]
    output=[]; failures=[]; any_stale=False
    for year,month in months:
        ym=f'{year}{month:02d}'
        try:
            raw,meta=memoized_json('espn-nba-scoreboard-month-'+ym,
                ESPN_SCOREBOARD,params={'dates':ym,'limit':500},ttl_seconds=20*60,refresh=refresh)
            parsed=parse_espn_schedule(raw)
            output.append(parsed)
            any_stale|=meta.get('stale',False)
        except Exception as exc:
            failures.append(f'{ym}: {exc}')
    if not output:
        raise RuntimeError('ESPN również nie odpowiada: '+'; '.join(failures))
    df=pd.concat(output,ignore_index=True)
    df=df.drop_duplicates(subset=['game_id']).sort_values('start_utc').reset_index(drop=True)
    if df.empty:
        raise RuntimeError('ESPN zwrócił odpowiedź bez rozpoznawalnych spotkań NBA.')
    result_meta={'source':'ESPN — terminarz zastępczy (nieoficjalny)',
        'timestamp':now_utc().isoformat(),'age_min':0,
        'stale':any_stale or bool(failures)}
    if failures:result_meta['warning']='Niepełne daty: '+'; '.join(failures)
    return df,result_meta


def schedule(refresh=False):
    """Fast ESPN schedule first; official NBA CDN is a fallback if ESPN fails.

    The feed source is always disclosed, including if it is stale.
    This avoids a repeatedly blocked NBA CDN request before every first page load.
    """
    espn_error = None
    try:
        parsed, meta = espn_schedule(refresh=refresh)
        if not parsed.empty:
            return parsed, meta
        espn_error = RuntimeError('ESPN zwróciło pusty terminarz')
    except Exception as exc:
        espn_error = exc

    try:
        raw, meta = memoized_json('nba-current-season-schedule', NBA_CDN_SCHEDULE,
                                  ttl_seconds=6*3600, refresh=refresh)
        parsed = parse_nba_schedule(raw)
        if not parsed.empty:
            meta['source'] = 'NBA CDN — oficjalny terminarz (źródło zapasowe)'
            meta['warning'] = f'ESPN niedostępne: {espn_error}'
            return parsed, meta
        raise RuntimeError('NBA CDN zwróciło pusty terminarz')
    except Exception as official_error:
        raise RuntimeError(f'Terminarz niedostępny. ESPN: {espn_error}; NBA CDN: {official_error}') from official_error


def scoreboard(refresh=False):
    return memoized_json('nba-scoreboard-today',NBA_CDN_SCOREBOARD,ttl_seconds=5*60,refresh=refresh)


def injury_rows(payload):
    """Normalize public ESPN team-based injury feed, preserving ambiguous statuses."""
    out=[];seen=set()
    def traverse(node,team=''):
        if isinstance(node,list):
            for item in node:traverse(item,team)
            return
        if not isinstance(node,dict):return
        team_obj=node.get('team')
        if isinstance(team_obj,dict):
            team=team_obj.get('abbreviation') or team_obj.get('displayName') or team
        elif isinstance(node.get('teamAbbreviation'),str):
            team=node['teamAbbreviation']
        athlete=node.get('athlete') or node.get('player') or {}
        if isinstance(athlete,dict):
            player=athlete.get('displayName') or athlete.get('fullName') or athlete.get('name')
        else:player=str(athlete) if athlete else None
        status=node.get('status') or node.get('injuryStatus')
        if isinstance(status,dict):status=status.get('displayName') or status.get('name')
        if player and status:
            details=node.get('details') or {}
            note=details.get('detail','') if isinstance(details,dict) else str(details)
            k=(str(player),str(team),str(status))
            if k not in seen:
                out.append({'player':player,'team':team,'status':str(status),'note':note});seen.add(k)
        for key in ('injuries','items','teams','groups','athletes'):
            if key in node:traverse(node[key],team)
    traverse(payload)
    return pd.DataFrame(out,columns=['player','team','status','note'])


def injuries(refresh=False):
    raw,meta=memoized_json('espn-injuries',ESPN_INJURIES,ttl_seconds=45*60,refresh=refresh)
    return injury_rows(raw),meta


def current_odds(api_key,regions='eu',refresh=False,markets='h2h,totals'):
    if not api_key or not str(api_key).strip():raise ValueError('Brak klucza do The Odds API')
    # API key intentionally never stored in our disk cache or logs.
    payload=http_json(ODDS_API,params={'apiKey':api_key,'regions':regions,'markets':markets,'oddsFormat':'decimal'},timeout=18)
    rows=[]
    for event in payload:
        for book in event.get('bookmakers',[]):
            for m in book.get('markets',[]):
                for o in m.get('outcomes',[]):
                    rows.append({'event_id':event.get('id'), 'start_utc':event.get('commence_time'),
                      'home_team':event.get('home_team'),'away_team':event.get('away_team'),
                      'bookmaker':book.get('title'),'bookmaker_key':book.get('key'),
                      'market':m.get('key'),'name':o.get('name'),'line':o.get('point'),
                      'odds':o.get('price'),'book_updated':book.get('last_update'),
                      'market_updated':m.get('last_update')})
    return pd.DataFrame(rows), {'source':'The Odds API','timestamp':now_utc().isoformat(),'stale':False}


def nfl_nonapplicable():pass

def event_player_odds(api_key,event_id,regions='eu'):
    """Optional, quota-consuming event player prop lookup. Availability depends on API tier/book."""
    if not api_key:raise ValueError('Brak klucza API')
    if not event_id or '/' in str(event_id):raise ValueError('Nieprawidłowe ID spotkania')
    url=f'https://api.the-odds-api.com/v4/sports/basketball_nba/events/{event_id}/odds'
    payload=http_json(url,params={'apiKey':api_key,'regions':regions,
        'markets':'player_points,player_rebounds,player_assists,player_threes,player_points_rebounds_assists',
        'oddsFormat':'decimal'},timeout=20)
    rows=[]
    for book in payload.get('bookmakers',[]):
        for m in book.get('markets',[]):
            for o in m.get('outcomes',[]):
                rows.append({'event_id':event_id,'bookmaker':book.get('title'), 'bookmaker_key':book.get('key'),
                   'market':m.get('key'),'player':o.get('description'), 'side':o.get('name'),
                   'line':o.get('point'), 'odds':o.get('price'), 'updated':m.get('last_update')})
    return pd.DataFrame(rows)


def parse_live_minutes(value):
    """NBA CDN can return ISO 8601 game-time duration, e.g. PT31M05.00S."""
    import re
    if isinstance(value,(float,int)):return float(value)
    s=str(value or '')
    if s.startswith('PT'):
        m=re.fullmatch(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+(?:\.\d+)?)S)?',s)
        if m:
            h,mm,ss=m.groups()
            return float(h or 0)*60+float(mm or 0)+float(ss or 0)/60
    if ':' in s:
        try:
            m,ss=s.split(':',1)
            return float(m)+float(ss)/60
        except ValueError:pass
    try:return float(s)
    except (ValueError,TypeError):return 0.


def parse_nba_cdn_boxscore(raw):
    game=raw.get('game',raw)
    if str(game.get('gameStatus',3)) not in ('3','Final'):
        return []
    id=str(game.get('gameId',''))
    started=game.get('gameTimeUTC') or game.get('gameDateTimeUTC') or ''
    date=started[:10]
    rows=[]
    for side in ('homeTeam','awayTeam'):
        t=game.get(side) or {}
        team=t.get('teamTricode','')
        other=(game.get('awayTeam') or {}) if side=='homeTeam' else (game.get('homeTeam') or {})
        opp=other.get('teamTricode','')
        for p in t.get('players',[]):
            s=p.get('statistics') or {}
            name=p.get('name') or p.get('nameI') or (' '.join(filter(None,[p.get('firstName'),p.get('familyName')])))
            if not name or not s:continue
            minutes=parse_live_minutes(s.get('minutes'))
            # Missing minutes are not an observed 0-minute game.
            if minutes<=0:continue
            rows.append({
                'PLAYER_NAME':name,'PLAYER_ID':p.get('personId'),
                'TEAM_ABBREVIATION':team,'GAME_ID':id,'GAME_DATE':date,
                'MATCHUP':f'{team} vs. {opp}' if side=='homeTeam' else f'{team} @ {opp}',
                'MIN':round(minutes,2),'PTS':s.get('points'),
                'REB':s.get('reboundsTotal'),'AST':s.get('assists'),
                'FG3M':s.get('threePointersMade'), 'FG3A':s.get('threePointersAttempted'),
                'FGA':s.get('fieldGoalsAttempted'), 'OREB':s.get('reboundsOffensive'),
                'DREB':s.get('reboundsDefensive'),'TOV':s.get('turnovers'),
            })
    return rows


def partial_cdn_logs(season, max_new_games=26):
    """Best-effort limited fallback to official NBA final box scores when Stats API is blocked.

    Never claim full-season coverage unless every final game has been synchronized.
    """
    import concurrent.futures
    sched,_=schedule()
    if sched.empty:raise RuntimeError('Brak terminarza w NBA CDN')
    final=sched[pd.to_numeric(sched['status_code'],errors='coerce')==3].copy()
    # CDN schedule covers the current season only; don't use when season differs.
    yr=now_utc().year if now_utc().month>=9 else now_utc().year-1
    current=f'{yr}-{(yr+1)%100:02d}'
    if season!=current:
        raise RuntimeError('Zapasowy feed CDN obejmuje tylko bieżący sezon, nie wybrany sezon historyczny.')
    final=final.sort_values('start_utc',ascending=False)
    ids=[g for g in final['game_id'].tolist() if len(str(g))==10]
    new=[g for g in ids if read_cache('box-final-'+str(g),100*365*86400)[0] is None]
    selected=new[:max_new_games]
    def fetch_one(game_id):
        key='box-final-'+str(game_id)
        try:
            raw=http_json(f'https://cdn.nba.com/static/json/liveData/boxscore/boxscore_{game_id}.json',timeout=11)
            parsed=parse_nba_cdn_boxscore(raw)
            if parsed:
                store_cache(key,parsed)
            return parsed
        except Exception:return []
    if selected:
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
            list(pool.map(fetch_one,selected))
    rows=[];covered=0
    for game_id in ids:
        cached,_=read_cache('box-final-'+str(game_id),100*365*86400)
        if cached:
            rows.extend(cached);covered+=1
    if not rows:raise RuntimeError('Brak statystyk zawodników w NBA CDN')
    return pd.DataFrame(rows),{'source':'NBA CDN — częściowe boxscores (źródło zapasowe)',
        'timestamp':now_utc().isoformat(),'age_min':0,
        'stale':covered<len(ids), 'coverage':f'{covered}/{len(ids)} finałowych spotkań',
        'warning':'Statystyki nie obejmują wszystkich spotkań sezonu. Zbyt mała próbka do wiarygodnych ocen.' if covered<len(ids) else ''}
