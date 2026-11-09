"""BestBets v7.8: honest opponent model audit and independent forecast tracking."""
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
from team_logos import logo_data_uri, refresh_logos_in_background
from simulation_sources import historical_espn_results
from viewer_time import choices, resolve_zone, localize, games_on_day
from dashboard_data import previous_day_ranking
from center_leaderboard import show_top10
from schedule_ui import day_navigation, display_cards, result_type
from schedule_data import fixtures_for_day
from odds_fetcher import automatic_odds
from simulation_view import render_simulations
from odds_engine import normalized_offers, best_prices, player_edges, edge_metrics, legend_for, MARKET_LABELS, LABELS
from market_archive import save_offers, snapshot_summary, historical_two_sided_lines

PATH=Path(__file__).resolve().parent
WARSAW=ZoneInfo('Europe/Warsaw')

def viewer_timezone():
    return resolve_zone(st.session_state.get('viewer_tz_override','Automatyczna'),
                        getattr(st.context,'timezone',None))


def viewer_time_column(values):
    return localize(values, viewer_timezone())


@st.cache_data(ttl=15*60, max_entries=14, show_spinner=False)
def load_daily_ranking_v713(season, local_today, zone_name, nonce):
    # New cache identity: v7.12 users still had cached TOP10 rows without
    # minutes, opponent or position. Rebuild them from current ESPN boxscores.
    completed, note=historical_espn_results(season,refresh=nonce>0)
    top, meta=previous_day_ranking(completed,local_today,ZoneInfo(zone_name))
    return top,meta,note


ARCHIVE_PATH=PATH/'data'/'historyczne_kursy.csv'
SEASON='2026-27'
MARKET_API={'player_points':'PTS','player_rebounds':'REB','player_assists':'AST',
            'player_threes':'FG3M','player_points_rebounds_assists':'PRA'}

st.set_page_config(page_title='BestBets | NBA Intelligence',page_icon=Image.open(PATH/'assets'/'bestbets_brand_icon_64.png'),layout='wide',initial_sidebar_state='auto')
CSS="""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Space+Grotesk:wght@500;600;700;800&display=swap');
:root{--gold:#ff6a00;--ink:#eaf0f7;--muted:#9ba9bc;--panel:#0b1220;--line:#263346;}
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
.bb-title span{color:#ff6a00}.bb-sub{color:#b0bdcf;line-height:1.55;max-width:800px;font-size:14px}
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
.bb-versus small{font-size:11px;color:#96a4b5}.bb-versus b{font-size:23px;color:#ff6a00}
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
CSS += """<style>.bb-hero{background:linear-gradient(110deg,#0b1220,#10264d);border-color:#1b4382}.bb-title span{color:#ff6a00}.bb-logo{width:88px;height:88px;object-fit:contain;border-radius:22px;flex-shrink:0}.bb-gamecard{border-color:#214780}.bb-tag{color:#ff6a00}.stButton button[kind="primary"],.stDownloadButton button{background:linear-gradient(120deg,#ff9040,#ff641c);color:#0b1220;border-color:#ff7e24}div[data-testid="stMetric"]{border-color:#224575}</style>"""
st.markdown(CSS,unsafe_allow_html=True)

@st.cache_data(ttl=3600,max_entries=3,show_spinner=False)
def load_schedule(nonce):return schedule(refresh=nonce>0)

@st.cache_data(ttl=1800,max_entries=3,show_spinner=False)
def load_injuries(nonce):return injuries(refresh=nonce>0)

@st.cache_data(ttl=4*3600,max_entries=5,show_spinner=False)
def load_logs(season,nonce):return game_logs(season,refresh=nonce>0)

@st.cache_data(ttl=4*3600,max_entries=12,show_spinner=False)
def load_dataset(name,season,nonce):return extended_set(name,season,refresh=nonce>0)

@st.cache_data(ttl=3600,max_entries=4,show_spinner=False)
def load_backtest(logs,market,min_games):return rolling_backtest(logs,market,min_games=min_games)

@st.cache_data(ttl=20*60,max_entries=4,show_spinner=False)
def cached_normalize_offers(featured,props):
    return normalized_offers(featured,props)

@st.cache_data(ttl=20*60,max_entries=4,show_spinner=False)
def cached_best_prices(offers):
    return best_prices(offers)

@st.cache_data(ttl=35*60,max_entries=3,show_spinner=False)
def cached_player_edges(prop_best,logs,inj,team_ctx,med):
    return player_edges(prop_best,logs,inj,team_ctx,med)



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
    visible=[c for c in ['Mecz','Początek (lokalny)','Rynek','Zawodnik','Linia','Wariant','Bukmacher','Najwyższy kurs',
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
    """Full NBA schedule. Cards are primary; table and CSV are optional."""
    st.subheader("Terminarz NBA")
    zone = viewer_timezone()
    selected = day_navigation("schedule", zone)
    st.caption("Wybierz dowolną datę. Wszystkie godziny odpowiadają Twojej strefie czasowej.")
    rows, issues = fixtures_for_day(sched, selected, zone, st.session_state.nonce)
    if issues:
        st.warning("Niepełne dane dla wybranej daty: " + "; ".join(issues))
    if rows is None or rows.empty:
        display_cards(rows, zone)
        return

    filter_col, view_col = st.columns([1.1, 1.4])
    with filter_col:
        status_filter = st.selectbox(
            "Status meczu",
            ["Wszystkie", "Zaplanowane", "Na żywo", "Zakończone"],
            key="bb_schedule_status_filter",
        )
    with view_col:
        table_mode = st.toggle("Widok tabeli zamiast kart", key="bb_schedule_table_mode", value=False)
    status_value = {"Zaplanowane":"scheduled", "Na żywo":"live", "Zakończone":"final"}
    if status_filter != "Wszystkie":
        rows = rows[rows.apply(result_type, axis=1) == status_value[status_filter]].copy()

    if table_mode:
        if rows.empty:
            st.info("Brak spotkań o wybranym statusie.")
        else:
            table = rows.copy().sort_values("start_utc")
            table["Termin (lokalny)"] = viewer_time_column(table["start_utc"]).dt.strftime("%d.%m.%Y %H:%M")
            table["Spotkanie"] = table["away"] + " @ " + table["home"]
            table["Status"] = table["status"].astype(str)
            # These are actual feed scores; scheduled games have no score.
            table["Wynik rzeczywisty"] = table.apply(
                lambda g: (
                    f"{int(float(g['away_score']))} : {int(float(g['home_score']))}"
                    if result_type(g) != "scheduled"
                    and pd.notna(g.get("away_score"))
                    and pd.notna(g.get("home_score"))
                    else "—"
                ),
                axis=1,
            )
            st.dataframe(
                table[["Termin (lokalny)", "Spotkanie", "Status", "Wynik rzeczywisty"]],
                hide_index=True, use_container_width=True,
            )
    else:
        display_cards(rows, zone)

    if not rows.empty:
        export = rows.copy()
        export["Termin (lokalny)"] = viewer_time_column(export["start_utc"]).dt.strftime("%d.%m.%Y %H:%M")
        st.download_button(
            "Eksportuj mecze z wybranego dnia (CSV)",
            export.to_csv(index=False).encode("utf-8-sig"),
            file_name=f"bestbets_terminarz_{selected.isoformat()}.csv",
            mime="text/csv",
        )

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
        rows.append({'Mecz (lokalny)':t.tz_convert(viewer_timezone()).strftime('%d.%m %H:%M'),
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
    st.markdown('<div style="font-size:22px;font-family:Space Grotesk;font-weight:800;color:#f5c46b;margin:4px 0 20px">🪙 BestBets <small style="color:#8e9fb2;font-size:11px">NBA / v7.18</small></div>',unsafe_allow_html=True)
    page=st.radio('Nawigacja',[
        '🏠 Centrum', '📆 Terminarz', '🏀 Symulacje 5000', '🧑‍🚀 Zawodnicy', '🏟️ Drużyny',
        '💹 Kursy i value','📈 Performance Tracker','🧪 Backtesting', '📚 NBA Data Lab'],index=0,label_visibility='collapsed')
    st.selectbox('Strefa czasowa', choices(),key='viewer_tz_override',help='Automatyczna korzysta ze strefy przeglądarki. Zmiany DST obsługuje zoneinfo.')
    st.caption('Godziny meczów: '+str(viewer_timezone()))
    season=st.selectbox('Sezon', ['2026-27','2025-26','2024-25'],index=0)
    st.divider()
    if st.button('↻ Odśwież dostępne dane',use_container_width=True):
        st.session_state.nonce+=1
        st.rerun()
    st.caption('Terminarz: ESPN (szybkie źródło) → NBA CDN w razie awarii · NBA Stats: oficjalne dane · kontuzje: ESPN · kursy: The Odds API.')
    st.caption('BestBets to narzędzie do analizy danych, bez gwarancji zysków.')

from base64 import b64encode
brand_icon_base64=b64encode((PATH/'assets'/'bestbets_brand_icon_64.png').read_bytes()).decode('ascii')
st.markdown(f'''<div class="bb-hero">
<img class="bb-logo" src="data:image/png;base64,{brand_icon_base64}" alt="BestBets"/><div>
<div class="bb-kicker">NBA intelligence platform · season 2026–27</div>
<div class="bb-title">Best<span>Bets</span></div>
<div class="bb-sub">Oficjalne statystyki NBA, analiza matchupów, przewidywane minuty, raport kontuzji i porównanie kursów. Wszystko w jednym panelu, z widocznymi ograniczeniami danych.</div>
</div></div>''',unsafe_allow_html=True)

if page == '🏠 Centrum':
    r1,r2=st.columns([1.6,1])
    with r1:
        st.markdown("#### Terminarz dnia")
        zone = viewer_timezone()
        selected = day_navigation("center", zone)
        try:
            sched, meta = load_schedule(st.session_state.nonce)
            chosen, problems = fixtures_for_day(sched, selected, zone, st.session_state.nonce)
            display_cards(chosen, zone, compact=True)
            if problems:
                st.warning("Niepełne dane dla wybranej daty: " + "; ".join(problems))
            if "ESPN" in meta.get("source", ""):
                st.caption("Terminarz: ESPN (zapasowo NBA CDN).")
            pill(meta)
        except Exception as exc:
            st.error("Nie udało się pobrać terminarza: " + str(exc))
    with r2:
        st.markdown('#### Injury report')
        try:
            inj,meta=load_injuries(st.session_state.nonce)
            if inj.empty:st.info('ESPN nie zwrócił rozpoznawalnych rekordów kontuzji. Nie oznacza to, że wszyscy są zdrowi.')
            else:
                st.metric('Wpisy w raporcie ESPN',len(inj))
                refresh_logos_in_background()
                for _,rec in inj.head(10).iterrows():
                    code=str(rec.get('team') or '—')
                    icon=logo_data_uri(code) if code in set(TEAM_MAP.values()) else ''
                    logo=(f'<img src="{icon}" width="28" height="28" style="object-fit:contain" alt="{safe(code)}">' if icon else '<span>🏥</span>')
                    st.markdown(f'<div style="display:flex;align-items:center;gap:9px;padding:6px 2px;border-bottom:1px solid #263346">{logo}<span style="flex:1"><b>{safe(rec["player"])}</b> <small style="color:#95a7bb">{safe(code)}</small></span><small>{safe(rec["status"])}</small></div>',unsafe_allow_html=True)
                st.caption('Kluby pochodzą z ESPN; nierozpoznane przypisania nie są zgadywane.')
                mini_legend([],{'player':'Zawodnik z wpisem w raporcie ESPN','team':'Drużyna gracza','status':'Status według ESPN, nie oficjalna decyzja trenerów'})
            pill(meta)
        except Exception as exc:st.warning('Raport ESPN niedostępny: '+str(exc))
        st.link_button('Oficjalny raport NBA',OFFICIAL_INJURIES,use_container_width=True)
    st.markdown('#### TOP 10 zawodników — poprzedni dzień')
    try:
        today=datetime.now(viewer_timezone()).date()
        top, coverage, note=load_daily_ranking_v713(season,today,str(viewer_timezone()),st.session_state.nonce)
        if top.empty:
            st.info('Brak zweryfikowanych statystyk zawodników za poprzedni lokalny dzień.')
        else:
            st.caption('Rzeczywiste statystyki zakończonych meczów ESPN. U góry: mecz i nominalna pozycja; pod spodem: PTS, REB, AST oraz faktyczne minuty. Brak potwierdzonych danych = —.')
            show_top10(top)
        st.caption(f"Zatwierdzone box score: {coverage['complete_games']}/{coverage['requested_games']} zakończonych spotkań.")
        if coverage['failed_games']:
            st.warning('Ranking może być niepełny: nie pobrano statystyk wszystkich zakończonych spotkań.')
        if note:st.caption(str(note)[:200])
    except Exception as exc:
        st.info('Ranking chwilowo niedostępny: '+str(exc)[:160])
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
    from roster_view import render_player_profile
    render_player_profile(season,st.session_state.nonce)

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
        offers=cached_normalize_offers(feat,props)
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
        best=cached_best_prices(offers)
        if not best.empty:
            b1,b2,b3,b4=st.columns(4)
            labelled_metric(b1,'Bukmacherzy',str(offers['bookmaker_key'].nunique()),'Liczba firm z kursami w odpowiedzi API')
            labelled_metric(b2,'Oferty kursowe',str(len(offers)),'Wszystkie pobrane warianty, także powtórzenia między firmami')
            labelled_metric(b3,'Unikalne porównania',str(len(best)),'Porównanie po meczu, rynku, zawodniku, linii i wariancie')
            labelled_metric(b4,'Rynki graczy',str(len(best[best['market'].isin(STAT_NAMES)])),'Warianty dla graczy; mogą nie być dostępne w każdym regionie')
        selected_view=st.radio('Wybierz analizę kursów',
            ['🏆 Najlepsze dostępne kursy','📊 Model value graczy','🧮 Kalkulator (opcjonalnie)'],
            horizontal=True,key='bb64_odds_view',help='Ładujemy wyłącznie wybraną analizę. Inne widoki nie obciążają serwera.')
        if selected_view=='🏆 Najlepsze dostępne kursy':
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
                        near['Start (lokalny)']=viewer_time_column(near['start_utc']).dt.strftime('%d.%m %H:%M')
                        near['Mecz']=near['away']+' @ '+near['home']
                        st.markdown('**Nadchodzące mecze — terminarz dostępny, kursy jeszcze niedostępne**')
                        st.dataframe(near[['Start (PL)','Mecz']],hide_index=True,use_container_width=True)
                        mini_legend([],{'Start (PL)':'Data rozpoczęcia spotkania w czasie polskim','Mecz':'Goście @ gospodarze; brak kursu nie oznacza braku możliwości obstawienia meczu'})
                except Exception:
                    st.caption('Nie udało się załadować również zastępczego widoku najbliższych meczów.')
        if selected_view=='📊 Model value graczy':
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
                with st.spinner('Oceniam wyniki i kontrolę jakości (wynik jest buforowany)…'):
                    edges=cached_player_edges(prop_best,logs,inj,team_ctx,med)
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
        if selected_view=='🧮 Kalkulator (opcjonalnie)':
            st.markdown('#### Kalkulator zawodników NBA')
            st.caption('Pojedynczy zawodnik lub beta importu wielu linii z obrazu. '
                       'Wyniki bazują na dostępnej historii NBA i nie są skalibrowane.')
            calculator_mode=st.radio(
                'Tryb kalkulatora',
                ['📷 Import screenshot — analiza wielu pozycji',
                 '👤 Kalkulator pojedynczego zawodnika'],
                horizontal=True,key='bb717_calculator_mode')
            if calculator_mode.startswith('📷'):
                from screenshot_ui import render_screenshot_calculator
                render_screenshot_calculator(season,get_logs)
            else:
                from roster_view import (global_player_selector,player_observed_logs,
                                         show_calculator_history_chart)
                player,pid,team,coverage=global_player_selector(st.session_state.nonce)
                if player is not None:
                    a,b,c=st.columns([1,1,1])
                    market=a.selectbox('Statystyka',list(STAT_NAMES),
                        format_func=lambda v:STAT_NAMES[v],key='bb7_calculator_market')
                    side=b.selectbox('Wariant',['OVER','UNDER'],key='bb7_calculator_side')
                    line=c.number_input('Linia',min_value=0.5,value=5.5,step=.5,
                                        key='bb7_calculator_line')
                    odds=st.number_input('Kurs dziesiętny',min_value=1.01,value=1.85,
                                         step=.01,key='bb7_calculator_odds')
                    selection=(season,team,pid,market,float(line),side,float(odds))
                    if st.button('Oblicz i pokaż wykres występów',key='bb7_calculate',
                                 type='primary'):
                        st.session_state['bb7_calc_selection']=selection
                    if st.session_state.get('bb7_calc_selection')==selection:
                        with st.spinner('Ładuję występy wybranego zawodnika…'):
                            try:
                                sub,details=player_observed_logs(
                                    team,pid,player,season,st.session_state.nonce)
                            except (ValueError,KeyError,TypeError,RuntimeError) as exc:
                                st.warning('Nie udało się pobrać statystyk: '+str(exc)[:180])
                                sub=pd.DataFrame()
                                details={}
                        st.caption('Dostępne występy: '+str(len(sub))+' · '+
                                   str(details.get('coverage','')))
                        projection=None
                        if len(sub)>=5:
                            try:
                                p=calc_projection(sub,market)
                                projection=p['prediction']
                                if float(line).is_integer():
                                    st.info('Linia całkowita może oznaczać zwrot stawki. '
                                            'Zmień na linię połówkową do analizy EV.')
                                else:
                                    m=edge_metrics(prop_probability(p,line,side),odds)
                                    k1,k2,k3,k4=st.columns(4)
                                    labelled_metric(k1,'Szansa modelu',
                                        f"{m['p_model_pct']:.2f}%",'Niekalibrowana prognoza')
                                    labelled_metric(k2,'Próg kursu',
                                        f"{m['p_break_even_pct']:.2f}%",'100/kurs')
                                    labelled_metric(k3,'Przewaga',
                                        f"{m['edge_pp']:+.2f} pp",'Niezweryfikowana')
                                    labelled_metric(k4,'EV modelu',
                                        f"{m['ev_pct']:+.2f}%",'Tylko według modelu')
                                    st.warning('To NIE jest skalibrowana szansa '
                                               'ani sprawdzona przewaga nad kursem. '
                                               'Przy małej próbce i nieznanych '
                                               'absencjach nawet wysokie dodatnie '
                                               'EV może być poważnie błędne.')
                                    st.caption(f"Prognoza: {p['prediction']:.1f} · "
                                        f"Minuty: {p['estimated_minutes']:.1f} · "
                                        f"Próba: {p['sample_size']} meczów. "
                                        'Dodatnie EV nie dowodzi rentowności.')
                            except (ValueError,KeyError,TypeError) as exc:
                                st.warning('Nie można wyznaczyć prognozy: '+str(exc)[:180])
                        else:
                            st.warning('Za mało rzeczywistych występów (minimum 5) '
                                       'na obliczenie szansy i EV. Historia poniżej '
                                       'pokazuje tylko dostępne spotkania.')
                        if len(sub)>=10 and not float(line).is_integer():
                        from prediction_engine_v2 import forecast_v2
                        try:
                            candidate=forecast_v2(
                                sub,market,line,pd.Timestamp.now(tz='UTC'),draws=2048)
                            st.markdown('##### Prediction Engine 2.0 — wariant badawczy')
                            r1,r2,r3=st.columns(3)
                            r1.metric('Szansa OVER v2',f"{100*candidate['p_over']:.1f}%")
                            r2.metric('Prognoza v2',f"{candidate['mean']:.1f}")
                            r3.metric('Przewidywane minuty v2',f"{candidate['minutes']:.1f}")
                            st.caption('Losowania: 2048 · 80% przedział symulowany: '+
                                       f"{candidate['p10']:.0f}–{candidate['p90']:.0f} · "
                                       'Próba: '+str(candidate['sample'])+' meczów.')
                            st.warning('Wariant 2.0 NIE jest skalibrowany. '
                                       'Nie wykorzystuj różnic procentowych jako dowodu przewagi '
                                       'ani rekomendacji. Wymaga walk-forward i późniejszych danych.')
                            if candidate['warnings']:
                                st.caption(' • '.join(candidate['warnings']))
                        except (ValueError,KeyError,TypeError) as exc:
                            st.caption('Prediction Engine 2.0 niedostępny: '+str(exc)[:140])
                    show_calculator_history_chart(sub,player,market,line,projection)
                        if sub is not None and not sub.empty:
                            st.dataframe(sub[['GAME_DATE','MATCHUP','MIN','PTS','REB',
                                              'AST','FG3M','PRA']].tail(20)
                                         .sort_values('GAME_DATE',ascending=False),
                                         hide_index=True,use_container_width=True)

    automatic_market_panel()

elif page == '📈 Performance Tracker':
    from performance_tracker import (performance_metrics,audit_summary)
    from tracker_storage import (read as tracker_read, settle as tracker_settle, tracker_backend)
    from simulation_sources import historical_espn_results
    cfg=tracker_backend()
    st.subheader('BestBets Performance Tracker')
    st.caption('Magazyn danych: '+cfg['label'])
    st.caption('Zamrożone prognozy powstają TYLKO przy otwarciu zakładki '
               '„Symulacje 5000” przed rozpoczęciem meczu; nigdy po fakcie. '
               'Wyniki końcowe są dopasowywane do identyfikatora ESPN.')
    if not cfg['remote']:
        st.warning('SQLite jest lokalny i nietrwały na Streamlit Cloud. '
                   'Dla trwałego archiwum skonfiguruj TRACKER_DATABASE_URL '
                   'w sekcji Secrets jako adres własnego PostgreSQL. '
                   'Bez tego po restarcie dane mogą zniknąć.')
    else:
        st.caption('Zewnętrzny PostgreSQL skonfigurowany. '
                   'Nie publikujemy hasła ani adresu połączenia.')
    st.caption('Zapis prognoz następuje podczas odwiedzania symulacji. '
               'Nie jest to jeszcze samodzielne monitorowanie 24/7.')
    with st.expander('Test historyczny: nowy model kontra stare średnie',expanded=False):
        st.caption('Walk-forward: każdy mecz prognozowany wyłącznie na podstawie '
                   'spotkań zakończonych wcześniej. Porównanie nie obejmuje '
                   'prawdziwego modelu tempa i kontuzji. Metryki nie oznaczają przewagi bukmacherskiej.')
        if st.button('Porównaj modele na wcześniejszych meczach',
                     key='tracker_walkforward'):
            try:
                from simulation_backtest import walk_forward_comparison
                with st.spinner('Porównuję na rzeczywiście zakończonych meczach…'):
                    finished,notes=historical_espn_results(season)
                    compared,score=walk_forward_comparison(finished,max_games=140)
                    from model_validation import evaluate_models
                    heldout,holdout_score=evaluate_models(finished,holdout_n=40,include_venue=True)
                if holdout_score:
                    st.session_state['tracker_new_holdout_score']=holdout_score
                    st.session_state['tracker_new_holdout_rows']=heldout
                if not score:
                    st.warning('Za mało wcześniejszych meczów dla obu modeli.')
                else:
                    st.session_state['tracker_walkforward_score']=score
                    st.session_state['tracker_walkforward_rows']=compared
            except Exception as exc:
                st.error('Test nie został wykonany: '+str(exc)[:200])
        score=st.session_state.get('tracker_walkforward_score')
        if score:
            st.caption('Mecze z kompletnym porównaniem: '+str(score['games']))
            st.dataframe(pd.DataFrame([
                {'Model':'Stare średnie','MAE sumy':score['old_total_mae'],
                 'MAE drużyn':score['old_team_mae'],
                 'Trafność zwycięzcy':score['old_winner_accuracy'],
                 'Brier':score['old_brier']},
                {'Model':'Forma + siła rywali','MAE sumy':score['new_total_mae'],
                 'MAE drużyn':score['new_team_mae'],
                 'Trafność zwycięzcy':score['new_winner_accuracy'],
                 'Brier':score['new_brier']},
            ]),hide_index=True,use_container_width=True)
            if score['new_total_mae']>=score['old_total_mae']:
                st.warning('Nowa metoda NIE zmniejszyła błędu sum w tej próbce. '
                           'Nie można twierdzić, że jest lepsza.')
            else:
                st.caption('Nowa metoda zmniejszyła MAE sumy w tej próbce; '
                           'wymaga kolejnych niezależnych testów.')
            st.markdown('#### Osobny test: atak / obrona kontra stary model')
            heldout_summary=st.session_state.get('tracker_new_holdout_score')
            if heldout_summary:
                st.caption('Chronologicznie ostatnie 40 spotkań — wyłącznie '
                           'dane sprzed rozpoczęcia każdego meczu. Nowy model '
                           'ataku/obrony jest BADAWCZY i nie zmienia '
                           'domyślnych prognoz BestBets.')
                st.dataframe(pd.DataFrame([
                    {'Model':code,'Mecze':value['games'],
                     'MAE sumy':value['total_mae'],
                     'MAE drużyn':value['team_mae'],
                     'Trafność zwycięzców':value['winner_accuracy'],
                     'Brier':value['brier']}
                    for code,value in heldout_summary.items()
                ]),hide_index=True,use_container_width=True)
                st.caption('Uwaga: wariant venue_research jest tylko hipotezą dom/wyjazd. Zwróć uwagę na N (Mecze) każdego modelu; mniejszej liczby obserwacji nie wolno porównywać jak identycznej próby. Na kilkudziesięciu meczach niewielkie różnice '
                           'nie potwierdzają przewagi modelu. Nie są to '
                           'statystyki rentowności zakładów.')
            if 'tracker_walkforward_rows' in st.session_state:
                st.download_button('Eksport wyniku porównania CSV',
                    st.session_state['tracker_walkforward_rows'].to_csv(
                        index=False).encode('utf-8-sig'),
                    file_name='bestbets_model_comparison.csv',mime='text/csv')
    if st.button('Pobierz i rozlicz zakończone mecze',type='primary',
                 key='tracker_settle'):
        with st.spinner('Sprawdzam potwierdzone wyniki ESPN…'):
            try:
                finished,notes=historical_espn_results(season,refresh=True)
                n=tracker_settle(finished,config=cfg)
                st.success('Rozliczono nowych spotkań: '+str(n))
                if notes:st.caption(str(notes))
            except Exception as exc:
                st.error('Nie udało się rozliczyć prognoz. Sprawdź połączenie z bazą i odpowiedź ESPN.')
    try:
        full_archive=tracker_read(season,config=cfg)
        available_models=(sorted(full_archive['model_id'].dropna().astype(str).unique())
                          if not full_archive.empty and 'model_id' in full_archive
                          else [])
        if len(available_models)>1:
            chosen_model=st.selectbox('Wariant modelu do rozliczenia',
                available_models,key='bb76_tracker_model')
            st.caption('Każdy wariant oceniamy osobno. Różne modele mogą mieć '
                       'inne próbki meczów, więc ich wyniki nie są bezpośrednim '
                       'porównaniem head-to-head.')
            frozen=full_archive[full_archive['model_id']==chosen_model].copy()
        else:
            frozen=full_archive
            if available_models:
                st.caption('Wariant modelu: '+available_models[0])
        verified,stats=performance_metrics(frozen)
        qa=audit_summary(frozen)
        m1,m2,m3,m4=st.columns(4)
        m1.metric('Zamrożone mecze',len(frozen))
        m2.metric('Rozliczone mecze',stats['games'])
        m3.metric('Trafność zwycięzców',
                  f"{stats['winner_accuracy']*100:.1f}%"
                  if stats['winner_accuracy'] is not None else '—')
        m4.metric('Śr. błąd sumy',
                  f"{stats['total_mae']:.1f} pkt"
                  if stats['total_mae'] is not None else '—')
        if stats['games']:
            a,b,c=st.columns(3)
            a.metric('Błąd punktów na drużynę',f"{stats['team_mae']:.1f}")
            b.metric('Bias sumy punktów',f"{stats['total_bias']:+.1f} pkt")
            c.metric('Brier score',f"{stats['brier']:.3f}")
            st.caption('Niższy Brier score jest lepszy, ale bez odpowiednio '
                       'dużej próby nie można stwierdzić kalibracji. '
                       'Bias dodatni = model zaniża sumy, ujemny = zawyża.')
        if frozen.empty:
            st.info('Na tym serwerze nie zapisano jeszcze prognoz. '
                    'Otwórz „Symulacje 5000” przed kolejnym meczem.')
        else:
            st.caption('Kontrola jakości: '+str(qa['suspicious_win_probs'])+
                       ' prognoz z faworytem powyżej 85%. '
                       'To tylko flaga do audytu.')
            visible=frozen.copy()
            visible['Start lokalny']=viewer_time_column(visible['start_utc']).dt.strftime('%d.%m.%Y %H:%M')
            visible['Spotkanie']=visible['away']+' @ '+visible['home']
            visible['Stan']=visible['home_score'].notna().map(
                {True:'Rozliczony',False:'Oczekuje'})
            display_cols=['Start lokalny','Spotkanie','away_points','home_points',
                          'away_win_pct','home_win_pct','away_score','home_score',
                          'Stan','model_id','source']
            st.dataframe(visible[display_cols],hide_index=True,
                         use_container_width=True)
            st.download_button('Pobierz pełne archiwum prognoz (CSV)',
                full_archive.to_csv(index=False).encode('utf-8-sig'),
                file_name='bestbets_pregame_archive.csv',mime='text/csv')
            if not verified.empty:
                st.markdown('#### Błędy zakończonych spotkań')
                st.dataframe(verified[['game_id','forecast_total',
                    'actual_total','total_error','winner_hit','brier']],
                    hide_index=True,use_container_width=True)
        st.caption('Brak historycznych prognoz sprzed uruchomienia Trackera '
                   '— nie odtwarzamy ich z późniejszych wyników.')
    except Exception as exc:
        st.error('Nie udało się odczytać Performance Trackera. Sprawdź konfigurację bazy danych.')

elif page == '🧪 Backtesting':
    st.subheader('Backtesting i kalibracja — bez przecieku danych z przyszłości')
    row_note('Dlaczego to ważne','W każdej prognozie używamy wyłącznie wcześniejszych występów. Automatyczne archiwum zbiera PRAWDZIWE ceny przed meczem. Zaczyna się ono teraz, nie odtwarza cudownie brakujących starych kursów. Test z liniami symulowanymi nie jest testem rentowności.')
    with st.expander('🧠 Prediction Engine 2.0 — Model Battle (test badawczy)',expanded=False):
        st.caption('Porównujemy obecny model z wariantem 2.0 na identycznych '
                   'późniejszych meczach zawodników. Linia Over/Under pochodzi '
                   'WYŁĄCZNIE ze wcześniejszej historii (średnia ostatnich 10, '
                   'zaokrąglona do x,5), a NIE od bukmachera. '
                   'Wynik NIE dowodzi dodatniego ROI.')
        c1,c2=st.columns(2)
        battle_market=c1.selectbox('Statystyka do porównania',list(STAT_NAMES),
            format_func=lambda k:STAT_NAMES[k],key='bb718_market')
        seasons=c2.multiselect('Sezony testowe',options=['2026-27','2025-26','2024-25'],
            default=[season],key='bb718_seasons',
            help='Starsze sezony są pobierane tylko na żądanie. '
                 'Jeżeli NBA Stats nie odpowiada, nie wypełniamy luk fikcyjnymi danymi.')
        max_cases=st.slider('Maksymalna liczba testowanych występów',60,600,240,
            step=60,key='bb718_cases')
        if st.button('Uruchom niezależne porównanie modeli',
                     key='bb718_run',type='primary'):
            if not seasons:
                st.warning('Wybierz przynajmniej jeden sezon.')
            else:
                from player_model_battle import chronological_battle
                frames=[]
                provenance=[]
                with st.spinner('Ładuję historyczne występy i wykonuję walk-forward…'):
                    for season_part in seasons:
                        try:
                            raw,details=load_logs(season_part,st.session_state.nonce)
                            normalized=normalize_logs(raw)
                            frames.append(normalized)
                            source=(details or {}).get('source','NBA') if isinstance(details,dict) else 'NBA'
                            coverage=(details or {}).get('coverage','') if isinstance(details,dict) else ''
                            provenance.append(f"{season_part}: {len(normalized)} występów; {source} {coverage}")
                            if isinstance(details,dict) and details.get('stale'):
                                st.warning(f'{season_part}: źródło wskazuje niepełne lub przestarzałe dane.')
                        except (ValueError,KeyError,TypeError,RuntimeError) as ex:
                            st.warning(f'{season_part}: historia jest niedostępna — '+str(ex)[:170])
                    if frames:
                        df=pd.concat(frames,ignore_index=True)
                        compared,report=chronological_battle(
                            df,battle_market,max_cases=max_cases,min_games=10)
                        st.session_state['bb718_battle']=(compared,report,
                            (tuple(seasons),battle_market,max_cases),provenance)
                    else:
                        st.session_state.pop('bb718_battle',None)
        cached=st.session_state.get('bb718_battle')
        if cached:
            compared,report,config,provenance=cached
            if config!=(tuple(seasons),battle_market,max_cases):
                st.info('Zmieniono parametry — uruchom porównanie ponownie.')
            elif compared.empty:
                st.warning('Brak wystarczającej liczby prawdziwych meczów z '
                           'wcześniejszą historią zawodników. Nie oceniamy skuteczności.')
                for desc in provenance:st.caption(desc)
            else:
                for desc in provenance:st.caption(desc)
                st.markdown('##### Porównanie na tej samej próbie')
                for stage,label in [('all','Wszystkie dostępne testy'),
                                    ('later_30pct','Ostatnie 30% w czasie')]:
                    metrics=report.get(stage,{})
                    st.markdown('**'+label+' · '+str(metrics.get('n',0))+' obserwacji**')
                    if metrics.get('legacy') and metrics.get('v2'):
                        values=[]
                        for code,model_name in [('legacy','Dotychczasowy'),
                                                ('v2','Prediction Engine 2.0')]:
                            m=metrics[code]
                            values.append({'Model':model_name,
                                'MAE prognozy':m['mae'],
                                'Brier (mniej lepiej)':m['brier'],
                                'Log loss':m['logloss'],
                                'Trafność Over/Under':f"{100*m['over_under_accuracy']:.1f}%",
                                'Bias punktowy':m['bias']})
                        st.dataframe(pd.DataFrame(values),hide_index=True,
                                     use_container_width=True)
                st.caption(f"Zawodnicy: {report['n_players']} · "
                           f"Sezony: {report['n_seasons']} · próg: "
                           f"{report['line_source']}. "
                           'Każdy występ rozliczamy tylko wobec meczów sprzed jego daty.')
                st.warning('Test wyłącznie na SYNTETYCZNYCH liniach, '
                           'bez historycznych kursów bukmacherów. '
                           'Próby graczy z jednego meczu są skorelowane, '
                           'a ostatnie 30% nie jest nowym niezależnym sezonem. '
                           'Nie uruchamiamy automatycznie żadnych zmian produkcyjnych.')
                st.download_button('Pobierz porównanie modelu CSV',
                    compared.to_csv(index=False).encode('utf-8-sig'),
                    file_name='bestbets_model_battle_v718.csv',
                    mime='text/csv',key='bb718_export')
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


st.markdown('''<div class="bb-footer">BestBets v7.18 · Dane NBA: NBA CDN / stats.nba.com przez nba_api · Kontuzje: ESPN (nieoficjalne) · Kursy: automatycznie przez The Odds API, wymagany klucz; brak potwierdzenia Betclic Polska. 
Nie jest to strona NBA ani Betclic. Model jest eksperymentalny i jego prognozy wymagają walidacji.</div>''',unsafe_allow_html=True)
