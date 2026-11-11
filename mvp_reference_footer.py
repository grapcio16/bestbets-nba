"""Reference-inspired six miniature functional navigation previews.

Each preview opens an existing MVP page or inserts a real player-prop query.
Text shown here is navigation and methodology, not made-up NBA predictions.
"""
from __future__ import annotations
import streamlit as st

FOOTER_TILES=(
    ("home","⌂","Centrum","NBA dashboard","Terminarz, aktualne wyniki i alerty"),
    ("simulations","◈","Symulacje","5 000 przebiegów","Średnie wyniki i analiza meczów"),
    ("games","▣","Terminarz","NBA Games","Daty i godziny w Twojej strefie"),
    ("players","♙","Zawodnicy","Player profiles","Składy, statystyki, historia"),
    ("teams","⬡","Drużyny","30 NBA teams","Forma, zdobyte i tracone punkty"),
)


def render_reference_footer(on_navigate,season):
    """Horizontal interactive cards; vertical two-column wrap on narrow devices."""
    st.markdown(
        '<div class="bb83-footer-heading">EXPLORE BESTBETS · '
        'SZYBKIE PRZEJŚCIA</div>',unsafe_allow_html=True)
    with st.container(key="bb83-footer"):
        cols=st.columns(6,gap="small")
        for i,(route,icon,title,stat,subtitle) in enumerate(FOOTER_TILES):
            with cols[i]:
                with st.container(border=True):
                    st.markdown(
                        f'<div class="bb83-mini-kicker">{icon}  {title}</div>'
                        f'<div class="bb83-mini-title">{stat}</div>'
                        f'<div class="bb83-mini-body">{subtitle}</div>',
                        unsafe_allow_html=True)
                    st.button(
                        "Otwórz ↗",key=f"bb83_footer_{route}",
                        use_container_width=True,
                        on_click=on_navigate,args=(route,))
        with cols[5]:
            with st.container(border=True):
                st.markdown(
                    '<div class="bb83-mini-kicker">⌨  SKRÓTY WPISYWANIA</div>'
                    '<div class="bb83-mini-title">Player Props</div>'
                    '<div class="bb83-mini-body">'
                    '<b>PTS</b> punkty · <b>REB</b> zbiórki · <b>AST</b> asysty'
                    '<br><b>3PM</b> trójki · <b>PRA</b> PTS+REB+AST'
                    '</div>',unsafe_allow_html=True)
                st.button(
                    "Wpisz PRA ↗",key="bb83_footer_shortcut",
                    use_container_width=True,
                    on_click=_open_pra,args=(on_navigate,))


def _open_pra(on_navigate):
    st.session_state["bb_mvp_search_text"]="Jayson Tatum over 35.5 PRA"
    st.session_state["bb_mvp_autosubmit"]=True
    st.session_state.pop("bb_mvp_search_parse",None)
    st.session_state.pop("bb_mvp_search_results",None)
    on_navigate("props")
