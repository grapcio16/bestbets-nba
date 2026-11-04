"""Automated, budgeted The Odds API integration for an interactive Streamlit app.

A one-time API key is required; no unauthorized scraper or invented Betclic-PL odds.
Provider data (not the API key) is cached on disk. Token redacted from errors.
"""
from __future__ import annotations
import json, os, threading, re
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd
from sources import current_odds, event_player_odds

DIR=Path(__file__).resolve().parent / 'data'
DIR.mkdir(exist_ok=True)
LEDGER=DIR/'odds_quota.json'
LOCK=threading.RLock()

DEFAULTS={
    'regions':'eu,us', 'featured_markets':'h2h,spreads,totals',
    'prop_regions':'us','prop_markets':'player_points,player_rebounds,player_assists,player_threes,player_points_rebounds_assists',
    'max_prop_events':1, 'max_daily_credits':15, 'featured_ttl_minutes':180, 'props_ttl_minutes':360,
}

def config():
    """Override limits via env; values in app's private config, never user interface work."""
    c=DEFAULTS.copy()
    for k,env in [('regions','BESTBETS_ODDS_REGIONS'),('prop_regions','BESTBETS_PROPS_REGIONS')]:
        value=os.getenv(env,'').strip()
        if value:c[k]=value
    for k,env in [('max_prop_events','BESTBETS_PROPS_EVENTS'),('max_daily_credits','BESTBETS_ODDS_DAILY_CREDITS'),
                  ('featured_ttl_minutes','BESTBETS_ODDS_TTL_MINUTES'),('props_ttl_minutes','BESTBETS_PROPS_TTL_MINUTES')]:
        try:c[k]=max(0,min(10000,int(os.getenv(env,''))))
        except ValueError:pass
    c['max_prop_events']=min(5,c['max_prop_events'])
    return c


def redact(err,key):
    msg=str(err)
    if key: msg=msg.replace(key,'[UKRYTY KLUCZ]')
    msg=re.sub(r'([?&]apiKey=)[^&\s]+',r'\1[UKRYTY KLUCZ]',msg,flags=re.I)
    return msg[:500]


def _snapshot(kind):
    kind=re.sub(r'[^A-Za-z0-9_-]','_',str(kind))
    path=DIR/f'odds_{kind}.json'
    if not path.exists():return None,None
    try:
        item=json.loads(path.read_text('utf-8'))
        data=pd.DataFrame(item.get('rows',[]))
        return data,item.get('at')
    except (ValueError,OSError,TypeError):return None,None


def _save(kind,df):
    kind=re.sub(r'[^A-Za-z0-9_-]','_',str(kind))
    path=DIR/f'odds_{kind}.json'
    record={'at':datetime.now(timezone.utc).isoformat(),'rows':df.to_dict('records')}
    temp=path.with_suffix('.json.tmp')
    try:
        temp.write_text(json.dumps(record,ensure_ascii=False,default=str),encoding='utf-8')
        temp.replace(path)
    except OSError:pass


def _age_min(dt):
    if not dt:return float('inf')
    try:return max(0.,(datetime.now(timezone.utc)-datetime.fromisoformat(dt)).total_seconds()/60)
    except (TypeError,ValueError):return float('inf')


def _usage():
    date=datetime.now(timezone.utc).strftime('%Y-%m-%d')
    try:
        d=json.loads(LEDGER.read_text('utf-8'))
        if d.get('date')==date:return int(d.get('credits',0))
    except (FileNotFoundError,ValueError,OSError,TypeError):pass
    return 0


def _reserve(cost, daily_limit):
    """Estimated request credits. Reserve before HTTP call to cap repeat attempts."""
    with LOCK:
        used=_usage()
        if used+cost>daily_limit:return False,used
        value={'date':datetime.now(timezone.utc).strftime('%Y-%m-%d'),'credits':used+cost}
        try:LEDGER.write_text(json.dumps(value),encoding='utf-8')
        except OSError:return False,used
        return True,used+cost


def _read_fetch(kind,ttl,api_key,cost,limit,fetch):
    with LOCK:
        cached,at=_snapshot(kind)
        age=_age_min(at)
        # Empty feeds should retry sooner; they can change when books publish prices.
        effective_ttl=min(ttl,15) if cached is not None and cached.empty else ttl
        if cached is not None and age<effective_ttl:
            return cached,{'source':'cache dostawcy','updated':at,'age_min':round(age,1),'stale':False,'error':''}
        allowed,used=_reserve(cost,limit)
        if not allowed:
            return cached if cached is not None else pd.DataFrame(),{
                'source':'cache' if at else 'brak','updated':at,'age_min':round(age,1),
                'stale':True,'error':f'Limit zapytań API ustawiony w BestBets: {used}/{limit} kredytów UTC/dzień. Nie pobieram kolejnych kursów.'}
        try:
            df=fetch()
            # An empty API response is a real result: never substitute fake odds.
            _save(kind,df)
            return df,{'source':'The Odds API','updated':datetime.now(timezone.utc).isoformat(),
                       'age_min':0.,'stale':False,'error':''}
        except Exception as ex:
            return cached if cached is not None else pd.DataFrame(),{
                'source':'cache' if at else 'brak','updated':at,'age_min':round(age,1),
                'stale':True,'error':redact(ex,api_key)}


def automatic_odds(key):
    """Fetch standard odds and props for the nearest upcoming NBA game automatically.

    Does not require UI clicks; stays within configurable request-credit budget.
    """
    c=config(); empty=pd.DataFrame()
    if not key:
        prices,meta=_read_fetch('espn_public_h2h_v51',45,'',0,0,espn_moneylines)
        if meta.get('source')!='brak':meta['source']='ESPN — publicznie raportowane kursy (źródło zastępcze)'
        return prices,empty,{'featured':meta,
                             'props':{'source':'brak klucza','error':'Automatyczne rynki zawodników wymagają jednorazowo ODDS_API_KEY.', 'stale':True},
                             'daily_credits':_usage(),'daily_limit':c['max_daily_credits'],
                             'featured_regions':'ESPN','props_regions':'—','max_prop_events':0}
    feat_cost=len(c['regions'].split(','))*len(c['featured_markets'].split(','))
    f,fs=_read_fetch('featured',c['featured_ttl_minutes'],key,feat_cost,c['max_daily_credits'],
                lambda:current_odds(key,regions=c['regions'],markets=c['featured_markets'])[0])
    prop_frames=[];prop_status=[]
    if not f.empty and c['max_prop_events']:
        t=f[['event_id','start_utc','home_team','away_team']].drop_duplicates()
        t['start_utc']=pd.to_datetime(t['start_utc'],utc=True,errors='coerce')
        now=pd.Timestamp.now(tz='UTC')
        t=t[(t['start_utc']>now)&(t['start_utc']<now+pd.Timedelta(hours=72))]
        t=t.sort_values('start_utc').head(c['max_prop_events'])
        for _,event in t.iterrows():
            event_id=str(event['event_id'])
            cost=len(c['prop_markets'].split(','))*len(c['prop_regions'].split(','))
            def fetch(evt=event_id):
                x=event_player_odds(key,evt,regions=c['prop_regions'])
                if x.empty:return x
                x=x.copy()
                x['start_utc']=event['start_utc'].isoformat()
                x['home_team']=event['home_team']; x['away_team']=event['away_team']
                return x
            p,ps=_read_fetch('props_'+event_id,c['props_ttl_minutes'],key,cost,
                c['max_daily_credits'],fetch)
            if not p.empty:
                for field in ('start_utc','home_team','away_team'):
                    if field not in p:p[field]=event[field]
                prop_frames.append(p)
            prop_status.append(ps)
    props=pd.concat(prop_frames,ignore_index=True) if prop_frames else empty
    status={'featured':fs,'props':prop_status[0] if prop_status else {
               'source':'niepobrane','error':'Brak najbliższych meczów w ofercie lub limit propów wynosi zero.',
               'stale':True},
            'daily_credits':_usage(),'daily_limit':c['max_daily_credits'],
            'featured_regions':c['regions'],'props_regions':c['prop_regions'],
            'max_prop_events':c['max_prop_events']}
    return f,props,status


def american_decimal(value):
    """Convert real ESPN moneyline prices; no guessed vig or odds."""
    try:
        s=str(value).strip().upper()
        if s in ('EVEN','EVENS'):return 2.0
        n=float(s)
        if n==0:return None
        return round((1+n/100) if n>0 else (1+100/abs(n)),4)
    except (ValueError,TypeError):return None


def parse_espn_scoreboard_prices(payload):
    """Only explicit published sportsbook moneylines. Skips missing publisher or price.

    This is an unofficial ESPN fallback, not a Betclic PL integration.
    """
    rows=[]
    for event in payload.get('events',[]):
        for cmp in event.get('competitions',[]):
            competitors=cmp.get('competitors',[]) or []
            teams={x.get('homeAway'):x.get('team',{}).get('displayName','') for x in competitors}
            home,away=teams.get('home',''),teams.get('away','')
            if not home or not away:continue
            for odds in cmp.get('odds',[]) or []:
                book=odds.get('provider') or {}
                name=str(book.get('name') or book.get('displayName') or '').strip()
                if not name:continue
                key='espn_'+str(book.get('id') or name.lower().replace(' ','_'))
                for side,team in [('home',home),('away',away)]:
                    side_data=odds.get(side+'TeamOdds') or {}
                    dec=american_decimal(side_data.get('moneyLine'))
                    if dec is None or dec<=1.0:continue
                    rows.append({'event_id':str(event.get('id') or cmp.get('id') or ''),
                        'start_utc':event.get('date'),'home_team':home,'away_team':away,
                        'bookmaker':name,'bookmaker_key':key,'market':'h2h','name':team,'line':None,
                        'odds':dec,'market_updated':odds.get('lastUpdated') or odds.get('updated') or ''})
    return pd.DataFrame(rows)


def parse_espn_summary_prices(payload, event):
    """Best-effort ESPN game-summary pickcenter moneylines (only explicit published prices).

    ESPN may omit this section or offer only a spread; never derive a moneyline.
    """
    rows=[]
    competitors=(event.get('competitions') or [{}])[0].get('competitors') or []
    teams={x.get('homeAway'):(x.get('team') or {}).get('displayName','') for x in competitors}
    home,away=teams.get('home'),teams.get('away')
    if not home or not away or not event.get('id'):return pd.DataFrame()
    candidates=payload.get('pickcenter') or []
    if not isinstance(candidates,list):return pd.DataFrame()
    for odds in candidates:
        if not isinstance(odds,dict):continue
        provider=odds.get('provider') or {}
        name=str(provider.get('name') or provider.get('displayName') or '').strip()
        if not name:continue
        key='espn_'+str(provider.get('id') or name.lower().replace(' ','_'))
        for side,team in (('home',home),('away',away)):
            side_odds=odds.get(side+'TeamOdds') or {}
            value=side_odds.get('moneyLine') if isinstance(side_odds,dict) else None
            dec=american_decimal(value)
            if dec is None or dec<=1:continue
            rows.append({'event_id':str(event['id']),'start_utc':event.get('date'),
                'home_team':home,'away_team':away,'bookmaker':name,'bookmaker_key':key,
                'market':'h2h','name':team,'line':None,'odds':dec,
                'market_updated':odds.get('lastUpdated') or odds.get('updated') or ''})
    return pd.DataFrame(rows)

def espn_moneylines():
    """Public ESPN fallback; includes pickcenter in game summaries when published.

    Does not promise bookmaker coverage, access in Poland or real-time prices.
    Returns an empty frame rather than inventing values if ESPN publishes no odds.
    """
    from sources import ESPN_SCOREBOARD, http_json
    now=datetime.now(timezone.utc)
    frames=[]; events_without_prices=[]
    for days in (0,1,2):
        date=(now+pd.Timedelta(days=days)).strftime('%Y%m%d')
        payload=http_json(ESPN_SCOREBOARD,params={'dates':date,'limit':100},timeout=10)
        parsed=parse_espn_scoreboard_prices(payload)
        if not parsed.empty:frames.append(parsed)
        published={str(x) for x in parsed['event_id']} if not parsed.empty else set()
        for event in payload.get('events',[]):
            event_id=str(event.get('id') or '')
            if event_id and event_id not in published:
                events_without_prices.append(event)
    # Summary endpoint can expose pickcenter data absent from scoreboard. A small cap
    # makes this fallback less likely to overload a public, undocumented data service.
    for event in events_without_prices[:5]:
        try:
            summary=http_json('https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary',
                              params={'event':event['id']},timeout=9)
            parsed=parse_espn_summary_prices(summary,event)
            if not parsed.empty:frames.append(parsed)
        except Exception:
            continue
    if not frames:return pd.DataFrame()
    return pd.concat(frames,ignore_index=True).drop_duplicates().reset_index(drop=True)
