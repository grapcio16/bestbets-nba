"""BestBets MVP v8.0 — focused navigation and shared premium UI.

MAIN: Home, Player Props (Calculator), Games, Simulations, Players, Teams.
WORKSPACE: Favorites, Trends, Tools, Settings.
No OCR screen, odds comparison, tracking dashboard, backtest or Data Lab here;
their computation and historical files remain in repository for later release.
"""
from __future__ import annotations

from base64 import b64encode
from html import escape
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from mvp_theme import apply_mvp_theme
from mvp_reference_theme import apply_reference_theme
from mvp_reference_footer import render_reference_footer
from mvp_data import confirmed_finals, team_games, team_summary, league_table, safe_value
from teams import TEAM_FULL
from team_logos import logo_data_uri, refresh_logos_in_background
from viewer_time import choices,resolve_zone
from schedule_ui import day_navigation,display_cards,result_type
from schedule_data import fixtures_for_day
from core import STAT_NAMES
from simulation_sources import historical_espn_results

ROOT=Path(__file__).resolve().parent

MAIN_PAGES=(
    ("home","⌂  Home"),
    ("props","▥  Player Props"),
    ("games","▣  Games"),
    ("simulations","◈  Simulations"),
    ("players","♙  Players"),
    ("teams","⬡  Teams"),
)
EXTRA_PAGES=(
    ("favorites","☆  Favorites"),
    ("trends","▥  Trends"),
    ("tools","⚒  Tools"),
    ("settings","⚙  Settings"),
)
ALL_PAGES={k:v for k,v in (*MAIN_PAGES,*EXTRA_PAGES)}
PAGE_HEADINGS={
    "home":("Home","Dzisiejsze mecze i najważniejsze informacje NBA"),
    "props":("Player Props","Wyszukiwarka rynków i rzeczywiste statystyki zawodników"),
    "games":("Games","Terminarz, wyniki i szczegóły spotkań"),
    "simulations":("Simulations 5000","Eksperymentalne symulacje rzeczywistych meczów NBA"),
    "players":("Players","Aktualne składy i historia występów"),
    "teams":("Teams","Forma, atak i obrona poszczególnych drużyn"),
    "favorites":("Favorites","Zapisani zawodnicy i drużyny w tej sesji"),
    "trends":("Trends","Obserwowane trendy z zakończonych spotkań"),
    "tools":("Tools","Proste narzędzia do oceny kursów i ryzyka"),
    "settings":("Settings","Strefa czasowa, sezon i odświeżanie danych"),
}


def set_page(page):
    if page in ALL_PAGES:
        st.session_state["bb_mvp_page"]=page


def _season():
    return st.session_state.get("bb_mvp_season","2026-27")


def _zone():
    try:
        return resolve_zone(
            st.session_state.get("bb_mvp_zone","Automatyczna"),
            getattr(st.context,"timezone",None))
    except Exception:
        from zoneinfo import ZoneInfo
        return ZoneInfo("Europe/Warsaw")


@st.cache_data(ttl=15*60,max_entries=3,show_spinner=False)
def get_schedule(nonce):
    from sources import schedule
    return schedule(refresh=nonce>0)


@st.cache_data(ttl=25*60,max_entries=3,show_spinner=False)
def get_injuries(nonce):
    from sources import injuries
    return injuries(refresh=nonce>0)


@st.cache_data(ttl=3*3600,max_entries=5,show_spinner=False)
def get_logs(season,nonce):
    from sources import game_logs
    return game_logs(season,refresh=nonce>0)


@st.cache_data(ttl=4*3600,max_entries=5,show_spinner=False)
def get_dataset(name,season,nonce):
    from sources import extended_set
    return extended_set(name,season,refresh=nonce>0)


@st.cache_data(ttl=45*60,max_entries=6,show_spinner=False)
def get_history(season,nonce):
    return historical_espn_results(season,refresh=nonce>0)


def _actuals(season,nonce):
    try:
        results,warnings=get_history(season,nonce)
    except Exception as exc:
        return pd.DataFrame(),["Historia ESPN niedostępna: "+str(exc)[:120]]
    verified=confirmed_finals(results,pd.Timestamp.now(tz="UTC"))
    messages=[]
    if warnings:messages.append("Nie wszystkie wyniki ESPN są obecnie dostępne.")
    if verified.empty:messages.append("Brak potwierdzonych finałów sezonu.")
    return verified,messages


def _logo_img(code,size=52):
    src=logo_data_uri(code)
    if src:
        return f'<img src="{escape(src,quote=True)}" width="{size}" height="{size}" alt="{escape(code)}" style="object-fit:contain">'
    return '<span style="font-size:28px">🏀</span>'


def _sidebar():
    """Reference-style six primary links plus discreet workspace/settings."""
    with st.sidebar:
        icon=ROOT/"assets"/"bestbets_brand_icon_64.png"
        brand=(f'<img src="data:image/png;base64,{b64encode(icon.read_bytes()).decode()}" alt="BestBets">'
               if icon.exists() else '<span style="font-size:31px">🏀</span>')
        st.markdown(
            '<div class="bbm-brand">'+brand+
            '<div><b>BEST<span>BETS</span></b>'
            '<div class="bbm-eyebrow" style="font-size:8px;letter-spacing:.08em">'
            'NBA INTELLIGENCE</div></div></div>',unsafe_allow_html=True)
        current=st.session_state["bb_mvp_page"]
        main_labels={
            "home":"⌂  Centrum",
            "props":"▥  Player Props (Kalkulator)",
            "games":"▣  Terminarz",
            "simulations":"◈  Symulacje",
            "players":"♙  Zawodnicy",
            "teams":"⬡  Drużyny",
        }
        for page,_ in MAIN_PAGES:
            st.button(
                main_labels.get(page,page),key="bb_nav_"+page,
                use_container_width=True,
                type="primary" if current==page else "secondary",
                on_click=set_page,args=(page,))
        st.markdown('<div style="height:14px;border-bottom:1px solid #2b4569;margin:3px 12px 13px"></div>',
                    unsafe_allow_html=True)
        st.button(
            "⚙  Ustawienia",key="bb_nav_settings",
            use_container_width=True,
            type="primary" if current=="settings" else "secondary",
            on_click=set_page,args=("settings",))
        with st.expander("Więcej · Favorites / Trends / Tools",
                         expanded=False):
            for page,label in EXTRA_PAGES:
                if page=="settings":continue
                st.button(
                    label,key="bb_nav_"+page,use_container_width=True,
                    type="primary" if current==page else "secondary",
                    on_click=set_page,args=(page,))
        st.markdown(
            '<div class="bbm-sidebar-footer">'
            'Sezon '+escape(_season())+' · NBA / ESPN<br>'
            'Modele eksperymentalne · wyniki niegwarantowane'
            '</div>',unsafe_allow_html=True)


def _topbar(page):
    # Search bar is the topmost element on the approved Player Props layout.
    # Do not add a second header or search field above it.
    if page=="props":
        return
    title,description=PAGE_HEADINGS[page]
    st.markdown(
        '<div class="bbm-topbar">'
        '<div><div class="bbm-eyebrow">BESTBETS / NBA INTELLIGENCE</div>'
        f'<h1>{escape(title)}</h1>'
        f'<p>{escape(description)}</p></div>'
        '<span class="bbm-mini-tag">SEASON '+escape(_season())+
        '</span></div>',
        unsafe_allow_html=True)
    # Player Props already has a full-size search hero — avoid two search bars.
    if page=="props":
        return
    left,right=st.columns([5,1],vertical_alignment="bottom")
    with left:
        query=st.text_input(
            "Globalne wyszukiwanie typów",
            placeholder="🔎  Search players & props · np. Jayson Tatum over 25.5 points",
            label_visibility="collapsed",key="bbm_global_query")
    with right:
        if st.button("Search",key="bbm_global_go",
                     type="primary",use_container_width=True):
            if not query.strip():
                st.info("Wpisz pełne zdarzenie z zawodnikiem, linią i rynkiem.")
            else:
                st.session_state["bb_mvp_search_text"]=query
                st.session_state.pop("bb_mvp_search_parse",None)
                st.session_state.pop("bb_mvp_search_results",None)
                set_page("props")
                st.rerun()


def _notes(messages):
    if messages:
        with st.expander("Dostępność danych",expanded=False):
            for message in messages:st.caption(str(message))


def _quick_actions():
    a,b,c=st.columns(3)
    with a:
        st.button("▥  Player Props",key="bbm_home_props",
                  use_container_width=True,type="primary",
                  on_click=set_page,args=("props",))
    with b:
        st.button("▣  Today's games",key="bbm_home_games",
                  use_container_width=True,on_click=set_page,args=("games",))
    with c:
        st.button("◈  5000 simulations",key="bbm_home_sims",
                  use_container_width=True,on_click=set_page,args=("simulations",))


def home_page():
    st.markdown(
        '<div class="bbm-intro"><div class="bbm-kicker">COURTSIDE · NBA DASHBOARD</div>'
        '<strong>Tonight’s basketball, one clear view.</strong>'
        '<p>Rzeczywisty terminarz, najważniejsze absencje i szybka nawigacja. '
        'Nie generujemy „pewnych typów dnia” bez zweryfikowanego modelu.</p></div>',
        unsafe_allow_html=True)
    _quick_actions()
    tz=_zone()
    selected=day_navigation("center",tz)
    messages=[]
    try:
        schedule,meta=get_schedule(st.session_state["bb_mvp_nonce"])
        chosen,issues=fixtures_for_day(
            schedule,selected,tz,st.session_state["bb_mvp_nonce"])
        messages.extend(issues)
    except Exception as exc:
        schedule=pd.DataFrame();chosen=pd.DataFrame()
        messages.append("Terminarz niedostępny: "+str(exc)[:130])
    total=len(chosen)
    upcoming=0;completed=0
    if total:
        states=chosen.apply(result_type,axis=1)
        upcoming=int((states=="scheduled").sum())
        completed=int((states=="final").sum())
    a,b,c=st.columns(3)
    a.metric("Games",total)
    b.metric("Upcoming",upcoming)
    c.metric("Finished",completed)
    l,r=st.columns([1.9,1.05],gap="large")
    with l:
        st.markdown('<div class="bbm-section"><h3>NBA games</h3>'
                    f'<small>{selected.strftime("%d.%m.%Y")}</small></div>',
                    unsafe_allow_html=True)
        display_cards(chosen,tz,compact=True)
    with r:
        st.markdown('<div class="bbm-section"><h3>Injury alerts</h3>'
                    '<small>ESPN · nieoficjalne</small></div>',
                    unsafe_allow_html=True)
        try:
            inj,metadata=get_injuries(st.session_state["bb_mvp_nonce"])
            if inj is None or inj.empty:
                st.info("Brak potwierdzonych wpisów w aktualnej odpowiedzi ESPN.")
            else:
                for _,row in inj.head(7).iterrows():
                    person=escape(str(row.get("player") or ""))
                    team=escape(str(row.get("team") or "—"))
                    status=escape(str(row.get("status") or "—"))
                    st.markdown(
                        '<div class="bbm-card">'
                        f'<strong>{person}</strong>'
                        f'<div class="bbm-compact">{team} · {status}</div>'
                        '</div>',unsafe_allow_html=True)
            if isinstance(metadata,dict) and metadata.get("stale"):
                messages.append("Raport kontuzji może być nieaktualny.")
        except Exception as exc:
            st.info("Raport kontuzji jest chwilowo niedostępny.")
    _notes(messages)


def games_page():
    tz=_zone()
    st.markdown(
        '<div class="bbm-intro"><div class="bbm-kicker">NBA / SCHEDULE</div>'
        '<strong>Every game. Every result.</strong>'
        '<p>Wszystkie godziny w wybranej strefie czasowej. '
        'Nie mylimy wyników rzeczywistych z symulowanymi.</p></div>',
        unsafe_allow_html=True)
    day=day_navigation("games",tz)
    try:
        schedule,metadata=get_schedule(st.session_state["bb_mvp_nonce"])
        games,issues=fixtures_for_day(
            schedule,day,tz,st.session_state["bb_mvp_nonce"])
        if not games.empty:
            selected=st.segmented_control(
                "Status",["Wszystkie","Zaplanowane","Na żywo","Zakończone"],
                default="Wszystkie",key="bbm_game_status")
            status_map={"Zaplanowane":"scheduled","Na żywo":"live",
                        "Zakończone":"final"}
            if selected!="Wszystkie":
                games=games[games.apply(result_type,axis=1)==status_map[selected]]
        st.markdown('<div class="bbm-section"><h3>Matchups</h3>'
                    '<small>Wyniki z terminarza NBA/ESPN</small></div>',
                    unsafe_allow_html=True)
        display_cards(games,tz)
        _notes(issues+(
            ["Terminarz z nieaktualnej odpowiedzi."]
            if isinstance(metadata,dict) and metadata.get("stale") else []))
        st.button("◈  Open simulations",key="bbm_from_games_sims",
                  type="primary",on_click=set_page,args=("simulations",))
    except Exception as exc:
        st.error("Nie udało się pobrać meczów: "+str(exc)[:160])


def simulations_page():
    from simulation_view import render_simulations
    st.markdown(
        '<div class="bbm-intro"><div class="bbm-kicker">5,000 MONTE CARLO RUNS</div>'
        '<strong>Game projections, not guarantees.</strong>'
        '<p>Średnie wyniki, prawdopodobieństwa zwycięstwa i szczegóły '
        'wybranego meczu. Model jest badawczy i wymaga kalibracji.</p></div>',
        unsafe_allow_html=True)
    @st.fragment(run_every="30m")
    def _content():
        render_simulations(
            _season(),st.session_state["bb_mvp_nonce"],
            get_schedule,get_dataset,get_logs,get_injuries)
    _content()


def players_page():
    from roster_view import roster_selector,player_observed_logs
    from mvp_player_card import render_player_card
    tz=_zone()
    st.markdown(
        '<div class="bbm-intro"><div class="bbm-kicker">NBA ROSTERS</div>'
        '<strong>Pick a player. Explore real form.</strong>'
        '<p>Składy z ESPN. Histogram zawodnika jest tworzony '
        'dopiero po pobraniu jego rzeczywistych występów.</p></div>',
        unsafe_allow_html=True)
    nonce=st.session_state["bb_mvp_nonce"]
    name,pid,team,roster,meta=roster_selector(
        "bbm_player_team","bbm_player_name",nonce)
    if not name:return
    left,right=st.columns([3,1])
    with left:
        st.caption(f"{TEAM_FULL.get(team,team)} · "+str(len(roster))+
                   " zawodników w dostępnym składzie")
    with right:
        favorite=any(f.get("name")==name for f in
                     st.session_state.get("bb_mvp_favorite_players",[]))
        if st.button("★ Saved" if favorite else "☆ Favorite",
                     key="bbm_fav_player_page"):
            entries=[f for f in st.session_state["bb_mvp_favorite_players"]
                     if f.get("name")!=name]
            if not favorite:entries.append({"name":name,"team":team})
            st.session_state["bb_mvp_favorite_players"]=entries
            st.rerun()
    if meta.get("stale"):
        st.warning("Skład pochodzi z kopii, która może być nieaktualna.")
    if not roster.empty:
        with st.expander("Roster · pełny skład",expanded=False):
            selected_cols=[k for k in
                           ("PLAYER_NAME","POSITION","ROSTER_STATUS")
                           if k in roster]
            st.dataframe(roster[selected_cols],
                         use_container_width=True,hide_index=True)
    first,second=st.columns([1.3,1])
    with first:
        market=st.selectbox(
            "Statystyka",list(STAT_NAMES),
            format_func=lambda x:STAT_NAMES[x],
            key="bbm_player_market")
    with second:
        line=st.number_input(
            "Linia do badania (nie kurs bukmachera)",
            min_value=.5,max_value=150.,value=20.5,step=.5,
            key="bbm_player_line")
    ident=(name,pid,team,_season(),market,line)
    if st.button("📊  Show player analysis",type="primary",
                 key="bbm_player_load"):
        st.session_state["bbm_player_loaded"]=ident
    if st.session_state.get("bbm_player_loaded")!=ident:
        st.info("Kliknij „Show player analysis”, aby pobrać występy "
                "wybranego zawodnika. Wyniki nie są fabrykowane.")
        return
    try:
        with st.spinner("Pobieram zakończone mecze zawodnika…"):
            history,metadata=player_observed_logs(
                team,pid,name,_season(),nonce)
    except Exception as exc:
        st.error("Historia niedostępna: "+str(exc)[:140]);return
    if history.empty:
        st.warning("Brak rzeczywistych rozegranych spotkań tego zawodnika.")
        return
    with st.expander("Kompletność danych",expanded=False):
        st.caption(str(metadata.get("source","ESPN")))
        st.caption(str(metadata.get("coverage","")))
        st.caption(str(metadata.get("warning","")))
    row=pd.Series({
        "Zawodnik":name,"Rynek":market,"Linia":line,
        "Drużyna":team,"Pozycja":(
            roster.loc[roster["PLAYER_NAME"]==name,"POSITION"].iloc[0]
            if "POSITION" in roster else "—"),
        "Przeciwnik":None,"_espn_id":pid,"Wybór":"OVER",
        "Źródło statystyk":metadata.get("source","ESPN"),
        "Uwagi":metadata.get("warning",""),
    })
    render_player_card(
        row,history,_season(),pd.Timestamp.now(tz="UTC"),
        slug="bbm_player_profile")


def teams_page():
    st.markdown(
        '<div class="bbm-intro"><div class="bbm-kicker">NBA / TEAM INTELLIGENCE</div>'
        '<strong>Form, scoring & defensive context.</strong>'
        '<p>Dane obliczane z rzeczywistych finałów bieżącego sezonu, '
        'nie z przewidywanych wyników.</p></div>',unsafe_allow_html=True)
    codes=sorted(TEAM_FULL,key=lambda c:TEAM_FULL[c])
    team=st.selectbox("Wybierz drużynę",codes,
                      format_func=lambda c:TEAM_FULL[c],
                      key="bbm_selected_team")
    if st.button(
        "★ Saved" if team in st.session_state["bb_mvp_favorite_teams"]
        else "☆ Add to Favorites",key="bbm_fav_team"):
        selected=set(st.session_state["bb_mvp_favorite_teams"])
        if team in selected:selected.remove(team)
        else:selected.add(team)
        st.session_state["bb_mvp_favorite_teams"]=sorted(selected)
        st.rerun()
    logo=_logo_img(team,74)
    st.markdown(
        '<div class="bbm-team-head">'+logo+
        '<div><div class="bbm-eyebrow">NBA TEAM PROFILE</div>'
        f'<h2>{escape(TEAM_FULL[team])}</h2>'
        f'<small>{escape(team)} · Sezon {escape(_season())}</small></div></div>',
        unsafe_allow_html=True)
    finals,issues=_actuals(_season(),st.session_state["bb_mvp_nonce"])
    summary=team_summary(finals,team)
    metrics=st.columns(4)
    metrics[0].metric("W / L",f'{summary["wins"]} / {summary["losses"]}')
    metrics[1].metric("Points / game",safe_value(summary["scored"],1))
    metrics[2].metric("Allowed / game",safe_value(summary["allowed"],1))
    metrics[3].metric("Net margin",safe_value(summary["margin"],1))
    if not summary["gp"]:
        st.warning("Brak potwierdzonych finałów tego zespołu. "
                   "Nie pokazujemy wyników zastępczych.")
        _notes(issues);return
    st.markdown('<div class="bbm-section"><h3>Recent performance</h3>'
                f'<small>{summary["gp"]} zakończonych meczów</small></div>',
                unsafe_allow_html=True)
    data=team_games(finals,team).tail(12)
    chart=go.Figure()
    chart.add_trace(go.Bar(
        x=[d.strftime("%d/%m") for d in data["start_utc"]],
        y=data["margin"].tolist(),
        marker_color=["#21d996" if v>0 else "#fb626a" for v in data["margin"]],
        text=[f"{m:+.0f}" for m in data["margin"]],
        textposition="outside",
        hovertext=data["opponent"].tolist(),
        hovertemplate="vs %{hovertext}<br>Różnica: %{y:+.0f}<extra></extra>"))
    chart.add_hline(y=0,line_color="#83a9d4",line_dash="dash")
    chart.update_layout(
        height=320,showlegend=False,margin=dict(l=14,r=14,t=30,b=20),
        paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(showgrid=False),yaxis=dict(gridcolor="rgba(149,187,225,.12)"),
        font=dict(color="#cfe0f4"))
    st.plotly_chart(chart,use_container_width=True)
    a,b,c=st.columns(3)
    a.metric("Win rate · L5",safe_value(summary["last5"],0,"%"))
    b.metric("Win rate · L10",safe_value(summary["last10"],0,"%"))
    c.metric("Win rate · season",safe_value(summary["win_pct"],0,"%"))
    st.markdown('<div class="bbm-section"><h3>Recent boxscores</h3>'
                '<small>zweryfikowane finały</small></div>',
                unsafe_allow_html=True)
    with st.expander("Szczegóły ostatnich 12 spotkań",expanded=False):
        st.dataframe(
            data[["start_utc","opponent","scored","allowed",
                  "margin","venue"]].iloc[::-1],
            hide_index=True,use_container_width=True)
    _notes(issues)


def favorites_page():
    st.markdown('<div class="bbm-intro"><div class="bbm-kicker">SAVED WATCHLIST</div>'
                '<strong>Your courtside shortlist.</strong>'
                '<p>Ulubione pozycje pozostają w bieżącej sesji przeglądarki. '
                'Nie obiecujemy synchronizacji między urządzeniami.</p></div>',
                unsafe_allow_html=True)
    teams=st.session_state["bb_mvp_favorite_teams"]
    people=st.session_state["bb_mvp_favorite_players"]
    a,b=st.columns(2)
    a.metric("Favorite teams",len(teams))
    b.metric("Favorite players",len(people))
    st.markdown("### Teams")
    if not teams:st.info("W Teams wybierz drużynę i kliknij ☆ Add to Favorites.")
    for code in teams:
        col1,col2,col3=st.columns([3,1,1],vertical_alignment="center")
        col1.markdown(
            '<div class="bbm-card">'+_logo_img(code,37)+
            '<strong style="margin-left:12px">'+escape(TEAM_FULL.get(code,code))+
            '</strong></div>',unsafe_allow_html=True)
        if col2.button("View",key=f"bbm_open_team_{code}",
                       use_container_width=True):
            st.session_state["bbm_selected_team"]=code
            set_page("teams");st.rerun()
        if col3.button("Remove",key=f"bbm_rm_team_{code}",
                       use_container_width=True):
            st.session_state["bb_mvp_favorite_teams"]=[
                t for t in teams if t!=code]
            st.rerun()
    st.markdown("### Players")
    if not people:st.info("Zapisz zawodnika w Player Props lub Players.")
    for player in people:
        name=str(player.get("name") or "")
        team=str(player.get("team") or "")
        col1,col2,col3=st.columns([3,1,1],vertical_alignment="center")
        col1.markdown(
            '<div class="bbm-card"><strong>'+escape(name)+
            '</strong><div class="bbm-compact">'+escape(team)+
            '</div></div>',unsafe_allow_html=True)
        if col2.button("View",key="bbm_open_person_"+name,
                       use_container_width=True):
            if team in TEAM_FULL:
                st.session_state["bbm_player_team"]=team
            set_page("players")
            st.rerun()
        if col3.button("Remove",key="bbm_rm_person_"+name,
                       use_container_width=True):
            st.session_state["bb_mvp_favorite_players"]=[
                p for p in people if p.get("name")!=name]
            st.rerun()


def trends_page():
    st.markdown('<div class="bbm-intro"><div class="bbm-kicker">DATA-BACKED TRENDS</div>'
                '<strong>Actual form. No invented edges.</strong>'
                '<p>Ranking drużyn oparty wyłącznie na zakończonych meczach '
                'w bieżącym sezonie. To analiza opisowa, nie typ bukmacherski.</p></div>',
                unsafe_allow_html=True)
    finals,issues=_actuals(_season(),st.session_state["bb_mvp_nonce"])
    minimum=st.slider("Minimum zakończonych meczów",3,15,5,key="bbm_trend_min")
    table=league_table(finals,minimum_games=minimum)
    if table.empty:
        st.info("Nie mamy wystarczającej liczby potwierdzonych spotkań.")
        _notes(issues);return
    st.markdown('<div class="bbm-section"><h3>Hot teams · last 5</h3>'
                '<small>Win rate ostatnich pięciu występów</small></div>',
                unsafe_allow_html=True)
    leaders=table.head(6)
    for group in range(0,len(leaders),3):
        columns=st.columns(3)
        for i in range(group,min(group+3,len(leaders))):
            row=leaders.iloc[i]
            with columns[i-group]:
                st.markdown(
                    '<div class="bbm-card">'+_logo_img(row["code"],47)+
                    '<strong style="margin-left:10px">'+escape(str(row["name"]))+'</strong>'+
                    f'<div style="font-size:26px;color:#21dc97;font-weight:850">'
                    f'{row["last5"]:.0f}%</div>'
                    f'<div class="bbm-compact">{int(row["gp"])} meczów · '
                    f'średnia różnica {row["margin"]:+.1f} pkt</div></div>',
                    unsafe_allow_html=True)
    st.markdown("#### Form ranking")
    with st.expander("Pełny ranking drużyn",expanded=False):
        display=table[["name","gp","wins","losses","last5",
                       "last10","scored","allowed","margin"]].rename(
            columns={"name":"Team","gp":"GP","wins":"W","losses":"L",
                     "last5":"W% L5","last10":"W% L10","scored":"PTS",
                     "allowed":"OPP PTS","margin":"Net pts"})
        st.dataframe(display,hide_index=True,use_container_width=True)
    _notes(issues)


def tools_page():
    st.markdown('<div class="bbm-intro"><div class="bbm-kicker">ANALYSIS UTILITIES</div>'
                '<strong>Know your break-even point.</strong>'
                '<p>Prosta matematyka kursów. Nie zastępuje rzetelnej '
                'prognozy ani nie sugeruje gotowych kuponów.</p></div>',
                unsafe_allow_html=True)
    a,b=st.columns([1,1])
    with a:
        odds=st.number_input(
            "Kurs dziesiętny",min_value=1.01,max_value=100.,
            value=1.80,step=.05,key="bbm_tool_odds")
        st.metric("Próg opłacalności",f"{100/odds:.2f}%")
        st.caption("Minimalne rzeczywiste prawdopodobieństwo, "
                   "przy którym wartość oczekiwana wynosi zero.")
    with b:
        p=st.slider(
            "Twoja niezależna ocena prawdopodobieństwa (%)",
            1,99,50,key="bbm_tool_prob")
        ev=((p/100)*odds-1)*100
        st.metric("Wartość oczekiwana przy tej ocenie",
                  f"{ev:+.1f}%")
        st.caption("Wynik zależy od wpisanej oceny, "
                   "nie jest prognozą modelu BestBets.")
    st.markdown(
        '<div class="bbm-note">Wskaźnik EV może być dodatni nawet dla '
        'bardzo złej prognozy prawdopodobieństwa. '
        'BestBets nie potwierdził jeszcze kalibracji rynków Player Props.</div>',
        unsafe_allow_html=True)


def settings_page():
    st.markdown('<div class="bbm-intro"><div class="bbm-kicker">PERSONAL SETTINGS</div>'
                '<strong>Your season. Your timezone.</strong>'
                '<p>Opcje wpływają na terminarz i analizę, '
                'bez zmiany lub nadpisywania zapisanych prognoz.</p></div>',
                unsafe_allow_html=True)
    season_options=["2026-27","2025-26","2024-25"]
    current=st.session_state["bb_mvp_season"]
    st.selectbox(
        "Sezon NBA",season_options,
        index=season_options.index(current) if current in season_options else 0,
        key="bb_mvp_season")
    tz_choices=choices()
    current_zone=st.session_state["bb_mvp_zone"]
    st.selectbox(
        "Strefa czasowa",tz_choices,
        index=tz_choices.index(current_zone) if current_zone in tz_choices else 0,
        key="bb_mvp_zone")
    st.caption("Godziny spotkań: "+str(_zone()))
    if st.button("↻  Refresh verified data",type="primary",
                 key="bbm_refresh"):
        st.session_state["bb_mvp_nonce"]+=1
        st.rerun()
    with st.expander("Źródła i ograniczenia",expanded=False):
        st.markdown(
            "Terminarz i wyniki: ESPN / NBA. Składy i występy: ESPN / NBA. "
            "Symulacje: model eksperymentalny oparty na dostępnych wynikach. "
            "Jeśli dane są niekompletne, aplikacja ich nie uzupełnia fikcyjnymi "
            "wartościami. Ulubione są zapisywane wyłącznie w sesji.")



def main():
    if "bb_mvp_page" not in st.session_state:
        st.session_state["bb_mvp_page"]="home"
    if "bb_mvp_season" not in st.session_state:
        st.session_state["bb_mvp_season"]="2026-27"
    if "bb_mvp_zone" not in st.session_state:
        st.session_state["bb_mvp_zone"]="Automatyczna"
    if "bb_mvp_nonce" not in st.session_state:
        st.session_state["bb_mvp_nonce"]=0
    if "bb_mvp_favorite_teams" not in st.session_state:
        st.session_state["bb_mvp_favorite_teams"]=[]
    if "bb_mvp_favorite_players" not in st.session_state:
        st.session_state["bb_mvp_favorite_players"]=[]
    apply_mvp_theme()
    apply_reference_theme()
    _sidebar()
    page=st.session_state["bb_mvp_page"]
    _topbar(page)
    if page=="home":home_page()
    elif page=="games":games_page()
    elif page=="simulations":simulations_page()
    elif page=="props":
        from mvp_prop_ui import render_player_props
        def _logs():
            from core import normalize_logs
            raw,meta=get_logs(_season(),st.session_state["bb_mvp_nonce"])
            return normalize_logs(raw),meta
        render_player_props(
            _season(),st.session_state["bb_mvp_nonce"],str(_zone()),
            get_schedule,_logs)
    elif page=="players":players_page()
    elif page=="teams":teams_page()
    elif page=="favorites":favorites_page()
    elif page=="trends":trends_page()
    elif page=="tools":tools_page()
    elif page=="settings":settings_page()
    if page in ("props","home"):
        render_reference_footer(set_page,_season())
    else:
        st.markdown(
            '<div class="bbm-compact" style="margin:20px 0 8px;'
            'border-top:1px solid #203350;padding-top:8px">'
            'BESTBETS · NBA INTELLIGENCE · Real NBA data · '
            'Experimental forecasts.</div>',
            unsafe_allow_html=True)
