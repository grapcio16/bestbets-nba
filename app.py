"""BestBets v6.3: mobile and public deployment preparation with preserved analysis."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
import html
import math
import os

import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
import streamlit as st
from PIL import Image

from core import (STAT_NAMES, norm_name, normalize_logs, calc_projection, prop_probability,
    value_assessment, rolling_backtest, backtest_external_lines, calibration_summary,
    calibration_bins, league_context, project_team_total, chronological_calibration_check, calibration_apply)
from sources import (DATASETS, nba_stats, game_logs, extended_set, schedule, injuries,
    current_odds, event_player_odds, OFFICIAL_INJURIES, ESPN_INJURIES, NBA_CDN_SCHEDULE)
from teams import TEAM_MAP, standardize_teams
from odds_fetcher import automatic_odds
from simulation_view import render_simulations
from odds_engine import normalized_offers, best_prices, player_edges, edge_metrics, legend_for, MARKET_LABELS, LABELS
from market_archive import save_offers, snapshot_summary, historical_two_sided_lines

PATH=Path(__file__).resolve().parent
WARSAW=ZoneInfo('Europe/Warsaw')
ARCHIVE_PATH=PATH/'data'/'historyczne_kursy.csv'
SEASON='2026-27'
MARKET_API={'player_points':'PTS','player_rebounds':'REB','player_assists':'AST',
            'player_threes':'FG3M','player_points_rebounds_assists':'PRA'}

st.set_page_config(page_title='BestBets | NBA Intelligence',page_icon=Image.open(Path(__file__).resolve().parent/'assets'/'bestbets_icon.png'),layout='wide',initial_sidebar_state='auto')
CSS="""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Space+Grotesk:wght@500;600;700;800&display=swap');
:root{--gold:#f3bf60;--ink:#eaf0f7;--muted:#9ba9bc;--panel:#111a28;--line:#263346;}
html,body,[class*="css"]{font-family:'DM Sans',sans-serif}
.stApp{background:radial-gradient(ellipse at 90% -10%,#273044 0%,#0b121d 40%,#080d15 90%);color:var(--ink)}
.block-container{max-width:1480px;padding-top:1.45rem;padding-bottom:3rem}
[data-testid="stSidebar"]{background:linear-gradient(180deg,#111926,#0b121b);border-right:1px solid #2b3445}
h1,h2,h3,h4{font-family:'Space Grotesk',sans-serif !important;letter-spacing:-.025em}
h2{font-size:1.58rem !important}h3{font-size:1.17rem !important}
[data-testid="stMetric"]{background:linear-gradient(135deg,#192335,#121c2b);border:1px solid #2a3a50;border-radius:16px;padding:17px 18px}
[data-testid="stMetricValue"]{color:#fff!important;font-family:'Space Grotesk',sans-serif;font-weight:700}
[data-testid="stMetricLabel"]{color:#9baabf!important}
div[data-testid="stDataFrame"]{border:1px solid #2a3a4f;border-radius:14px;overflow:hidden}
div[data-testid="stTabs"] button{font-weight:700}
.stButton button[kind="primary"],.stDownloadButton button{background:linear-gradient(115deg,#f9d68b,#eaa645);border:1px solid #f2c778;color:#141414;font-weight:800;border-radius:12px}
.stButton button{border-radius:10px}
[data-baseweb="select"]>div,[data-baseweb="input"]>div{background:#182335;border-color:#31435c}
.bb-hero{display:flex;align-items:center;gap:23px;padding:25px 28px;margin-bottom:20px;background:linear-gradient(115deg,rgba(234,183,88,.20),rgba(28,41,61,.92) 45%,rgba(16,25,39,.98));border:1px solid #776038;border-radius:24px;box-shadow:0 16px 55px rgba(0,0,0,.2)}
.bb-coin{width:92px;height:92px;flex-shrink:0;display:grid;place-items:center;border-radius:100%;border:6px double #ffe3a3;background:radial-gradient(circle at 27% 21%,#fff1ae,#f1bb54 58%,#a96d28);box-shadow:0 0 36px rgba(250,187,84,.18);font:800 33px 'Space Grotesk',sans-serif;color:#2f210d}
.bb-kicker{font:700 11px 'DM Sans',sans-serif;letter-spacing:.19em;color:#ffd88e;text-transform:uppercase}
.bb-title{font:800 48px/1.08 'Space Grotesk',sans-serif;letter-spacing:-.055em;color:#f4f6fa;margin:7px 0 6px}
.bb-title span{color:#f5c46b}.bb-sub{color:#b0bdcf;line-height:1.55;max-width:800px;font-size:14px}
.bb-row{display:flex;justify-content:space-between;align-items:center;gap:12px;margin:6px 0 12px}
.bb-tag{display:inline-flex;padding:5px 10px;background:#2b261c;border:1px solid #6b522c;border-radius:999px;color:#f5c46b;font-size:11px;font-weight:800;letter-spacing:.04em}
.bb-muted{color:#9eafc2;font-size:13px}
.bb-panel{padding:16px 19px;border-radius:15px;border:1px solid #29394c;background:linear-gradient(180deg,#182338,#121b2a);margin:8px 0 18px}
.bb-panel strong{color:#fff}.bb-panel p{margin:5px 0;color:#aab8c9;font-size:13px;line-height:1.65}
.bb-warning{padding:12px 16px;background:#2d261b;border:1px solid #7f5f2f;border-radius:12px;color:#f5d8a6;font-size:13px}
.bb-healthy{color:#8bdcae;font-weight:700}.bb-danger{color:#fb9a99;font-weight:700}
.bb-legend{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:9px 15px;margin:8px 0 19px}
.bb-legend > div{background:#101a29;border:1px solid #26384a;border-radius:10px;padding:9px 11px}
.bb-legend strong{display:block;color:#e4eefa;font-size:11px;line-height:1.3}
.bb-legend span{display:block;color:#8fa3bc;font-size:10px;line-height:1.5;margin-top:3px}
.bb-glow{border:1px solid #826737;background:linear-gradient(125deg,#2a2319,#1a2839);border-radius:16px;padding:16px 18px;margin-bottom:12px}
.bb-glow b{color:#ffda8f;font-size:24px}.bb-glow p{font-size:11px;color:#aab6c8}
.bb-footer{border-top:1px solid #233347;margin-top:32px;padding:20px 0;color:#8294aa;font-size:12px}
@media(max-width:750px){.bb-hero{gap:12px;padding:17px}.bb-coin{width:60px;height:60px;border-width:3px;font-size:23px}.bb-title{font-size:32px}.bb-sub{font-size:12px}.block-container{padding:1rem .65rem 2rem}}
</style>
"""
CSS += """
<style>
.bb-gamecard{border:1px solid #3b4560;background:linear-gradient(112deg,#192334,#101a29);border-radius:19px;padding:16px 20px;margin:12px 0 19px;box-shadow:0 7px 18px rgba(0,0,0,.14)}
.bb-gamehead{display:flex;justify-content:space-between;gap:10px;color:#9fb3ce;font-size:12px;font-weight:700;letter-spacing:.02em}
.bb-gamehead span{color:#f4ce81}.bb-versus{display:grid;grid-template-columns:1fr 48px 1fr;align-items:center;text-align:center;gap:8px;margin:15px 0 10px}
.bb-versus>div{display:flex;flex-direction:column;justify-content:center;align-items:center;gap:5px;min-width:0}
.bb-versus strong{font:700 17px 'Space Grotesk',sans-serif;color:#f4f7fa;text-align:center}
.bb-versus small{font-size:11px;color:#96a4b5}.bb-versus b{font-size:23px;color:#f6c770}
.bb-at{font-weight:800;color:#8a9aaf}.bb-winbar{height:10px;display:flex;overflow:hidden;border-radius:99px;background:#334154}
.bb-winlabels{display:flex;justify-content:space-between;color:#cdd8e9;font-size:12px;font-weight:800;margin:8px 0}
.bb-gamefooter{border-top:1px solid #30435b;margin-top:11px;padding-top:12px;font-size:12px;color:#b3c3d6}
.bb-gamefooter b{color:#f6d18b}
@media(min-width:900px){.bb-gamecard{max-width:1050px}.bb-versus strong{font-size:20px}}
@media(max-width:680px){.bb-versus{grid-template-columns:1fr 30px 1fr}.bb-versus strong{font-size:14px}}
</style>
"""
# v6.3: smaller screens and web-app shortcuts; keep desktop appearance unchanged.
CSS += """
<style>
@media (max-width: 850px) {
  .block-container {padding: .65rem .65rem 2rem;max-width:100%}
  .bb-hero {border-radius:16px;gap:12px;padding:14px;margin-bottom:16px}
  .bb-title {font-size:clamp(27px,7vw,37px);line-height:1.12}
  .bb-kicker {font-size:9px;letter-spacing:.10em}
  .bb-coin {height:56px;width:56px;border-width:3px;font-size:21px}
  .bb-sub {font-size:12px}
  .bb-gamecard {padding:13px;border-radius:14px}
  .bb-gamehead {font-size:10px}
  .bb-versus {grid-template-columns:minmax(0,1fr) 22px minmax(0,1fr);gap:3px}
  .bb-versus strong {font-size:12px;overflow-wrap:anywhere}
  .bb-versus b {font-size:18px}
  .bb-versus small, .bb-gamefooter {font-size:10px}
  .bb-legend {grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:6px}
  [data-testid="stMetricValue"] {font-size:clamp(21px,5vw,30px)}
  [data-testid="stMetric"] {padding:11px;border-radius:12px}
  [data-testid="stDataFrame"] {max-width:100%;overflow-x:auto}
  [data-testid="stDialog"] {max-width:min(96vw,1150px)}
  div[data-testid="stHorizontalBlock"] {row-gap:10px}
}
@media (max-width: 480px) {
  .bb-hero {align-items:flex-start}
  .bb-versus strong {font-size:11px}
  .bb-winlabels {font-size:10px}
  .bb-sub {line-height:1.4}
}
</style>
"""
st.markdown(CSS,unsafe_allow_html=True)

@st.cache_data(ttl=1800,show_spinner=False)
def load_schedule(nonce):return schedule(refresh=nonce>0)

@st.cache_data(ttl=1800,show_spinner=False)
def load_injuries(nonce):return injuries(refresh=nonce>0)

@st.cache_data(ttl=3600,show_spinner=False)
def load_logs(season,nonce):return game_logs(season,refresh=nonce>0)

@st.cache_data(ttl=3600,show_spinner=False)
def load_dataset(name,season,nonce):return extended_set(name,season,refresh=nonce>0)

@st.cache_data(ttl=3600,show_spinner=False)
def load_backtest(logs,market,min_games):return rolling_backtest(logs,market,min_games=min_games)


def pill(status):
    age=status.get('age_min',0)
    source=status.get('source','brak źródła')
    if status.get('stale'):st.warning(f'Dane nieaktualne / cache sprzed {age} min. Źródło nie odpowiedziało. {status.get("warning","")}')
    else:st.caption(f'Źródło: {source} · aktualizacja: {status.get("timestamp","?")[:19]} UTC')


def safe(txt):return html.escape(str(txt))

def mini_legend(columns, overrides=None):
    """Small text positioned BELOW the corresponding data block, never a modal."""
    lookup=dict(legend_for(columns))
    if overrides:lookup.update(overrides)
    if not lookup:return
    pieces=[]
    for name,definition in lookup.items():
        pieces.append(f'<div><strong>{safe(name)}</strong><span>{safe(definition)}</span></div>')
    st.markdown('<div class="bb-legend">'+''.join(pieces)+'</div>',unsafe_allow_html=True)


def labelled_metric(container,name,value,description,delta=None):
    container.metric(name,value,delta=delta)
    with container: st.caption(description)


def market_prices_view(df,limit=180):
    visible=[c for c in ['Mecz','Początek (PL)','Rynek','Zawodnik','Linia','Wariant','Bukmacher','Najwyższy kurs',
                         'Najniższy kurs','Liczba firm','Różnica kursów (%)','Aktualizacja (UTC)'] if c in df]
    if df.empty:
        st.info('Brak porównywalnych kursów. Aplikacja nie zastępuje braków przykładowymi kwotami.')
        return
    st.dataframe(df[visible].head(limit),hide_index=True,use_container_width=True,height=min(610,70+min(limit,len(df))*35),
        column_config={c:st.column_config.Column(c,help=LABELS[c]) for c in visible if c in LABELS})
    mini_legend(visible)





def row_note(title,body):
    st.markdown(f'<div class="bb-panel"><strong>{safe(title)}</strong><p>{safe(body)}</p></div>',unsafe_allow_html=True)


def get_logs():
    try:
        raw,meta=load_logs(season,st.session_state.nonce)
        if meta.get('coverage'):
            st.warning(f'Źródło zapasowe NBA CDN: zsynchronizowano {meta["coverage"]}. To mogą być NIEPEŁNE dane sezonowe. Kliknij „Odśwież dostępne dane”, aby pobrać kolejną partię spotkań.')
        return normalize_logs(raw),meta
    except Exception as ex:
        st.error('Nie można pobrać logów zawodników z NBA Stats. '+str(ex))
        st.info('NBA Stats może ograniczać zapytania z hostingów. Inne zakładki nadal działają, jeżeli ich źródła są dostępne.')
        return None,None


def get_team():
    try:
        base,mb=load_dataset('Drużyny • podstawowe',season,st.session_state.nonce)
        adv,ma=load_dataset('Drużyny • advanced (pace/def)',season,st.session_state.nonce)
        return standardize_teams(base), standardize_teams(adv), (mb,ma)
    except Exception as ex:
        st.warning('Statystyki zaawansowane drużyn są niedostępne: '+str(ex))
        return pd.DataFrame(),pd.DataFrame(),None


def schedule_page(sched,inj=None):
    st.subheader('Terminarz NBA — godziny polskie')
    if sched is None or sched.empty:
        st.info('Nie udało się załadować terminarza. Odśwież dane i sprawdź, czy NBA CDN lub ESPN odpowiada.');return
    today=datetime.now(WARSAW)
    days=st.slider('Ile najbliższych dni pokazać?',1,14,5,key='schedule_days')
    only_upcoming=st.checkbox('Tylko mecze jeszcze nierozpoczęte',value=True)
    v=sched.copy()
    v['lokalna']=v['start_utc'].dt.tz_convert('Europe/Warsaw')
    v=v[v['lokalna'].notna()]
    if only_upcoming:v=v[v['start_utc']>=pd.Timestamp.now(tz='UTC')-pd.Timedelta(minutes=5)]
    v=v[v['lokalna']<pd.Timestamp(today+timedelta(days=days))]
    if v.empty:st.info('Brak meczów spełniających filtry.');return
    v['Termin (PL)']=v['lokalna'].dt.strftime('%d.%m.%Y %H:%M')
    v['Spotkanie']=v['away']+' @ '+v['home']
    v['Wynik']=v['away_score'].fillna('-').astype(str)+' : '+v['home_score'].fillna('-').astype(str)
    v['Status']=v['status']
    st.dataframe(v[['Termin (PL)','Spotkanie','Status','Wynik','game_id']],hide_index=True,use_container_width=True,height=min(550,len(v)*36+45))
    mini_legend(['Początek (PL)','Mecz'],{'Termin (PL)':'Termin w lokalnym czasie polskim','Spotkanie':'Drużyna gości @ gospodarze','Status':'Informacja, czy mecz się rozpoczął/ukończył','Wynik':'Wynik gości i gospodarzy','game_id':'Unikatowy numer meczu NBA'})
    st.download_button('Eksportuj terminarz CSV',v.to_csv(index=False).encode('utf-8-sig'),file_name='bestbets_terminarz.csv',mime='text/csv')


def injury_status_for(name,inj):
    if inj is None or inj.empty:return None
    v=inj[inj['player'].map(norm_name)==norm_name(name)]
    return None if v.empty else v.iloc[0].to_dict()


def label_status(info):
    if not info:return ('Brak wpisu w ESPN (nie potwierdza pełnej dostępności)',False)
    status=str(info.get('status','')).lower()
    blocked= any(x in status for x in ('out','inactive','suspended','injured reserve'))
    return (f"{info.get('status')} — ESPN",blocked)


def uploaded_lines():
    st.write('**Linie z Betclic Polska (CSV, ręczne)**')
    st.caption('Wgraj plik z faktycznymi aktualnymi kursami; nie są pobierane z Betclic.pl automatycznie.')
    template=pd.DataFrame(columns=['player','market','line','odds_over','odds_under','opponent','source'])
    st.download_button('Pobierz szablon CSV',template.to_csv(index=False).encode('utf-8-sig'),file_name='bestbets_kursy_szablon.csv',mime='text/csv')
    u=st.file_uploader('Kursy over/under',type=['csv'],key='uploaded_odds')
    if not u:return None
    try:
        lines=pd.read_csv(u)
        lines.columns=[str(c).strip().lower() for c in lines.columns]
        required={'player','market','line','odds_over','odds_under'}
        if not required.issubset(lines.columns):raise ValueError('Brakuje: '+', '.join(sorted(required-set(lines.columns))))
        for c in ['line','odds_over','odds_under']:lines[c]=pd.to_numeric(lines[c],errors='coerce')
        lines['market']=lines['market'].astype(str).str.upper()
        return lines
    except Exception as exc:
        st.error(f'Błąd pliku CSV: {exc}');return None


def lines_from_api_props(df,book):
    if df is None or df.empty:return pd.DataFrame()
    subset=df[df['bookmaker_key']==book].copy()
    subset['market']=subset['market'].map(MARKET_API)
    subset=subset[subset['market'].notna() & subset['player'].notna()].copy()
    if subset.empty:return pd.DataFrame()
    subset['side']=subset['side'].astype(str).str.upper()
    p=subset.pivot_table(index=['player','market','line'],columns='side',values='odds',aggfunc='first').reset_index()
    p.columns=[str(x).lower() if isinstance(x,str) else x for x in p.columns]
    if 'over' not in p or 'under' not in p:return pd.DataFrame()
    return p.rename(columns={'over':'odds_over','under':'odds_under'}).dropna(subset=['odds_over','odds_under'])


def upcoming_watchlist(logs,sched,inj,team_ctx,league_avg,days=4):
    """Roster-matched estimates for games already in NBA CDN schedule; no odds involved."""
    if sched is None or sched.empty or logs is None or logs.empty:return pd.DataFrame()
    now=pd.Timestamp.now(tz='UTC')
    upcoming=sched[(sched['start_utc']>=now)&(sched['start_utc']<now+pd.Timedelta(days=days))].copy()
    upcoming=upcoming.drop_duplicates('game_id')
    if upcoming.empty:return pd.DataFrame()
    teams={}
    for _,g in upcoming.iterrows():
        if not g.get('home') or not g.get('away'):continue
        teams.setdefault(g['home'],(g['away'],g['home']+' – '+g['away'],g['start_utc']))
        teams.setdefault(g['away'],(g['home'],g['away']+' – '+g['home'],g['start_utc']))
    latest=logs.sort_values('GAME_DATE').groupby('PLAYER_NAME').tail(1)
    latest=latest[latest['TEAM_ABBREVIATION'].isin(teams)].copy()
    rows=[]
    for _,r in latest.iterrows():
        name=r['PLAYER_NAME']; team=r['TEAM_ABBREVIATION']
        g=logs[logs['PLAYER_NAME']==name]
        if len(g)<3:continue
        info=injury_status_for(name,inj)
        status,blocked=label_status(info)
        if blocked:continue
        opp,match,t=teams[team]
        projections={}
        for market in STAT_NAMES:
            try:projections[market]=calc_projection(g,market,opp,team_ctx,league_avg)
            except ValueError:pass
        if not projections:continue
        rows.append({'Mecz (PL)':t.tz_convert('Europe/Warsaw').strftime('%d.%m %H:%M'),
          'Spotkanie':match,'Zawodnik':name,'Drużyna':team,'Rywal':opp,
          'Minuty':projections['PTS']['estimated_minutes'],
          'Punkty':projections['PTS']['prediction'],
          'Zbiórki':projections['REB']['prediction'],
          'Asysty':projections['AST']['prediction'],
          'Trójki':projections['FG3M']['prediction'],
          'PRA':projections['PRA']['prediction'],
          'Występy':projections['PTS']['sample_size'],
          'Status ESPN':status})
    return pd.DataFrame(rows)


def analyze_lines(lines,logs,inj,teams=None,averages=None,calibrator=None,calibrator_market=None):
    if lines is None or lines.empty:return pd.DataFrame()
    results=[]
    game_teams=None
    if 'TEAM_ABBREVIATION' in logs:pass
    lognames={norm_name(x):x for x in logs['PLAYER_NAME'].dropna().unique()}
    for _,row in lines.iterrows():
        try:
            name=lognames.get(norm_name(row['player']))
            if not name:continue
            market=str(row['market']).upper()
            if market not in STAT_NAMES:continue
            hist=logs[logs['PLAYER_NAME']==name]
            if hist.empty:continue
            injured=injury_status_for(name,inj)
            status,blocked=label_status(injured)
            if blocked:continue
            opponent=str(row.get('opponent','')).upper().strip()
            forecast=calc_projection(hist,market,opponent=opponent,
                team_context=teams,averages=averages)
            if forecast['sample_size']<5:continue
            for side,col,other in [('OVER','odds_over','odds_under'),('UNDER','odds_under','odds_over')]:
                odds=float(row[col])
                if odds<=1:continue
                comparison=value_assessment(forecast,float(row['line']),side,odds,float(row[other]))
                is_calibrated=calibrator is not None and market==calibrator_market
                used_prob=comparison['p_model']
                if is_calibrated:
                    p_over_raw=prop_probability(forecast,float(row['line']),'OVER')
                    p_over_adj=calibration_apply(p_over_raw,calibrator)
                    used_prob=p_over_adj if side=='OVER' else 1-p_over_adj
                ev_used=used_prob*odds-1
                results.append({'Zawodnik':name,'Drużyna':hist.iloc[-1]['TEAM_ABBREVIATION'],
                    'Rynek':market,'Linia':row['line'],'Typ':side,'Kurs':odds,
                    'Prognoza':forecast['prediction'],'Minuty prognozowane':forecast['estimated_minutes'],
                    'Korekta matchup':forecast['matchup_factor'],
                    'Szansa modelu (%)':round(used_prob*100,1),
                    'Model skalibrowany':('TAK' if is_calibrated else 'NIE'),
                    'Próg opłacalności (%)':round(comparison['p_break_even']*100,1),
                    'EV model (%)':round(ev_used*100,1),
                    'Przewaga (%)':round(100*(used_prob-comparison['p_break_even']),1),'Próba':forecast['sample_size'],
                    'Wiarygodność':forecast['reliability'],'Kontuzja':status,
                    'Źródło kursu':row.get('source','wgrany CSV')})
        except (ValueError,TypeError,KeyError,ZeroDivisionError):continue
    out=pd.DataFrame(results)
    if out.empty:return out
    return out.sort_values('EV model (%)',ascending=False)


if 'nonce' not in st.session_state:st.session_state.nonce=0
if 'api_data' not in st.session_state:st.session_state.api_data=pd.DataFrame()
if 'api_props' not in st.session_state:st.session_state.api_props=pd.DataFrame()
if 'api_key' not in st.session_state:st.session_state.api_key=''

with st.sidebar:
    st.markdown('<div style="font-size:22px;font-family:Space Grotesk;font-weight:800;color:#f5c46b;margin:4px 0 20px">🪙 BestBets <small style="color:#8e9fb2;font-size:11px">NBA / v6.3</small></div>',unsafe_allow_html=True)
    page=st.radio('Nawigacja',[
        '🏠 Centrum', '📆 Terminarz', '🏀 Symulacje 5000', '🧑‍🚀 Zawodnicy', '🏟️ Drużyny',
        '💹 Kursy i value','🧪 Backtesting', '📚 NBA Data Lab', '📱 Telefon i publikacja'],index=0,label_visibility='collapsed')
    season=st.selectbox('Sezon', ['2026-27','2025-26','2024-25'],index=0)
    st.divider()
    if st.button('↻ Odśwież dostępne dane',use_container_width=True):
        st.session_state.nonce+=1
        st.rerun()
    st.caption('Terminarz: NBA CDN → ESPN · NBA Stats: oficjalne dane · kontuzje: ESPN · kursy: The Odds API (wymaga jednorazowego klucza).')
    st.caption('BestBets to narzędzie do analizy danych, bez gwarancji zysków.')

st.markdown('''<div class="bb-hero">
<div class="bb-coin">BB</div><div>
<div class="bb-kicker">NBA intelligence platform · season 2026–27</div>
<div class="bb-title">Best<span>Bets</span></div>
<div class="bb-sub">Oficjalne statystyki NBA, analiza matchupów, przewidywane minuty, raport kontuzji i porównanie kursów. Wszystko w jednym panelu, z widocznymi ograniczeniami danych.</div>
</div></div>''',unsafe_allow_html=True)

if page == '🏠 Centrum':
    st.markdown('### Panel główny')
    c1,c2,c3,c4=st.columns(4)
    labelled_metric(c1,'Terminarz','NBA CDN / ESPN','NBA oficjalnie, ESPN jako zapasowe źródło')
    labelled_metric(c2,'Sezon',season,'Sezon rozgrywek wybrany do analiz')
    labelled_metric(c3,'Rynki zawodników','5','PTS, REB, AST, 3PM i PRA')
    labelled_metric(c4,'Kursy','The Odds API','Automatycznie tylko po skonfigurowaniu klucza')
    r1,r2=st.columns([1.6,1])
    with r1:
        st.markdown('#### Najbliższe mecze')
        try:
            sched,meta=load_schedule(st.session_state.nonce)
            now=pd.Timestamp.now(tz='UTC'); x=sched[(sched['start_utc']>=now)&(sched['start_utc']<now+pd.Timedelta(days=3))].head(14).copy()
            if x.empty:st.info('Brak potwierdzonych nadchodzących meczów w ciągu 3 dni.')
            else:
                x['Start (PL)']=x['start_utc'].dt.tz_convert('Europe/Warsaw').dt.strftime('%d.%m %H:%M')
                x['Mecz']=x['away']+' @ '+x['home']
                st.dataframe(x[['Start (PL)','Mecz','status']],hide_index=True,use_container_width=True,height=455)
                mini_legend([],{'Start (PL)':'Data i godzina spotkania w Polsce','Mecz':'Goście @ gospodarze','status':'Etap spotkania: przed grą, na żywo lub zakończone'})
            if 'ESPN' in meta.get('source',''):
                st.info('NBA CDN blokuje pobieranie terminarza. Wyświetlam spotkania z ESPN (źródło zastępcze).')
            pill(meta)
        except Exception as exc:
            st.error('Nie udało się pobrać terminarza (NBA CDN ani ESPN): '+str(exc))
    with r2:
        st.markdown('#### Injury report')
        try:
            inj,meta=load_injuries(st.session_state.nonce)
            if inj.empty:st.info('ESPN nie zwrócił rozpoznawalnych rekordów kontuzji. Nie oznacza to, że wszyscy są zdrowi.')
            else:
                st.metric('Wpisy w raporcie ESPN',len(inj))
                st.dataframe(inj[['player','team','status']].head(11),hide_index=True,use_container_width=True,height=420)
                mini_legend([],{'player':'Zawodnik z wpisem w raporcie ESPN','team':'Drużyna gracza','status':'Status według ESPN, nie oficjalna decyzja trenerów'})
            pill(meta)
        except Exception as exc:st.warning('Raport ESPN niedostępny: '+str(exc))
        st.link_button('Oficjalny raport NBA',OFFICIAL_INJURIES,use_container_width=True)
    row_note('Jak interpretować aplikację','Prognozy bazują na historii występów. Dane o kontuzjach z ESPN nie zastępują oficjalnego raportu przed meczem. Szacowane minuty są obliczane automatycznie z ostatnich występów, nie potwierdzone przez drużynę.')

elif page == '📆 Terminarz':
    try:
        sched,meta=load_schedule(st.session_state.nonce)
        schedule_page(sched)
        pill(meta)
    except Exception as exc:st.error(str(exc))

elif page == '🏀 Symulacje 5000':
    @st.fragment(run_every='30m')
    def simulations_panel():
        render_simulations(season,st.session_state.nonce,load_schedule,load_dataset,load_logs,load_injuries)
    simulations_panel()

elif page == '🧑‍🚀 Zawodnicy':
    st.subheader('Statystyki zawodników')
    logs,meta=get_logs()
    if logs is not None and not logs.empty:
        st.metric('Zawodnicy z występami w sezonie',logs['PLAYER_NAME'].nunique())
        people=sorted(logs['PLAYER_NAME'].unique().tolist())
        c1,c2=st.columns([2,1])
        player=c1.selectbox('Zawodnik',people)
        market=c2.selectbox('Statystyka',list(STAT_NAMES),format_func=lambda x:STAT_NAMES[x])
        sub=logs[logs['PLAYER_NAME']==player].sort_values('GAME_DATE')
        try:
            p=calc_projection(sub,market)
            v1,v2,v3,v4=st.columns(4)
            labelled_metric(v1,'Średnia',f"{p['season_avg']:.1f}",'Średnia z całego dostępnego sezonu')
            labelled_metric(v2,'Ostatnie 5',f"{p['last5']:.1f}",'Średnia z pięciu ostatnich występów')
            labelled_metric(v3,'Prognoza',f"{p['prediction']:.1f}",'Modelowa wartość na kolejny mecz, nie wynik pewny')
            labelled_metric(v4,'Szacowane minuty',f"{p['estimated_minutes']:.1f}",'Model czasu gry oparty na ostatnich meczach')
            hist=sub.tail(18).copy().sort_values('GAME_DATE')
            # Text categories contain the YEAR, preventing e.g. 02.11 sorting before 25.10.
            xlabels=hist['GAME_DATE'].dt.strftime('%d.%m.%Y').tolist()
            values=pd.to_numeric(hist[market],errors='coerce').tolist()
            fig=go.Figure()
            colors=['#58C6A3' if pd.notna(v) and v >= p['prediction'] else '#EEAE58' for v in values]
            fig.add_trace(go.Bar(
                x=xlabels,y=values,name='Ostatnie wyniki',marker_color=colors,
                text=[f'{v:g}' if pd.notna(v) else '' for v in values],textposition='outside',
                customdata=hist['MATCHUP'].fillna('—'),
                hovertemplate='<b>%{x}</b><br>Mecz: %{customdata}<br>Wynik: %{y}<extra></extra>'))
            fig.add_hline(y=p['prediction'],line_dash='dash',line_color='#91D8F7',
                          annotation_text=f'Prognoza {p["prediction"]:.1f}',annotation_position='top left')
            fig.update_xaxes(type='category',categoryorder='array',categoryarray=xlabels,
                title='Data meczu',tickangle=-35,showgrid=False)
            fig.update_yaxes(title=STAT_NAMES[market],rangemode='tozero',gridcolor='#2B3C53',zeroline=False)
            fig.update_layout(title=f'{player} — {STAT_NAMES[market]} (chronologicznie)',
                height=460,margin=dict(t=70,b=70,l=18,r=15),
                paper_bgcolor='rgba(0,0,0,0)',plot_bgcolor='rgba(0,0,0,0)',
                font_color='#CFDAE7',showlegend=False,bargap=.24)
            st.plotly_chart(fig,use_container_width=True)
            st.caption('Każdy słupek = jeden mecz, od najstarszego po lewej do najnowszego po prawej. Żółty = wynik niższy od prognozy; zielony = wynik równy prognozie lub wyższy. Jasnoniebieska linia = prognoza modelu, NIE linia bukmachera. Najedź na słupek, aby zobaczyć rywala.')
            st.dataframe(sub[['GAME_DATE','TEAM_ABBREVIATION','MATCHUP','MIN','PTS','REB','AST','FG3M','FG3A','PRA']].tail(20).sort_values('GAME_DATE',ascending=False),use_container_width=True,hide_index=True)
            mini_legend([],{'GAME_DATE':'Dzień rozegrania meczu','TEAM_ABBREVIATION':'Skrót drużyny gracza','MATCHUP':'Rywal i miejsce meczu','MIN':'Minuty na parkiecie','PTS':'Punkty zdobyte przez gracza','REB':'Zbiórki','AST':'Asysty','FG3M':'Celne rzuty za trzy','FG3A':'Próby rzutów za trzy','PRA':'Punkty + zbiórki + asysty'})
            st.download_button('Pobierz historię zawodnika',sub.to_csv(index=False).encode('utf-8-sig'),file_name='bestbets_zawodnik.csv',mime='text/csv')
            pill(meta)
        except ValueError as ex:st.info(str(ex))

elif page == '🏟️ Drużyny':
    st.subheader('Drużyny — skuteczność, tempo, obrona')
    base,adv,metas=get_team()
    if not base.empty:
        bcols=[x for x in ['TEAM_NAME','GP','W','L','PTS','REB','AST','FG3M','FG3A','FG3_PCT','TOV'] if x in base]
        st.dataframe(base[bcols],hide_index=True,use_container_width=True,height=450)
    if not adv.empty:
        st.markdown('#### Metryki zaawansowane NBA')
        acols=[x for x in ['TEAM_NAME','PACE','OFF_RATING','DEF_RATING','NET_RATING','TS_PCT','EFG_PCT'] if x in adv]
        st.dataframe(adv[acols],hide_index=True,use_container_width=True)
        if {'TEAM_NAME','NET_RATING'}.issubset(adv):
            x=adv.nlargest(15,'NET_RATING').sort_values('NET_RATING')
            fig=px.bar(x,x='NET_RATING',y='TEAM_NAME',orientation='h',color_discrete_sequence=['#EFB85C'],title='Net Rating — wybrane drużyny')
            fig.update_layout(height=480,paper_bgcolor='rgba(0,0,0,0)',plot_bgcolor='rgba(0,0,0,0)',font_color='#D8E1F0')
            st.plotly_chart(fig,use_container_width=True)
        st.download_button('Dane drużyn — CSV',adv.to_csv(index=False).encode('utf-8-sig'),file_name='bestbets_advanced.csv',mime='text/csv')
        if metas:
            for m in metas:pill(m)
    mini_legend(['GP','W','L','PACE','OFF_RATING','DEF_RATING','NET_RATING','TS_PCT'],
                {'GP':'Rozegrane mecze','W':'Zwycięstwa','L':'Porażki','PACE':'Tempo — liczba posiadań na 48 min',
                 'OFF_RATING':'Punkty zdobywane na 100 posiadań','DEF_RATING':'Punkty tracone na 100 posiadań (niżej = lepiej)',
                 'NET_RATING':'Różnica ratingu ataku i obrony na 100 posiadań','TS_PCT':'True Shooting — skuteczność uwzględniająca rzuty za 2, 3 i wolne'})
    row_note('Wskazówka','Drużynowe statystyki zaawansowane mogą być niedostępne, jeśli NBA Stats blokuje połączenia z hostingu. Aplikacja nie zastępuje ich wymyślonymi danymi.')

elif page == '💹 Kursy i value':
    st.subheader('Automatyczna porównywarka kursów NBA')
    row_note('Bez ręcznego wpisywania kursów',
      'Przy skonfigurowanym kluczu BestBets sam pobiera kursy, porównuje identyczne rynki i wybiera najwyższy kurs. '
      'Dostawca może obejmować Betclic FR — nie jest to Betclic Polska. Rynki graczy najczęściej pochodzą z regionu US; dostępność oferty w Polsce trzeba zweryfikować.')
    st.markdown('<div class="bb-warning">Wynik dodatni w modelu ≠ pewny zakład. Prawdopodobieństwa są eksperymentalne, a świeżość kursów zależy od limitu dostawcy. BestBets nigdy nie zastępuje brakujących danych wymyślonymi kursami.</div>',unsafe_allow_html=True)
    try: configured_key=str(st.secrets.get('ODDS_API_KEY','')).strip()
    except Exception: configured_key=''
    configured_key=configured_key or os.getenv('ODDS_API_KEY','').strip()

    @st.fragment(run_every='30m')
    def automatic_market_panel():
        feat,props,status=automatic_odds(configured_key)
        if not configured_key:
            st.markdown('#### Połączenie z dostawcą kursów')
            s1,s2,s3=st.columns(3)
            labelled_metric(s1,'The Odds API','Niepołączone','Nie ma jednorazowego klucza API; brak możliwości pobrania wielu ofert')
            labelled_metric(s2,'ESPN — bez klucza',str(len(feat))+' ofert','Darmowy odczyt tylko publikowanych kursów zwycięzcy; często brak danych')
            labelled_metric(s3,'Kursy zawodników','Niedostępne','PTS, REB, AST, 3PM i PRA wymagają zewnętrznej usługi z odpowiednimi rynkami')
            st.info('Aplikacja działa. Żeby uzyskać automatyczne porównanie kursów, potrzebne jest **jednorazowe połączenie z dostawcą**. Później BestBets pobiera dane sam, z uwzględnieniem limitów API.')
            st.markdown('**Konfiguracja na Twoim Windows 11 — tylko jeden raz:**')
            st.markdown('1. Otwórz stronę The Odds API i utwórz klucz.\n2. Zamknij czarne okno BestBets.\n3. W folderze `BestBets_NBA_v4` kliknij dwukrotnie `USTAW_KLUCZ_API.bat`.\n4. Wklej klucz w tym oknie (nie do czatu).\n5. Otwórz `START_BESTBETS.bat`, następnie zakładkę **Kursy i value**.')
            st.link_button('Strona The Odds API — klucz', 'https://the-odds-api.com/')
            st.caption('Oferty Betclic Polska nie są potwierdzone w tym API. Najwyższy kurs w aplikacji to najlepszy z dostarczonych ofert, a nie z całego rynku — dostępność w Polsce trzeba sprawdzić.')
            if status.get('featured',{}).get('error'):
                st.warning('Publiczny feed ESPN: '+str(status['featured']['error']))
            elif feat.empty:
                st.caption('ESPN nie opublikowało odczytywalnych kursów dla sprawdzonych spotkań. To nie błąd instalacji i nie oznacza, że mecze nie mają ofert u bukmacherów.')
        else:
            f_meta=status['featured'];p_meta=status['props']
            st.caption(f"Dostawca: The Odds API · rynek główny: {status['featured_regions']} · props: {status['props_regions']} · budżet lokalny: {status['daily_credits']}/{status['daily_limit']} kredytów dziennie (szacunkowo)")
            for label,m in [('Mecze',f_meta),('Rynki zawodników',p_meta)]:
                when=m.get('updated') or 'nigdy'
                st.caption(f"{label}: {m.get('source','?')} · ostatni odczyt {when} · {m.get('age_min','?')} min od odczytu")
                if m.get('error'):st.warning(f"{label}: {m['error']}")
                if m.get('stale'):st.warning(f'{label}: dane nie są świeże. Nie traktuj ich jako aktualnego kursu do obstawienia.')
        if not feat.empty and status.get('featured',{}).get('stale'):
            st.warning('UWAGA: kursy meczowe pochodzą ze starszej kopii. Nie traktuj ich jako aktualnej oferty bukmachera.')
        offers=normalized_offers(feat,props)
        # Only archive PRE-GAME real bookmaker quotes that were not marked stale.
        # This does not make new paid API requests and never saves the API key.
        if configured_key and not offers.empty:
            valid_parts=[]
            if not status.get('featured',{}).get('stale',True):
                valid_parts.append(offers[~offers['market'].isin(STAT_NAMES)])
            if not status.get('props',{}).get('stale',True):
                valid_parts.append(offers[offers['market'].isin(STAT_NAMES)])
            if valid_parts:
                save_offers(pd.concat(valid_parts,ignore_index=True),ARCHIVE_PATH)
        best=best_prices(offers)
        if not best.empty:
            b1,b2,b3,b4=st.columns(4)
            labelled_metric(b1,'Bukmacherzy',str(offers['bookmaker_key'].nunique()),'Liczba firm z kursami w odpowiedzi API')
            labelled_metric(b2,'Oferty kursowe',str(len(offers)),'Wszystkie pobrane warianty, także powtórzenia między firmami')
            labelled_metric(b3,'Unikalne porównania',str(len(best)),'Porównanie po meczu, rynku, zawodniku, linii i wariancie')
            labelled_metric(b4,'Rynki graczy',str(len(best[best['market'].isin(STAT_NAMES)])),'Warianty dla graczy; mogą nie być dostępne w każdym regionie')
        tabs=st.tabs(['🏆 Najlepsze dostępne kursy','📊 Model value graczy','🧮 Kalkulator (opcjonalnie)'])
        with tabs[0]:
            st.markdown('#### Najwyższy kurs u danego bukmachera')
            st.caption('Nie mieszamy różnych linii. Przykład: OVER 23.5 i OVER 24.5 są osobnymi rynkami; kursy na nie NIE są porównywalne.')
            if not best.empty:
                names=sorted(best['Rynek'].unique().tolist())
                selected=st.multiselect('Rynek — filtr widoku (opcjonalny)',names,default=names)
                shown=best[best['Rynek'].isin(selected)]
                market_prices_view(shown)
                st.download_button('Eksport porównania CSV',best.to_csv(index=False).encode('utf-8-sig'),
                                   file_name='bestbets_najlepsze_kursy.csv',mime='text/csv')
            else:
                st.info('Żadne porównywalne kursy nie zostały zwrócone przez podłączone źródło. To nie awaria aplikacji.')
                try:
                    sc,sc_meta=load_schedule(st.session_state.nonce)
                    near=sc[(sc['start_utc']>=pd.Timestamp.now(tz='UTC')) &
                            (sc['start_utc']<=pd.Timestamp.now(tz='UTC')+pd.Timedelta(days=3))].head(8).copy()
                    if not near.empty:
                        near['Start (PL)']=near['start_utc'].dt.tz_convert('Europe/Warsaw').dt.strftime('%d.%m %H:%M')
                        near['Mecz']=near['away']+' @ '+near['home']
                        st.markdown('**Nadchodzące mecze — terminarz dostępny, kursy jeszcze niedostępne**')
                        st.dataframe(near[['Start (PL)','Mecz']],hide_index=True,use_container_width=True)
                        mini_legend([],{'Start (PL)':'Data rozpoczęcia spotkania w czasie polskim','Mecz':'Goście @ gospodarze; brak kursu nie oznacza braku możliwości obstawienia meczu'})
                except Exception:
                    st.caption('Nie udało się załadować również zastępczego widoku najbliższych meczów.')
        with tabs[1]:
            st.markdown('#### Różnica między modelem a progiem kursu')
            st.caption('Podajemy dwa RÓŻNE wyniki: przewaga w punktach procentowych (pp) oraz EV w procentach (%).')
            prop_best=best[best['market'].isin(STAT_NAMES)].copy() if not best.empty else pd.DataFrame()
            if prop_best.empty:
                st.info('Brak automatycznych kursów over/under zawodników. Ten endpoint może być niedostępny w danym regionie, przy wyczerpanym limicie lub przed publikacją rynków przez bukmacherów.')
            else:
                logs,logs_meta=get_logs()
                try:inj,inj_meta=load_injuries(st.session_state.nonce)
                except Exception:
                    inj=pd.DataFrame(columns=['player','team','status','note'])
                    st.warning('Raport kontuzji niedostępny. Wyniki należy traktować ostrożnie.')
                team_ctx,med={},{}
                try:
                    adv,_=load_dataset('Drużyny • advanced (pace/def)',season,st.session_state.nonce)
                    team_ctx,med=league_context(standardize_teams(adv))
                except Exception:
                    st.caption('Pace i DEF RATING niedostępne z NBA Stats — użyto neutralnego współczynnika matchup 1.0.')
                edges=player_edges(prop_best,logs,inj,team_ctx,med)
                if edges.empty:
                    st.info('Nie można teraz ocenić opłacalności na danych graczy. Wymagane: kurs player prop z API oraz co najmniej 5 wcześniejszych występów z NBA Stats.')
                else:
                    st.warning('Wersja 6.2: surowe szanse NIE są skalibrowane na niezależnych historycznych kursach. „Szansa ostrożna” jest tylko stres-testem z korektą w kierunku 50%, NIE potwierdzoną szansą. Żaden wiersz nie jest zaleceniem obstawienia.')
                    q1,q2,q3=st.columns(3)
                    labelled_metric(q1,'Do sprawdzenia',str((edges['Ocena danych']=='WERYFIKUJ').sum()),
                        'Mniej flag jakości, ale model nadal nie został zweryfikowany na rzeczywistych kursach')
                    labelled_metric(q2,'Ostrożnie',str((edges['Ocena danych']=='OSTROŻNIE').sum()),
                        'Niepewny status, mała próba, duży błąd lub brak danych')
                    labelled_metric(q3,'Wstrzymane',str((edges['Ocena danych']=='WSTRZYMAJ').sum()),
                        'Kurs nieaktualny, mecz już się rozpoczął lub zawodnik jest wykluczony')
                    st.markdown('#### Ranking pod kontrolą jakości')
                    a,b,c=st.columns([2,2,1.5])
                    visible_risks=a.multiselect('Pokaż oceny danych',
                        ['WERYFIKUJ','OSTROŻNIE','WSTRZYMAJ'],default=['WERYFIKUJ','OSTROŻNIE'])
                    visible_markets=b.multiselect('Rynki zawodników',sorted(edges['Rynek'].unique().tolist()),
                        default=sorted(edges['Rynek'].unique().tolist()))
                    collapse_lines=c.checkbox('Jedna linia na rynek i zawodnika',value=True,
                        help='Ukrywa podobne, skorelowane warianty tego samego gracza i rynku. Pełne wyniki są w eksporcie CSV.')
                    shown=edges[edges['Ocena danych'].isin(visible_risks) & edges['Rynek'].isin(visible_markets)].copy()
                    if collapse_lines:
                        shown=shown.drop_duplicates(['event_id','player','market','selection'])
                    st.caption(f'Wyświetlane: {len(shown)} z {len(edges)} wariantów. Najpierw ocena danych, potem ostrożna wartość matematyczna. Brak gwarancji, że kurs jest dostępny w Polsce.')
                    cols=['Mecz','Zawodnik','Rynek','Linia','Wariant','Bukmacher','Najwyższy kurs',
                          'Ocena danych','Powody ostrożności','Próba','Testy walk-forward',
                          'MAE walk-forward','Prognoza','Minuty','Szansa modelu (%)',
                          'Szansa ostrożna (%)','Próg kursu (%)','Przewaga (pp)',
                          'EV ostrożne (%)','EV model (%)']
                    if shown.empty:
                        st.info('Brak analiz w aktualnym filtrze. Zmień ocenę danych lub rynek, aby zobaczyć wstrzymane warianty.')
                    else:
                        st.dataframe(shown[cols].head(150),hide_index=True,use_container_width=True,height=575,
                            column_config={c:st.column_config.Column(c,help=LABELS[c]) for c in cols if c in LABELS})
                        mini_legend(cols)
                        bars=shown.head(12)
                        chart=go.Figure(go.Bar(x=bars['Zawodnik']+' · '+bars['Wariant']+' '+bars['Linia'].astype(str),
                            y=bars['EV ostrożne (%)'],marker_color='#f3bf60',
                            text=bars['Ocena danych'],textposition='outside'))
                        chart.add_hline(y=0,line_color='#92a6be')
                        chart.update_layout(title='Stres-test EV (HEURYSTYKA, nie prognoza zwrotu)',
                            height=355,margin=dict(l=15,r=15,b=95,t=50),paper_bgcolor='rgba(0,0,0,0)',
                            plot_bgcolor='rgba(0,0,0,0)',font_color='#d6e0ed')
                        st.plotly_chart(chart,use_container_width=True)
                    st.download_button('Pobierz wszystkie analizy wraz z ostrzeżeniami CSV',
                        edges.to_csv(index=False).encode('utf-8-sig'),
                        file_name='bestbets_v62_kontrola_jakosci.csv',mime='text/csv')
                    snap=snapshot_summary(ARCHIVE_PATH)
                    row_note('Dodatkowa funkcja: automatyczne archiwum kursów',
                        f"Zapisane oferty: {snap['rows']} · mecze: {snap['events']}. "
                        'Dane odkładają się podczas otwierania/odświeżania zakładki kursów; '
                        'aplikacja nie działa w tle po zamknięciu serwera. '
                        'Rzeczywisty backtesting będzie możliwy po zakończeniu zarejestrowanych spotkań.')
        with tabs[2]:
            st.markdown('#### Opcjonalne obliczenie dla własnej linii')
            st.caption('Ten kalkulator jest dodatkowy. Automatyczne porównania działają bez wpisywania linii. W kalkulatorze wpisujesz tylko kurs i linię, a model sam liczy szansę gracza.')
            logs,meta=get_logs()
            if logs is not None and not logs.empty:
                players=sorted(logs['PLAYER_NAME'].dropna().unique().tolist())
                a,b,c=st.columns([2,1,1])
                player=a.selectbox('Zawodnik',players,key='v5_manual_player')
                market=b.selectbox('Statystyka',list(STAT_NAMES),format_func=lambda x:STAT_NAMES[x],key='v5_manual_market')
                side=c.selectbox('Wariant',['OVER','UNDER'],key='v5_manual_side')
                a,b=st.columns(2)
                line=a.number_input('Linia (np. 23.5)',min_value=0.5,value=20.5,step=.5,key='v5_manual_line')
                odds=b.number_input('Kurs dziesiętny (np. 1.85)',min_value=1.01,value=1.85,step=.01,key='v5_manual_odds')
                if float(line).is_integer():
                    st.info('Przy całkowitej linii możliwy jest zwrot stawki (push); prosty model dwuwynikowy może zawyżyć/zaniżyć EV. Użyj linii połówkowej.')
                else:
                    try:
                        p=calc_projection(logs[logs['PLAYER_NAME']==player],market)
                        m=edge_metrics(prop_probability(p,line,side),odds)
                        k1,k2,k3,k4=st.columns(4)
                        labelled_metric(k1,'Szansa modelu',f"{m['p_model_pct']:.2f}%",'Modelowa szansa zdarzenia — niekalibrowana')
                        labelled_metric(k2,'Próg kursu',f"{m['p_break_even_pct']:.2f}%",'Minimalna szansa według kursu; 100/kurs')
                        labelled_metric(k3,'Przewaga',f"{m['edge_pp']:+.2f} pp",'Różnica w punktach procentowych, nie procentowy zwrot')
                        labelled_metric(k4,'EV modelu',f"{m['ev_pct']:+.2f}%",'Oczekiwany modelowy zwrot; wynik zależy od trafności modelu')
                        st.progress(max(0,min(1,m['p_model_pct']/100)),text=f"Szansa modelu: {m['p_model_pct']:.1f}%")
                        st.caption(f"Prognoza: {p['prediction']:.1f} · minuty: {p['estimated_minutes']:.1f} · wcześniejsze mecze: {p['sample_size']}. Nie uznawaj tego za pewną przewagę bez backtestingu.")
                    except (ValueError,TypeError,KeyError) as ex:st.error(str(ex))
            else:st.info('Dla kalkulatora potrzebna jest historia występów z NBA Stats.')
    automatic_market_panel()

elif page == '🧪 Backtesting':
    st.subheader('Backtesting i kalibracja — bez przecieku danych z przyszłości')
    row_note('Dlaczego to ważne','W każdej prognozie używamy wyłącznie wcześniejszych występów. Automatyczne archiwum zbiera PRAWDZIWE ceny przed meczem. Zaczyna się ono teraz, nie odtwarza cudownie brakujących starych kursów. Test z liniami symulowanymi nie jest testem rentowności.')
    logs,meta=get_logs()
    if logs is not None:
        mode=st.radio('Rodzaj testu',['Automatycznie zapisane kursy','Symulowane linie (bez ROI)','Wgrane historyczne linie i kursy'],horizontal=True)
        market=st.selectbox('Rynek',list(STAT_NAMES),format_func=lambda x:STAT_NAMES[x],key='bt_market')
        test=pd.DataFrame()
        if mode.startswith('Automatycznie'):
            captured=historical_two_sided_lines(ARCHIVE_PATH)
            st.caption('BestBets zbiera kursy przed meczami, gdy otwierasz zakładkę „Kursy i value”. Czeka co najmniej 5 godzin od planowanego rozpoczęcia meczu. Nie generuje historycznych cen.')
            st.metric('Zapisane historyczne zestawy OVER + UNDER',len(captured))
            if not captured.empty:
                try:
                    test=backtest_external_lines(logs,captured[captured['market']==market])
                except Exception as ex:st.error('Błąd kontroli archiwum: '+str(ex))
            if test.empty:
                st.info('Jeszcze nie ma rozliczonych spotkań z zapisanymi przed meczem kursami i znanymi wynikami graczy. Dane zaczną się gromadzić od momentu uruchomienia funkcji.')
        elif mode.startswith('Symulowane'):
            min_games=st.slider('Minimum wcześniejszych meczów',5,20,8)
            if st.button('Uruchom walk-forward backtest',type='primary'):
                with st.spinner('Testowanie kolejnych meczów…'):
                    test=rolling_backtest(logs,market,min_games=min_games,max_rows=20000)
                    st.session_state.last_test=test
            elif 'last_test' in st.session_state:test=st.session_state.last_test
            st.caption('Próg testowy = średnia z ostatnich 10 meczów + 0,5; to nie są rzeczywiste kursy bukmachera.')
        else:
            st.markdown('CSV: `date,player,market,line,odds_over,odds_under` — dane historyczne zapisane **przed meczem**, nie odtworzone po wyniku.')
            sample=pd.DataFrame(columns=['date','player','market','line','odds_over','odds_under'])
            st.download_button('Pobierz szablon danych historycznych',sample.to_csv(index=False),file_name='bestbets_backtest_szablon.csv')
            h=st.file_uploader('Wgraj archiwalne linie i kursy',type=['csv'])
            if h:
                try:
                    lines_hist=pd.read_csv(h);lines_hist.columns=[str(c).lower().strip() for c in lines_hist.columns]
                    test=backtest_external_lines(logs,lines_hist)
                except Exception as ex:st.error(str(ex))
        if not test.empty:
            report=calibration_summary(test)
            m1,m2,m3,m4=st.columns(4)
            labelled_metric(m1,'Próba',report['n'],'Liczba obserwacji historycznych')
            labelled_metric(m2,'Brier score',report['brier'],'Błąd prawdopodobieństwa — mniejszy jest lepszy')
            labelled_metric(m3,'Log loss',report['logloss'],'Kara za błędne, pewne przewidywania — mniej = lepiej')
            labelled_metric(m4,'MAE prognozy',report['mae_projection'],'Średnia bezwzględna różnica wartości prognozy i wyniku')
            if 'return_per_unit' in test:
                st.metric('ROI (bez kosztów i ograniczeń)',f"{test['return_per_unit'].mean()*100:.1f}%")
                st.caption('To WYŁĄCZNIE wynik próby ze zarejestrowanych historycznych cen, a nie zweryfikowana przewaga strategii. Próba jest wybiórcza, a wynik nie uwzględnia opłat ani ograniczeń konta.')
            cal=calibration_bins(test)
            if not cal.empty:
                fig=go.Figure()
                fig.add_trace(go.Scatter(x=[0,1],y=[0,1],mode='lines',name='Idealna kalibracja',line=dict(dash='dash',color='#718096')))
                fig.add_trace(go.Scatter(x=cal['prognoza'],y=cal['trafienia'],mode='lines+markers',name='Model',line=dict(color='#F4C76B',width=3)))
                fig.update_layout(xaxis_title='Średnia prognoza P(over)',yaxis_title='Empiryczny udział over',height=385,paper_bgcolor='rgba(0,0,0,0)',plot_bgcolor='rgba(0,0,0,0)',font_color='#D6DFEB')
                st.plotly_chart(fig,use_container_width=True)
                st.dataframe(cal,hide_index=True,use_container_width=True)
                mini_legend([],{'prognoza':'Średnia deklarowana szansa modelu w grupie','trafienia':'Rzeczywista częstotliwość over w grupie','proba':'Liczba obserwacji w grupie'})
            st.download_button('Pobierz wyniki testu',test.to_csv(index=False).encode('utf-8-sig'),file_name='bestbets_backtest.csv',mime='text/csv')
            if report['n']<200:st.warning('Niewielka próba do oceny kalibracji. Potrzeba więcej meczów i historycznych linii.')
            check=chronological_calibration_check(test)
            if check is not None:
                st.markdown('#### Kalibracja na próbie odłożonej w czasie')
                row_note('Jak to działa',f"Pierwsze {check['train']} obserwacji służy do dopasowania kalibratora, a późniejsze {check['holdout']} do sprawdzenia. Dla rynków bukmacherskich używaj wyłącznie historycznych linii dostępnych przed meczami.")
                e1,e2=st.columns(2)
                e1.metric('Brier bez kalibracji',f"{check['brier_raw']:.4f}")
                e2.metric('Brier po kalibracji',f"{check['brier_calibrated']:.4f}")
                st.caption('Mniejszy Brier jest lepszy. Kalibracja nie musi poprawiać wyniku, szczególnie przy małej próbce lub symulowanych liniach.')
                if (mode.startswith('Wgrane') or mode.startswith('Automatycznie')) and check['brier_calibrated']<check['brier_raw']:
                    st.session_state.calibrator=check['calibrator']
                    st.session_state.calibrator_market=market
                    st.session_state.calibrator_season=season
                    st.success(f'Kalibrator {market} zapisano na tę sesję. Został sprawdzony na późniejszej próbie historycznej i poprawił Brier score.')
                st.download_button('Wyniki na odłożonej próbie CSV',check['holdout_frame'].to_csv(index=False).encode('utf-8-sig'),file_name='bestbets_holdout.csv')
        else:st.info('Brak zakończonych spotkań z odpowiednią historią danych. Uruchom test symulowany, wgraj kursy albo zbieraj automatyczne archiwum.')

elif page == '📚 NBA Data Lab':
    st.subheader('Oficjalne kategorie statystyk NBA')
    st.write('Zestawy są pobierane na żądanie z NBA Stats, aby nie wykonywać kilkunastu ciężkich zapytań przy każdym otwarciu strony.')
    st.caption('Źródło: stats.nba.com przez nba_api. Dostępność zależy od oficjalnego serwera NBA i jego limitów.')
    selection=st.selectbox('Wybierz rodzaj statystyk',list(DATASETS.keys()))
    st.markdown(f'<div class="bb-panel"><strong>{safe(selection)}</strong><p>Sezon {safe(season)} · NBA Stats API · pojedyncze pobranie na żądanie</p></div>',unsafe_allow_html=True)
    if st.button('Pobierz wybrane statystyki',type='primary'):
        try:
            with st.spinner('Pobieram dane NBA Stats…'):
                dataset,meta=load_dataset(selection,season,st.session_state.nonce)
                st.session_state['lab_df']=dataset
                st.session_state['lab_meta']=meta
                st.session_state['lab_name']=selection
        except Exception as ex:st.error('Nie udało się pobrać tego zestawu. '+str(ex))
    if st.session_state.get('lab_name')==selection:
        df=st.session_state.get('lab_df',pd.DataFrame())
        if not df.empty:
            st.metric('Wiersze',len(df))
            st.dataframe(df,use_container_width=True,height=550,hide_index=True)
            mini_legend(list(df.columns)[:25],{'GP':'Liczba rozegranych meczów','W':'Wygrane','L':'Przegrane','PTS':'Punkty','REB':'Zbiórki','AST':'Asysty','FG3M':'Celne trójki','FG3A':'Próby za trzy','PACE':'Posiadania na 48 min','DEF_RATING':'Punkty tracone na 100 posiadań','OFF_RATING':'Punkty zdobywane na 100 posiadań'})
            st.download_button('Eksportuj cały zestaw CSV',df.to_csv(index=False).encode('utf-8-sig'),file_name='bestbets_nba_dataset.csv',mime='text/csv')
            pill(st.session_state.get('lab_meta',{}))
    st.divider()
    st.markdown('#### Oficjalny box score po ID meczu NBA')
    gameid=st.text_input('Game ID (10 cyfr)',placeholder='np. 0022600001')
    if st.button('Pobierz box score'):
        if len(gameid)!=10 or not gameid.isdigit():st.error('ID meczu NBA musi składać się z 10 cyfr.')
        else:
            try:
                data,meta=nba_stats('boxscoretraditionalv3','BoxScoreTraditionalV3',{'game_id':gameid},
                        'boxscore-'+gameid,ttl_seconds=3600)
                st.dataframe(data,use_container_width=True)
                pill(meta)
            except Exception as ex:st.error(str(ex))
    row_note('Statystyki z linków NBA.com','Dostępne integracje: players/traditional, players/shooting, catch-shoot, player box scores, transition, defense-dash, teams/traditional, lineups, teams/shooting, opponent-shooting, hustle, defense, catch-shoot oraz transition. Każda kategoria pochodzi z odpowiadającego jej endpointu NBA; niektóre są przybliżonym odpowiednikiem widoku strony.')


elif page == '📱 Telefon i publikacja':
    st.subheader('BestBets na telefonie i w internecie')
    st.caption('Ta wersja jest gotowa do przygotowania publicznego wdrożenia; samo uruchomienie lokalne nie daje jeszcze publicznego adresu.')
    st.markdown('#### Krok 1 — opublikuj kod na GitHub')
    st.write('Utwórz repozytorium `bestbets-nba` i prześlij zawartość osobnej, przygotowanej paczki **BestBets_v6_3_GITHUB.zip**. Nie przesyłaj lokalnego folderu z Windows, w którym znajduje się prywatny klucz API.')
    st.info('Przy ręcznym przesyłaniu w przeglądarce `.gitignore` nie chroni przed omyłkowym wyborem prywatnego pliku. Paczka GitHub nie zawiera klucza ani lokalnych danych; sprawdź ją przed publikacją.')
    st.link_button('Otwórz GitHub','https://github.com/new')
    st.markdown('#### Krok 2 — uruchom BestBets na Streamlit Cloud')
    st.write('Wybierz repozytorium, gałąź `main`, a jako plik startowy `app.py`. W ustawieniach wersji Pythona wybierz **3.12**.')
    st.link_button('Otwórz Streamlit Community Cloud','https://share.streamlit.io/')
    st.markdown('#### Krok 3 — dodaj klucz tylko jako sekret serwera')
    st.write('W Streamlit Cloud → **App settings → Secrets** wpisz wpis z własnym kluczem. **Nie wklejaj klucza do GitHuba ani do publicznego pliku.**')
    st.code('ODDS_API_KEY = "TU_WSTAW_KLUCZ_W_PANELU_CLOUD"', language='toml')
    st.caption('To przykład formatu; prawdziwy klucz pozostaje na serwerze. Lokalny plik `.streamlit/secrets.toml` nie zostaje automatycznie przeniesiony do chmury.')
    st.markdown('#### Krok 4 — ikona BestBets na iPhonie')
    st.write('Po opublikowaniu otwórz publiczny adres w **Safari** → **Udostępnij** → **Dodaj do ekranu początkowego**. Jeśli pojawi się opcja **Otwórz jako aplikację internetową**, włącz ją, a potem wybierz **Dodaj**.')
    st.caption('To skrót do strony internetowej, nie natywna aplikacja z App Store. Ostateczny wygląd ikony zależy od Safari i metadanych wdrożenia.')
    st.markdown('#### Ograniczenia wersji publicznej')
    st.warning('Wszystkie osoby otwierające publiczną stronę będą korzystać ze wspólnego limitu The Odds API. BestBets ma lokalny budżet żądań, ale nie gwarantuje odporności na duży ruch. Na darmowym hostingu lokalna historia kursów może zniknąć przy restarcie; do archiwizacji potrzebna jest trwała baza.')
    st.caption('Prognozy mają charakter eksperymentalny; kursy mogą być niedostępne w Polsce. BestBets nie zawiera automatycznego obstawiania.')

st.markdown('''<div class="bb-footer">BestBets v6.3 · Dane NBA: NBA CDN / stats.nba.com przez nba_api · Kontuzje: ESPN (nieoficjalne) · Kursy: automatycznie przez The Odds API, wymagany klucz; brak potwierdzenia Betclic Polska. 
Nie jest to strona NBA ani Betclic. Model jest eksperymentalny i jego prognozy wymagają walidacji.</div>''',unsafe_allow_html=True)
