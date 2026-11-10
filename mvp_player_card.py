"""BestBets Player Props — one honest, production-shaped NBA research card.

The graphic deliberately resembles premium analytical dashboards in structure
(search → hero → controls → bar chart → matchup), without replicating another
app's proprietary branding, graphics, data or invented matchup grades.
"""
from __future__ import annotations
from html import escape
import math

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from core import STAT_NAMES
from season_props import clean_player_season, observed_hit_rates
from mvp_data import safe_value
from team_logos import logo_data_uri
from teams import TEAM_FULL

MARKET_TEXT={
    "PTS":"Points","REB":"Rebounds","AST":"Assists",
    "FG3M":"3-Point Made","PRA":"PTS + REB + AST",
}


def _plot(games,market,line):
    values=pd.to_numeric(games[market],errors="coerce").astype(float)
    dates=pd.to_datetime(games["GAME_DATE"],utc=True)
    matchups=games["MATCHUP"].astype(str).tolist() if "MATCHUP" in games else [""]*len(games)
    colors=["#1bdf91" if x>line else "#fb5c64" if x<line else "#f4af48"
            for x in values]
    positions=list(range(len(values)))
    hover=[[date.strftime("%d %b %Y"),str(game)] for date,game in zip(dates,matchups)]
    fig=go.Figure()
    fig.add_trace(go.Bar(
        x=positions,y=values.tolist(),
        marker=dict(color=colors,line=dict(width=0)),
        text=[f"{v:g}" for v in values],textposition="outside",
        textfont=dict(color="#eaf4ff",size=13,family="Arial"),
        customdata=hover,
        hovertemplate="%{customdata[0]} · %{customdata[1]}<br>"
                      "Wynik: %{y:g}<extra></extra>",
        name=MARKET_TEXT.get(market,market),
    ))
    fig.add_hline(
        y=float(line),line=dict(color="#e7eefa",dash="dash",width=1.7),
        annotation_text=f"LINIA {line:g}",annotation_position="top left",
        annotation_font=dict(size=12,color="#dee9fc"),
    )
    top=max(float(values.max()),line)*1.19+2
    fig.update_layout(
        height=395,bargap=.22,margin=dict(l=16,r=10,t=40,b=48),
        paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)",
        showlegend=False,font=dict(family="Arial",color="#c9d8ef"),
        xaxis=dict(tickvals=positions,ticktext=[
            date.strftime("%d/%m") for date in dates],
            showgrid=False,zeroline=False,tickfont=dict(size=10,color="#8faacf")),
        yaxis=dict(range=[0,top],showgrid=True,zeroline=False,
                   gridcolor="rgba(165,195,234,.12)",
                   tickfont=dict(color="#9cb3d2")),
        hoverlabel=dict(bgcolor="#152743",font_color="#fff"),
    )
    return fig


def _stats_panel(frequencies,venue_home,venue_away):
    pieces=[]
    for label,data in (
        ("L5",frequencies["last5"]),
        ("L10",frequencies["last10"]),
        ("L15",frequencies["last15"]),
        ("Sezon",frequencies["season"]),
    ):
        pct=data["over_pct"]
        pieces.append(
            '<div class="bbm-result-tile">'
            f'<small>{escape(label)} · HIT RATE OVER</small>'
            f'<b style="color:#27e19a">{pct:.1f}%</b>'
            f'<em>{data["over"]}/{data["n"]} występów</em></div>'
        )
    output='<div class="bbm-two" style="grid-template-columns:repeat(2,minmax(0,1fr))">'+ "".join(pieces) +'</div>'
    output+='<div class="bbm-venue-row">'
    output+=(
        '<div><small>HOME / średnia</small><strong>'
        +safe_value(venue_home,1)+'</strong></div>'
        '<div><small>AWAY / średnia</small><strong>'
        +safe_value(venue_away,1)+'</strong></div></div>'
    )
    return output


def render_player_card(row,logs,season,asof,slug="bb_mvp_prop"):
    """Render a functional full-page prop card, changing values with user inputs."""
    name=str(row.get("Zawodnik") or "")
    market=str(row.get("Rynek") or "PTS")
    if market not in STAT_NAMES:market="PTS"
    try:
        starting_line=float(row["Linia"])
    except (ValueError,TypeError,KeyError):
        st.error("Nie rozpoznano linii. Popraw wyszukiwanie.")
        return
    chosen=str(row.get("Wybór") or "OVER").upper()
    team=str(row.get("Drużyna") or "")
    person_id=row.get("_espn_id")
    games=clean_player_season(logs,name,season,asof,person_id)
    if games.empty:
        st.error("Brak zweryfikowanych występów zawodnika w tym sezonie. "
                 "Nie tworzymy wykresu z przykładowych liczb.")
        return

    co_name=escape(name)
    co_team=escape(TEAM_FULL.get(team,team))
    position=escape(str(row.get("Pozycja") or "—"))
    opponent=str(row.get("Przeciwnik") or "")
    line_frequencies=observed_hit_rates(games,market,starting_line)
    observed=line_frequencies["season"] if line_frequencies else None
    if observed is None:
        st.warning("Dla tego rynku brakuje realnych wyników.")
        return
    logo=logo_data_uri(team) if team else ""
    logo_html=(
        f'<img src="{escape(logo,quote=True)}" alt="{escape(team)}" '
        'style="width:25px;height:25px;object-fit:contain">'
        if logo else "")
    headshot=(f"https://a.espncdn.com/i/headshots/nba/players/full/{person_id}.png"
              if str(person_id or "").isdigit() else "")
    image=(f'<img class="bbm-headshot" src="{escape(headshot,quote=True)}" '
           f'alt="{co_name}">' if headshot else
           '<div class="bbm-headshot" style="display:grid;place-items:center;font-size:42px">🏀</div>')

    st.markdown(f"""
    <div class="bbm-player-head">
      {image}
      <div class="bbm-player-head-main">
        <div class="bbm-eyebrow">PLAYER PERFORMANCE</div>
        <h2>{co_name}</h2>
        <small>{logo_html} {co_team} · {position} ·
         {('vs '+escape(opponent)) if opponent else 'Przeciwnik niepotwierdzony'}</small>
        <div class="bbm-player-pills"><span class="bbm-pill">
          {escape(team)} · NBA SEASON {escape(season)}</span>
          <span class="bbm-mini-tag" style="border-radius:99px">
          {len(games)} zweryfikowanych występów</span></div>
      </div>
      <div class="bbm-player-stats">
        <div class="bbm-player-stat"><small>AVG</small>
          <b>{safe_value(observed['mean'],1)}</b><em>sezon</em></div>
        <div class="bbm-player-stat"><small>LINE</small>
          <b>{starting_line:g}</b><em>z wyszukiwarki</em></div>
        <div class="bbm-player-stat"><small>HIT RATE</small>
          <b style="color:#29e6a0">{observed['over_pct']:.0f}%</b>
          <em>Over: {observed['over']}/{observed['n']}</em></div>
      </div>
    </div>""",unsafe_allow_html=True)

    col1,col2,col3=st.columns([1.35,1,1.25],vertical_alignment="bottom")
    with col1:
        market=st.selectbox(
            "Prop / rynek",
            list(MARKET_TEXT),
            index=list(MARKET_TEXT).index(market),
            format_func=lambda x:MARKET_TEXT[x],
            key=f"{slug}_market")
    with col2:
        line=st.number_input(
            "Linia",min_value=.5,max_value=150.,value=starting_line,
            step=.5,format="%.1f",key=f"{slug}_line")
    with col3:
        side=st.radio("Kierunek",["OVER","UNDER"],horizontal=True,
                      index=1 if chosen=="UNDER" else 0,
                      key=f"{slug}_side")

    rates=observed_hit_rates(games,market,line)
    if not rates:
        st.warning("Nie ma rzeczywistych statystyk dla wybranego rynku.")
        return
    all_=rates["season"]
    selected_rate=all_["over_pct"] if side=="OVER" else all_["under_pct"]
    if market=="PRA":
        # All three components use the SAME completed games; do not sum
        # independent or incomplete per-stat samples.
        components=games[["PTS","REB","AST"]].apply(
            pd.to_numeric,errors="coerce")
        components=components.dropna()
        if not components.empty:
            averages=components.mean()
            st.markdown(
                '<div class="bbm-pra-breakdown">'
                '<strong>PRA · PUNKTY + ZBIÓRKI + ASYSTY</strong>'
                f'<span><b>{averages["PTS"]:.1f}</b> PTS</span>'
                '<em>+</em>'
                f'<span><b>{averages["REB"]:.1f}</b> REB</span>'
                '<em>+</em>'
                f'<span><b>{averages["AST"]:.1f}</b> AST</span>'
                '<em>=</em>'
                f'<span class="bbm-pra-total"><b>{averages.sum():.1f}</b> PRA / mecz</span>'
                '</div>',unsafe_allow_html=True)
    s1,s2=st.columns([1.25,1.2],vertical_alignment="bottom")
    with s1:
        period=st.radio(
            "Historia",["L5","L10","L15","SEZON"],horizontal=True,
            index=1,key=f"{slug}_period")
    with s2:
        venue=st.radio(
            "Parkiet",["Wszystkie","Dom","Wyjazd"],horizontal=True,
            key=f"{slug}_venue")
    displayed=games.tail({"L5":5,"L10":10,"L15":15}.get(period,len(games))).copy()
    if "MATCHUP" in displayed:
        away=displayed["MATCHUP"].astype(str).str.contains("@",regex=False)
        if venue=="Dom":displayed=displayed[~away]
        if venue=="Wyjazd":displayed=displayed[away]
    values=pd.to_numeric(displayed[market],errors="coerce")
    displayed=displayed[values.notna()].copy()

    left,right=st.columns([1.85,1],gap="medium")
    with left:
        st.markdown(f'<div class="bbm-section"><h3>Ostatnie mecze — '
                    f'{escape(MARKET_TEXT[market])}</h3>'
                    f'<small>Linia {line:g} · {escape(side)}</small></div>',
                    unsafe_allow_html=True)
        if displayed.empty:
            st.info("W tym okresie i na wybranym parkiecie nie ma występów.")
        else:
            st.plotly_chart(_plot(displayed,market,line),use_container_width=True,
                            key=f"{slug}_chart")
            window=observed_hit_rates(displayed,market,line)["season"]
            st.caption(f"Na wykresie: {window['over']}/{window['n']} OVER "
                       f"({window['over_pct']:.1f}%), {window['under']}/{window['n']} "
                       f"UNDER ({window['under_pct']:.1f}%). "
                       "Filtrowanie wykresu nie zmienia pełnych statystyk sezonu.")
    with right:
        st.markdown('<div class="bbm-section"><h3>Hit rate · Over</h3>'
                    '<small>rzeczywiste występy</small></div>',unsafe_allow_html=True)
        home=games["MATCHUP"].astype(str).str.contains("@",regex=False) if "MATCHUP" in games else pd.Series(False,index=games.index)
        home_avg=pd.to_numeric(games.loc[~home,market],errors="coerce").mean()
        away_avg=pd.to_numeric(games.loc[home,market],errors="coerce").mean()
        st.markdown(_stats_panel(rates,home_avg,away_avg),unsafe_allow_html=True)
        st.markdown(
            '<div class="bbm-result-tile" style="margin-top:9px">'
            '<small>WYBRANY KIERUNEK · SEZON</small>'
            f'<b style="color:{"#24e3a0" if side=="OVER" else "#ff8892"}">'
            f'{selected_rate:.1f}%</b>'
            f'<em>{all_["over"] if side=="OVER" else all_["under"]}/{all_["n"]} '
            'zakończonych występów</em></div>',unsafe_allow_html=True)
        if all_["n"]<10:
            st.warning(f"Tylko {all_['n']} występów — brak wiarygodnej próby "
                       "do wniosków o przyszłym meczu.")
        if all_["push"]:
            st.caption(f"Zwrot na całkowitej linii: {all_['push']} występów.")

    st.markdown(
        f'<div class="bbm-take"><strong>✦ BestBets Take</strong>'
        f'<span>{escape(name)} przekroczył linię {line:g} '
        f'{all_["over"]} razy w {all_["n"]} rzeczywistych występach '
        f'({all_["over_pct"]:.1f}%). UNDER: {all_["under_pct"]:.1f}%. '
        'To opis historii, a nie przewidywanie wyniku następnego meczu.'
        '</span></div>',unsafe_allow_html=True)

    opp_allowed=row.get("Obrona: stracone pkt/mecz")
    if opponent and pd.notna(opp_allowed):
        with st.container(border=True):
            st.markdown("**Matchup — realne wyniki drużyn**")
            a,b=st.columns(2)
            a.metric(f"{opponent} · tracone pkt/mecz",
                     safe_value(opp_allowed,1))
            b.metric(f"{opponent} · ostatnie 10",
                     safe_value(row.get("Obrona: L10 stracone"),1))
            st.caption("Statystyka całej drużyny — nie jest rankingiem "
                       "obrony pozycji tego zawodnika.")
    else:
        st.caption("Ocena obrony rywala: brak potwierdzonych danych. "
                   "Nie generujemy umownej oceny matchup A+.")

    with st.expander("Źródło danych, ostrzeżenia i historia",expanded=False):
        st.caption(str(row.get("Źródło statystyk") or "ESPN/NBA"))
        st.caption(str(row.get("Uwagi") or ""))
        keep=["GAME_DATE","MATCHUP","MIN","PTS","REB","AST","FG3M","PRA"]
        st.dataframe(games[[x for x in keep if x in games]].tail(25).iloc[::-1],
                     hide_index=True,use_container_width=True)
        st.caption("Żaden odsetek historyczny nie gwarantuje wyniku kolejnego meczu.")
