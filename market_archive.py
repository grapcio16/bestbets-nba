"""Local append-only pregame bookmaker quotes, for honest *future* backtesting.

No calls to external services. Never saves API keys. No automatic background jobs;
the archive updates when the Streamlit app actually loads its odds panel.
"""
from __future__ import annotations
import csv
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd

LOCK=threading.RLock()
FIELDS=['collected_utc','event_id','start_utc','home_team','away_team','market',
        'player','line','selection','bookmaker','bookmaker_key','odds','updated']


def save_offers(offers, destination, now=None, minimum_gap_minutes=60):
    """Save prices at most hourly per exact bookmaker/outcome; skip started events."""
    if offers is None or offers.empty:return 0
    moment=pd.to_datetime(now,utc=True) if now is not None else pd.Timestamp.now(tz='UTC')
    path=Path(destination)
    with LOCK:
        existing={}
        if path.exists():
            try:
                with path.open(newline='',encoding='utf-8') as file:
                    for item in csv.DictReader(file):
                        key=tuple(item.get(k,'') for k in ('event_id','market','player','line','selection','bookmaker_key'))
                        stamp=pd.to_datetime(item.get('collected_utc'),utc=True,errors='coerce')
                        if pd.notna(stamp) and (key not in existing or stamp>existing[key]):existing[key]=stamp
            except (OSError,UnicodeError):return 0
        new=[]
        for obj in offers.to_dict('records'):
            try:
                starts=pd.to_datetime(obj.get('start_utc'),utc=True,errors='coerce')
                price=float(obj.get('odds'))
                if pd.isna(starts) or starts<=moment or not 1<price<1000:continue
                key=tuple(str(obj.get(k,'') if pd.notna(obj.get(k,'')) else '') for k in ('event_id','market','player','line','selection','bookmaker_key'))
                if not key[0] or not key[-1]:continue
                prev=existing.get(key)
                if prev is not None and (moment-prev).total_seconds()<minimum_gap_minutes*60:continue
                new.append({k: str(obj.get(k,'') if pd.notna(obj.get(k,'')) else '') for k in FIELDS})
                new[-1]['collected_utc']=moment.isoformat()
                existing[key]=moment
            except (TypeError, ValueError, OverflowError):continue
        if not new:return 0
        try:
            path.parent.mkdir(parents=True,exist_ok=True)
            with path.open('a',newline='',encoding='utf-8') as file:
                writer=csv.DictWriter(file,fieldnames=FIELDS)
                if file.tell()==0:writer.writeheader()
                writer.writerows(new)
        except OSError:return 0
        return len(new)


def load_archive(destination):
    path=Path(destination)
    if not path.exists():return pd.DataFrame(columns=FIELDS)
    try:return pd.read_csv(path,dtype={'event_id':str},on_bad_lines='skip')
    except (OSError,ValueError,UnicodeError):return pd.DataFrame(columns=FIELDS)


def snapshot_summary(destination):
    rows=load_archive(destination)
    if rows.empty:return {'rows':0,'events':0,'first':''}
    return {'rows':len(rows),'events':rows['event_id'].nunique(),
            'first':str(rows['collected_utc'].min())[:16]}


def historical_two_sided_lines(destination, now=None):
    """Construct real pregame OVER/UNDER pairs from archived same-book prices.

    No fabricated line history. Matching takes the newest recorded odds BEFORE tip.
    It returns only ended games, but the outcome still has to be verified against
    official/ESPN player logs in the separate backtester.
    """
    df=load_archive(destination)
    fields=['date','player','market','line','odds_over','odds_under',
            'home_team','away_team','event_id','bookmaker']
    if df.empty:return pd.DataFrame(columns=fields)
    now=pd.to_datetime(now,utc=True) if now is not None else pd.Timestamp.now(tz='UTC')
    df=df[df['market'].isin(['PTS','REB','AST','FG3M','PRA'])].copy()
    if df.empty:return pd.DataFrame(columns=fields)
    df['start_ts']=pd.to_datetime(df['start_utc'],utc=True,errors='coerce')
    df['quote_ts']=pd.to_datetime(df['collected_utc'],utc=True,errors='coerce')
    df['odds']=pd.to_numeric(df['odds'],errors='coerce')
    df['line']=pd.to_numeric(df['line'],errors='coerce')
    df['selection']=df['selection'].str.upper()
    # Do not treat matches as concluded until 5 hours after the scheduled tip.
    df=df[(df['start_ts']<now-pd.Timedelta(hours=5)) &
          (df['quote_ts']<df['start_ts']) & (df['odds']>1) &
          df['line'].notna() & df['selection'].isin(['OVER','UNDER'])]
    if df.empty:return pd.DataFrame(columns=fields)
    group=['event_id','bookmaker_key','player','market','line','selection']
    df=df.sort_values('quote_ts').drop_duplicates(group,keep='last')
    wide=df.pivot_table(index=['event_id','bookmaker_key','player','market','line'],
            columns='selection',values='odds',aggfunc='last').reset_index()
    if not {'OVER','UNDER'}.issubset(wide.columns):return pd.DataFrame(columns=fields)
    wide=wide.dropna(subset=['OVER','UNDER'])
    if wide.empty:return pd.DataFrame(columns=fields)
    props=df.drop_duplicates(['event_id','bookmaker_key','player','market','line'],keep='last')
    merged=wide.merge(props[['event_id','bookmaker_key','player','market','line','start_ts','home_team','away_team','bookmaker']],
       on=['event_id','bookmaker_key','player','market','line'],how='left')
    # NBA scoreboard game-date is typically in US Eastern (not UTC).
    merged['date']=merged['start_ts'].dt.tz_convert('America/New_York').dt.strftime('%Y-%m-%d')
    merged=merged.rename(columns={'OVER':'odds_over','UNDER':'odds_under'})
    # ONE representative market per match/player/stat: avoid counting the same
    # outcome many times just because 10 bookmakers offered 10 price variants.
    keys=['event_id','player','market']
    merged['_book_count']=merged.groupby(keys+['line'])['bookmaker_key'].transform('nunique')
    merged=(merged.sort_values(keys+['_book_count','line','bookmaker'],
               ascending=[True,True,True,False,True,True],kind='stable')
               .drop_duplicates(keys,keep='first'))
    return merged[fields].reset_index(drop=True)
