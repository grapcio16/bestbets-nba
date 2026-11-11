"""BestBets v9 — reference-first landing, with the existing NBA data intact.

Only visual routing is reset. All historical data sources, statistical models,
real player-prop calculations and simulations remain in this repository.
"""
from __future__ import annotations

from base64 import b64encode
from html import escape
from pathlib import Path

import streamlit as st

from core import normalize_logs
from mvp_app import get_logs, get_schedule
from mvp_prop_ui import render_player_props
from mvp_reference_theme import apply_reference_theme
from bestbets_v90_theme import apply_v90_theme
from bestbets_v91_fx import apply_reference_fx

ROOT=Path(__file__).resolve().parent
SEASON="2026-27"

PAGES=(
    ("home","⌂","Centrum"),
    ("props","▥","Player Props (Kalkulator)"),
    ("games","▣","Terminarz"),
    ("simulations","◈","Symulacje"),
    ("players","♧","Zawodnicy"),
    ("teams","⬡","Drużyny"),
    ("settings","⚙","Ustawienia"),
    ("shortcuts","⌨","Skrót wpisywania"),
)
PAGE_NAMES={key:label for key,_,label in PAGES}
FOOTER_PAGES=("home","simulations","games","players","teams","shortcuts")


def _route(page):
    if page in PAGE_NAMES:
        st.session_state["bb90_page"]=page


def _brand():
    icon=ROOT/"assets"/"bestbets_brand_icon_64.png"
    if icon.is_file():
        encoded=b64encode(icon.read_bytes()).decode("ascii")
        mark=f'<img src="data:image/png;base64,{encoded}" alt="">'
    else:
        mark='<span class="bb90-ball">🏀</span>'
    return (
        '<div class="bbm-brand bb90-brand">'+mark
        +'<div><b>BEST<span>BETS</span></b>'
        '<small>NBA INTELLIGENCE</small></div></div>'
    )


def _sidebar():
    with st.sidebar:
        st.markdown(_brand(),unsafe_allow_html=True)
        current=st.session_state["bb90_page"]
        for key,icon,label in PAGES:
            if key in ("settings","shortcuts"):
                continue
            with st.container(key="bb90-nav-"+key):
                st.button(
                    f"{icon}  {label}",key="bb90_sidebar_"+key,
                    use_container_width=True,
                    type="primary" if current==key else "secondary",
                    on_click=_route,args=(key,),
                )
        st.markdown('<div class="bb90-sidebar-divider"></div>',unsafe_allow_html=True)
        with st.container(key="bb90-nav-settings"):
            st.button(
                "⚙  Ustawienia",key="bb90_sidebar_settings",
                use_container_width=True,
                type="primary" if current=="settings" else "secondary",
                on_click=_route,args=("settings",),
            )
        st.markdown('<div class="bb90-sidebar-flare"></div>',unsafe_allow_html=True)


def _footer_preview(page):
    if page=="home":
        return (
            '<div class="bb90-mini-brand">🏀 <b>BEST<span>BETS</span></b></div>'
            '<div class="bb90-mini-kpis">'
            '<div><small>Mecze dziś</small><strong>—</strong></div>'
            '<div><small>Najlepszy typ</small><strong class="green">—</strong></div>'
            '<div><small>Value</small><strong class="green">—</strong></div>'
            '<div><small>Kontuzje</small><strong class="red">—</strong></div>'
            '</div>'
            '<div class="bb90-mini-person">🏀 <span>Centrum NBA<small>W przygotowaniu</small></span></div>'
        )
    if page=="simulations":
        return (
            '<div class="bb90-mini-heading">Symulacje (5 000)</div>'
            '<div class="bb90-mini-match">'
            '<span class="bb90-orb">◉</span>'
            '<span><small>PROGNOZY</small><b>VS</b><small>NBA</small></span>'
            '<span class="bb90-orb right">◉</span>'
            '</div>'
            '<div class="bb90-mini-bar"><span></span></div>'
            '<div class="bb90-mini-caption">Model Monte Carlo · W przygotowaniu</div>'
        )
    if page=="games":
        return (
            '<div class="bb90-mini-heading">Terminarz</div>'
            '<div class="bb90-mini-search">‹　 Wybierz datę　 ›</div>'
            '<div class="bb90-mini-list"><b>▣</b> Mecze NBA <em>›</em></div>'
            '<div class="bb90-mini-list"><b>◷</b> Godziny lokalne <em>›</em></div>'
            '<div class="bb90-mini-list"><b>◈</b> Wyniki <em>›</em></div>'
        )
    if page=="players":
        return (
            '<div class="bb90-mini-heading">Zawodnicy</div>'
            '<div class="bb90-mini-search">⌕　 Szukaj zawodnika…</div>'
            '<div class="bb90-mini-list"><b>♙</b> Player Profiles <em>›</em></div>'
            '<div class="bb90-mini-list"><b>▥</b> Punkty i zbiórki <em>›</em></div>'
            '<div class="bb90-mini-list"><b>◈</b> Historia meczów <em>›</em></div>'
        )
    if page=="teams":
        return (
            '<div class="bb90-mini-heading">Drużyny</div>'
            '<div class="bb90-mini-search">⌕　 Szukaj drużyny…</div>'
            '<div class="bb90-mini-list"><b>◉</b> Boston Celtics <em>BOS</em></div>'
            '<div class="bb90-mini-list"><b>◉</b> New York Knicks <em>NYK</em></div>'
            '<div class="bb90-mini-list"><b>◉</b> Philadelphia 76ers <em>PHI</em></div>'
        )
    return (
        '<div class="bb90-mini-heading">⌨ Skrót wpisywania (Player Props)</div>'
        '<div class="bb90-mini-short"><b>PTS</b><span>punkty</span><small>over 25.5 pts</small></div>'
        '<div class="bb90-mini-short"><b>REB</b><span>zbiórki</span><small>over 8.5 reb</small></div>'
        '<div class="bb90-mini-short"><b>AST</b><span>asysty</span><small>under 5.5 ast</small></div>'
        '<div class="bb90-mini-short"><b>3PM</b><span>trójki celne</span><small>over 2.5 3pm</small></div>'
        '<div class="bb90-mini-short"><b>PRA</b><span>punkty+zbiórki+asysty</span><small>over 35.5 pra</small></div>'
    )


def _footer():
    # Six independent, real navigation controls are deliberately permanent.
    with st.container(key="bb90-footer"):
        cols=st.columns(6,gap="small")
        for i,key in enumerate(FOOTER_PAGES):
            with cols[i]:
                with st.container(border=True):
                    st.markdown(
                        '<div class="bb90-mini-card bb90-mini-'+escape(key)+'">'
                        +_footer_preview(key)+'</div>',
                        unsafe_allow_html=True,
                    )
        links=st.columns(6,gap="small")
        for i,key in enumerate(FOOTER_PAGES):
            with links[i]:
                icon={"home":"⌂","simulations":"◈","games":"▣",
                      "players":"♧","teams":"⬡","shortcuts":"⌨"}[key]
                label=PAGE_NAMES[key]
                if key=="shortcuts":
                    label="Skrót wpisywania"
                st.button(
                    f"{icon}  {label}",key="bb90_footer_"+key,
                    use_container_width=True,
                    on_click=_route,args=(key,),
                )


def _empty_canvas():
    # Reference layout when no athlete has been selected: structure is shown,
    # but every unknown statistic is blank, not a fabricated Jayson Tatum demo.
    st.markdown(
        '<div class="bb90-empty-hero">'
        '<div class="bb90-empty-avatar">⌕</div>'
        '<div class="bb90-empty-name">'
        '<div class="bb90-empty-label">PLAYER PROPS · NBA INTELLIGENCE</div>'
        '<strong>Wyszukaj zawodnika</strong>'
        '<span>Wpisz nazwisko, OVER / UNDER, linię i rynek w wyszukiwarce powyżej.</span>'
        '</div>'
        '<div class="bb90-empty-metric"><small>AVG</small><b>—</b></div>'
        '<div class="bb90-empty-metric"><small>LINE</small><b>—</b></div>'
        '<div class="bb90-empty-metric"><small>HIT RATE</small><b>—</b></div>'
        '<div class="bb90-empty-grade"><small>MATCHUP GRADE</small><b>—</b></div>'
        '</div>'
        '<div class="bb90-empty-grid">'
        '<section class="bb90-empty-chart">'
        '<h3><span>▥</span> Historia zawodnika</h3>'
        '<div class="bb90-empty-chart-center">Wyszukaj zawodnika, aby zobaczyć prawdziwe wyniki meczów</div>'
        '<div class="bb90-empty-axis"></div>'
        '</section><section class="bb90-empty-insights">'
        '<div class="bb90-empty-hits">'
        '<div>L5<small>—</small></div><div>L10<small>—</small></div>'
        '<div>L15<small>—</small></div><div>Season<small>—</small></div>'
        '</div>'
        '<div class="bb90-empty-averages">'
        '<div>Season AVG <b>—</b></div><div>Home <b>—</b></div>'
        '<div>Away <b>—</b></div></div>'
        '<div class="bb90-empty-defense">⬡　Matchup Defense<br><small>Wyniki po wyszukaniu</small></div>'
        '</section></div>'
        '<div class="bb90-empty-take">'
        '<strong>◎ BestBets Take</strong>'
        '<span>Analiza pojawi się po wybraniu zawodnika i rynku.</span>'
        '</div>',
        unsafe_allow_html=True,
    )


def _blank_page():
    name=PAGE_NAMES.get(st.session_state["bb90_page"],"")
    st.markdown(
        '<div class="bb90-blank-page">'
        '<div class="bb90-blank-mark">◈</div>'
        f'<h2>{escape(name)}</h2>'
        '<p>Ta zakładka zostanie zbudowana w kolejnym etapie.</p>'
        '</div>',
        unsafe_allow_html=True,
    )


def _player_props():
    from mvp_prop_ui import render_player_props
    from mvp_app import get_logs, get_schedule

    def load_logs():
        raw,metadata=get_logs(SEASON,st.session_state["bb90_nonce"])
        return normalize_logs(raw),metadata

    render_player_props(
        SEASON,st.session_state["bb90_nonce"],"Europe/Warsaw",
        get_schedule,load_logs,show_empty=False,
    )
    saved=st.session_state.get("bb_mvp_search_results")
    if not isinstance(saved,dict) or saved.get("table") is None:
        _empty_canvas()


def main():
    if "bb91_bootstrapped" not in st.session_state:
        # One-time visual redesign reset: no inherited Tatum example
        # on the new public landing, never reset on normal reruns.
        for key in tuple(st.session_state):
            if key.startswith("bb_mvp_search_") or key.startswith("bb_mvp_prop_"):
                st.session_state.pop(key, None)
        st.session_state["bb90_page"]="props"
        st.session_state["bb91_bootstrapped"]=True
    if "bb90_page" not in st.session_state:
        st.session_state["bb90_page"]="props"
    if "bb90_nonce" not in st.session_state:
        st.session_state["bb90_nonce"]=0
    if "bb90_bootstrapped" not in st.session_state:
        # A deployment update should open to a clean search, not a cached
        # athlete selected under the obsolete v8 layout.
        for key in list(st.session_state):
            if key.startswith("bb_mvp_search_") or key.startswith("bb_mvp_prop_"):
                st.session_state.pop(key,None)
        st.session_state["bb90_bootstrapped"]=True
    apply_reference_theme()
    apply_v90_theme()
    apply_reference_fx()
    st.markdown(
        '<div class="bb91-header-icons" aria-hidden="true">'
        '<span title="Powiadomienia">♢<i></i></span>'
        '<span title="Profil">♙</span>'
        '</div>',unsafe_allow_html=True)
    _sidebar()
    if st.session_state["bb90_page"]=="props":
        _player_props()
    else:
        _blank_page()
    _footer()
