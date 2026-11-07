"""BestBets v7 roster-first player browser.

Fast page load: one cached ESPN roster request for the selected team. Player
boxscores are fetched ONLY after pressing the statistics button or running the
calculator. Missing logs never make a player disappear from the selector.
"""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from core import STAT_NAMES, calc_projection, norm_name, normalize_logs
from roster_data import team_roster, team_recent_logs
from teams import TEAM_FULL


@st.cache_data(ttl=12*3600, max_entries=35, show_spinner=False)
def cached_team_roster(team: str, nonce: int = 0):
    return team_roster(team, refresh=nonce>0)


@st.cache_data(ttl=3*3600, max_entries=12, show_spinner=False)
def cached_team_logs(team: str, season: str, nonce: int = 0):
    return team_recent_logs(team,season,games_per_team=10)


def roster_selector(team_key: str, player_key: str, nonce: int = 0):
    """Choose from all 30 teams and their current roster, NOT observed logs."""
    teams = sorted(TEAM_FULL, key=lambda c: TEAM_FULL[c])
    col = st.columns([1,2])
    team = col[0].selectbox(
        "Drużyna NBA", teams, index=teams.index("GSW"),
        format_func=lambda c: TEAM_FULL[c], key=team_key
    )
    try:
        roster, meta = cached_team_roster(team,nonce)
    except Exception as exc:
        col[1].warning("Nie udało się pobrać składu "+team+": "+str(exc)[:140])
        return None,None,team,pd.DataFrame(),{}
    names = roster["PLAYER_NAME"].tolist()
    if not names:
        col[1].warning("ESPN nie zwróciło zawodników dla "+team)
        return None,None,team,roster,meta
    player = col[1].selectbox("Zawodnik", names, key=player_key)
    picked = roster[roster["PLAYER_NAME"]==player].iloc[0]
    return player,str(picked["PLAYER_ID"]),team,roster,meta


def player_observed_logs(team: str, player_id: str, name: str, season: str, nonce: int = 0):
    """Find the selected athlete by stable ESPN ID, with normalized-name fallback."""
    raw,meta = cached_team_logs(team,season,nonce)
    if raw is None or raw.empty:
        return pd.DataFrame(),meta
    logs = normalize_logs(raw)
    selection = pd.DataFrame()
    if "PLAYER_ID" in logs.columns and str(player_id):
        selection = logs[logs["PLAYER_ID"].astype(str)==str(player_id)].copy()
    if selection.empty:
        selection = logs[logs["PLAYER_NAME"].map(norm_name)==norm_name(name)].copy()
    selection = selection[selection["TEAM_ABBREVIATION"]==team]
    return selection.sort_values("GAME_DATE"),meta


def render_player_profile(season: str, nonce: int):
    st.subheader("Zawodnicy NBA — katalog składów v7.0")
    st.caption("Wybierz dowolną z 30 drużyn. Katalog pokazuje zawodników z aktualnego składu ESPN "
               "nawet bez rozegranych meczów. Historia ładuje się dopiero na żądanie.")
    player, pid, team, roster, meta = roster_selector(
        "bb7_player_team","bb7_player_name",nonce
    )
    if player is None:
        return
    st.metric("Zawodnicy w składzie drużyny",len(roster))
    if meta.get("stale"):
        st.warning("Skład pochodzi ze starszej kopii ESPN; aktualność transferów wymaga sprawdzenia.")
    st.caption("Źródło katalogu: "+str(meta.get("source","ESPN"))+
               ". Status na liście nie jest oficjalnym raportem kontuzji.")
    with st.expander("Pełny skład wybranej drużyny",expanded=False):
        display = roster[["PLAYER_NAME","POSITION","ROSTER_STATUS"]].rename(
            columns={"PLAYER_NAME":"Zawodnik","POSITION":"Pozycja",
                     "ROSTER_STATUS":"Status w katalogu ESPN"}
        )
        st.dataframe(display,hide_index=True,use_container_width=True)
    market = st.selectbox("Statystyka",list(STAT_NAMES),
                          format_func=lambda v:STAT_NAMES[v],key="bb7_player_market")
    current_selection = (team,pid,market,season)
    if st.button("Pokaż historię i analizę zawodnika",type="primary",
                 key="bb7_load_player"):
        st.session_state["bb7_player_loaded"] = current_selection
    if st.session_state.get("bb7_player_loaded") != current_selection:
        st.info("Zawodnik jest dostępny w katalogu. Kliknij przycisk, aby wczytać jego "
                "rzeczywiste występy. Brak rozegranych meczów nie usuwa go z listy.")
        return
    with st.spinner("Pobieram tylko spotkania wybranej drużyny…"):
        try:
            sub,logmeta = player_observed_logs(team,pid,player,season,nonce)
        except Exception as exc:
            st.warning("Historia występów chwilowo niedostępna: "+str(exc)[:170])
            return
    st.caption("Próba: "+str(len(sub))+" występów · "+str(logmeta.get("coverage",""))+
               ". Nie jest to automatycznie pełny sezon.")
    if sub.empty:
        st.info("W aktualnej próbce nie ma statystyk tego zawodnika. "
                "Pozostaje widoczny w katalogu, bez wymyślonej prognozy.")
        return
    st.dataframe(
        sub[["GAME_DATE","MATCHUP","MIN","PTS","REB","AST","FG3M","PRA"]]
        .tail(20).sort_values("GAME_DATE",ascending=False),
        hide_index=True,use_container_width=True
    )
    if len(sub)<3:
        st.warning("Tylko "+str(len(sub))+" występ(y). Nie wyznaczam prognozy "
                   "z tak małej próby.")
        return
    try:
        p = calc_projection(sub,market)
    except (ValueError,KeyError,TypeError) as exc:
        st.info("Nie da się obliczyć tej statystyki: "+str(exc)[:150])
        return
    a,b,c,d = st.columns(4)
    a.metric("Średnia w próbce",f"{p['season_avg']:.1f}")
    b.metric("Ostatnie pięć",f"{p['last5']:.1f}")
    c.metric("Prognoza modelu",f"{p['prediction']:.1f}")
    d.metric("Szacowane minuty",f"{p['estimated_minutes']:.1f}")
    st.caption("Szansa i prognoza są eksperymentalne, niekalibrowane. "
               "Skład nie potwierdza udziału w nadchodzącym meczu.")
    last = sub.tail(18)
    labels = last["GAME_DATE"].dt.strftime("%d.%m.%Y").tolist()
    fig=go.Figure(go.Bar(
        x=labels,y=last[market],name=STAT_NAMES[market],
        marker_color="#EDB96A",text=last[market],textposition="outside",
    ))
    fig.add_hline(y=p["prediction"],line_dash="dash",line_color="#6FCAB9",
                  annotation_text=f"Prognoza {p['prediction']:.1f}")
    fig.update_layout(
        height=370,xaxis_title="Data meczu",yaxis_title=STAT_NAMES[market],
        paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)",
        font_color="#CFDAE7",margin=dict(t=45,b=55,l=15,r=15)
    )
    st.plotly_chart(fig,use_container_width=True)
    st.download_button("Pobierz historię zawodnika (CSV)",
                       sub.to_csv(index=False).encode("utf-8-sig"),
                       file_name="bestbets_player_logs.csv",mime="text/csv")
