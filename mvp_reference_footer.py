"""BestBets v8.5 — screenshot-matched premium navigation previews.

Six permanent, functional lower modules. The preview art contains only
navigation/methodology; no fabricated odds, score, hit-rate or predictions.
"""
from __future__ import annotations

from html import escape

import streamlit as st

from team_logos import logo_data_uri

FOOTER_TILES=(
    ("home","⌂","Centrum","NBA dashboard","Zobacz analizę dnia"),
    ("simulations","◈","Symulacje","5 000 symulacji","Model Monte Carlo"),
    ("games","▣","Terminarz","Mecze NBA","Godziny w Twojej strefie"),
    ("players","♙","Zawodnicy","Player profiles","Statystyki i forma"),
    ("teams","⬡","Drużyny","30 NBA Teams","Forma i bilanse"),
)


def _club_logo(code):
    try:
        uri=logo_data_uri(code)
    except (ValueError,KeyError,TypeError,RuntimeError):
        uri=None
    return (
        f'<img src="{escape(uri,quote=True)}" alt="{escape(code)}">'
        if uri else '<span class="bb85-ball">●</span>'
    )


def _preview(route):
    if route=="home":
        return (
            '<div class="bb85-brandline"><span>🏀</span><strong>BEST<span>BETS</span></strong></div>'
            '<div class="bb85-tiny-kpis">'
            '<div><small>NBA</small><b>30</b></div>'
            '<div class="green"><small>PROPS</small><b>PTS</b></div>'
            '<div><small>RYNKI</small><b>5</b></div>'
            '</div>'
            '<div class="bb85-callout"><span class="bb85-avatar">🏀</span>'
            '<span><b>Centrum analiz NBA</b><small>Wyniki · zawodnicy · trendy</small></span>'
            '<span class="bb85-pill">GO</span></div>'
        )
    if route=="simulations":
        return (
            '<div class="bb85-preview-title">Symulacje (5 000)</div>'
            '<div class="bb85-sim-versus">'
            f'{_club_logo("BOS")}'
            '<div><small>MONTE CARLO</small><strong>VS</strong><small>MODEL NBA</small></div>'
            f'{_club_logo("PHI")}</div>'
            '<div class="bb85-sim-track"><i></i><i></i></div>'
            '<div class="bb85-preview-bottom"><span>5000 przebiegów</span>'
            '<strong>Analiza meczów</strong></div>'
        )
    if route=="games":
        return (
            '<div class="bb85-preview-title">NBA · Terminarz</div>'
            '<div class="bb85-search-mini">‹ &nbsp; Mecze i wyniki &nbsp; ›</div>'
            '<div class="bb85-compact-row"><strong>01</strong><span>Najbliższe mecze</span><em>›</em></div>'
            '<div class="bb85-compact-row"><strong>02</strong><span>Wyniki na żywo</span><em>›</em></div>'
            '<div class="bb85-compact-row"><strong>03</strong><span>Zakończone</span><em>›</em></div>'
        )
    if route=="players":
        return (
            '<div class="bb85-search-mini">⌕ &nbsp; Szukaj zawodnika…</div>'
            '<div class="bb85-person-row"><span>🏀</span><b>Jayson Tatum</b><small>PTS / REB</small></div>'
            '<div class="bb85-person-row"><span>🏀</span><b>Luka Dončić</b><small>AST / 3PM</small></div>'
            '<div class="bb85-person-row"><span>🏀</span><b>Nikola Jokić</b><small>PRA</small></div>'
        )
    if route=="teams":
        items=(("BOS","Boston Celtics"),("NYK","New York Knicks"),("PHI","Philadelphia 76ers"))
        rows=''.join(
            f'<div class="bb85-team-row">{_club_logo(short)}<b>{escape(full)}</b><small>{short}</small></div>'
            for short,full in items
        )
        return '<div class="bb85-search-mini">⌕ &nbsp; Szukaj drużyny…</div>'+rows
    return ""


def render_reference_footer(on_navigate,season):
    """Reference preview rail + six independent clickable page controls."""
    st.markdown(
        '<div class="bb83-footer-heading">EXPLORE BESTBETS · SZYBKIE PRZEJŚCIA</div>',
        unsafe_allow_html=True,
    )
    with st.container(key="bb83-footer"):
        cols=st.columns(6,gap="small")
        for i,(route,icon,title,stat,subtitle) in enumerate(FOOTER_TILES):
            with cols[i]:
                with st.container(border=True):
                    st.markdown(
                        '<div class="bb85-preview">'
                        '<div class="bb85-preview-head">'
                        f'<span>{escape(icon)} {escape(title)}</span>'
                        '</div>'
                        f'{_preview(route)}'
                        '</div>',
                        unsafe_allow_html=True,
                    )
        with cols[5]:
            with st.container(border=True):
                rows=(
                    ("PTS","punkty","25.5 pts"),
                    ("REB","zbiórki","8.5 reb"),
                    ("AST","asysty","5.5 ast"),
                    ("3PM","celne trójki","2.5 3pm"),
                    ("PRA","punkty + zbiórki + asysty","35.5 pra"),
                )
                table=''.join(
                    '<div class="bb85-shortcut-row">'
                    f'<strong>{escape(abbrev)}</strong>'
                    f'<span>{escape(desc)}</span>'
                    f'<small>{escape(example)}</small></div>'
                    for abbrev,desc,example in rows
                )
                st.markdown(
                    '<div class="bb85-preview bb85-shortcut-panel">'
                    '<div class="bb85-preview-head"><span>⌨ Skrót wpisywania (Player Props)</span></div>'
                    +table+'</div>',
                    unsafe_allow_html=True,
                )

        # These are the real navigation controls (not illustrative screenshots).
        # Their dedicated row matches the navigation bar below six image tiles.
        links=st.columns(6,gap="small")
        for i,(route,icon,title,_,_) in enumerate(FOOTER_TILES):
            with links[i]:
                st.button(
                    f"{icon}  {title}",key=f"bb83_footer_{route}",
                    use_container_width=True,
                    on_click=on_navigate,args=(route,),
                )
        with links[5]:
            st.button(
                "⌨  Player Props",key="bb83_footer_shortcut",
                use_container_width=True,
                on_click=_open_pra,args=(on_navigate,),
            )


def _open_pra(on_navigate):
    st.session_state["bb_mvp_search_text"]="Jayson Tatum over 35.5 PRA"
    st.session_state["bb_mvp_autosubmit"]=True
    st.session_state.pop("bb_mvp_search_parse",None)
    st.session_state.pop("bb_mvp_search_results",None)
    on_navigate("props")
