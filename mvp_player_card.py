"""Reference-perfect interactive Player Props research screen for BestBets.

All headline percentages, splits, bar values and matchup context come from
observed NBA results. A visual matchup-grade slot is present but stays N/D
unless a separately validated graded model is implemented.
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
MARKET_SHORT=("PTS","REB","AST","FG3M","PRA")


def _sync_market_to_tabs(slug):
    st.session_state[f"{slug}_market_tabs"]=st.session_state[f"{slug}_market"]


def _sync_tabs_to_market(slug):
    st.session_state[f"{slug}_market"]=st.session_state[f"{slug}_market_tabs"]


def _number(value,digits=1):
    try:
        v=float(value)
        return f"{v:.{digits}f}" if math.isfinite(v) else "—"
    except (TypeError,ValueError):
        return "—"


def _opponent_from_matchup(value):
    match=str(value or "").strip()
    if "@" in match:return match.split("@")[-1].strip()
    if "vs." in match:return match.split("vs.")[-1].strip()
    if "vs" in match:return match.split("vs")[-1].strip()
    return ""


def _plot(games,market,line):
    """Bright red/green screenshot-style bars with authentic boxscores."""
    values=pd.to_numeric(games[market],errors="coerce")
    dates=pd.to_datetime(games["GAME_DATE"],errors="coerce",utc=True)
    actual=[float(x) for x in values]
    count=len(games)
    x=list(range(count))
    opponents=[
        _opponent_from_matchup(v) for v in
        (games["MATCHUP"].tolist() if "MATCHUP" in games else [""]*count)
    ]
    chart=go.Figure()
    chart.add_trace(go.Bar(
        x=x,y=actual,
        marker=dict(
            color=["#00e66a" if v>line else "#ff5149" if v<line
                   else "#ffaf39" for v in actual],
            line=dict(width=0)
        ),
        text=[f"{v:g}" for v in actual],
        textposition="outside",
        textfont=dict(color="#f7fcff",size=16,family="Arial Black"),
        customdata=[[t.strftime("%d/%m"),opp] for t,opp in
                    zip(dates,opponents)],
        hovertemplate="<b>%{customdata[0]} %{customdata[1]}</b><br>"
                      "Wynik: %{y:g}<extra></extra>",
    ))
    chart.add_hline(
        y=float(line),line=dict(color="#e5f4ff",width=1.6,dash="dash"),
        annotation_text=f"  {line:g}  ",
        annotation_position="top left",
        annotation_font=dict(color="#fff",size=14),
    )
    top=max([float(line),*actual])*1.17+1.3
    labels=[
        f"{t.strftime('%m/%d')}<br>{'@'+opp if '@' in str(m) else opp}"
        for t,opp,m in zip(
            dates,opponents,
            games["MATCHUP"].tolist() if "MATCHUP" in games else [""]*count)
    ]
    chart.update_layout(
        height=415,bargap=.20,
        margin=dict(l=23,r=12,t=34,b=20),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Arial",color="#eef6ff"),
        showlegend=False,dragmode=False,
        xaxis=dict(
            tickmode="array",tickvals=x,ticktext=labels,
            tickfont=dict(size=13,color="#c4d5e9"),
            showgrid=False,zeroline=False,showline=True,
            linecolor="#3d6386",
        ),
        yaxis=dict(
            range=[0,top],gridcolor="rgba(140,180,220,.13)",
            tickfont=dict(color="#afc8e4",size=13),
            showline=False,zeroline=False,title=None,
            nticks=6,
        ),
        hoverlabel=dict(bgcolor="#152f53",font_color="#fff"),
    )
    return chart


def _team_logo_html(team,size=48):
    image=logo_data_uri(team) if team in TEAM_FULL else ""
    if not image:
        return '<span style="font-size:28px;color:#7abaff">🏀</span>'
    return (
        f'<img src="{escape(image,quote=True)}" '
        f'alt="{escape(str(team))}" '
        f'width="{size}" height="{size}">'
    )


def _headline_html(name,team,position,opponent,headshot,season,
                   observed,line,l10,opp_defense=None):
    img=(
        f'<img src="{escape(headshot,quote=True)}" '
        f'alt="Zdjęcie: {escape(name,quote=True)}" loading="lazy">'
        if headshot else
        '<span style="font-size:58px;color:#0dd99b">♙</span>'
    )
    pos=str(position or "—")
    if pos.lower() in ("nan","none","null"):pos="—"
    opponent_label=f"vs {escape(opponent)}" if opponent else "Rywal do potwierdzenia"
    opp_heading=_number(opp_defense,1) if opp_defense is not None else "—"
    return f"""
    <div class="bb83-hero">
      <div class="bb83-portrait">
        <div class="bb83-team-back">{_team_logo_html(team,88)}</div>
        {img}
      </div>
      <div class="bb83-identity">
        <h2>{escape(name)}</h2>
        <div class="bb83-identity-line">
          <span class="bb83-team-badge">{escape(team)}</span>
          <b>{escape(pos)}</b><span>│</span>
          <span>{opponent_label}</span>
        </div>
        <small>NBA {escape(season)} · Realne występy ·
        {observed['n']} meczów z danymi rynku</small>
      </div>
      <div class="bb83-hero-metrics">
        <div class="bb83-hero-metric"><label>AVG</label>
          <b>{_number(observed['mean'])}</b><em>sezon</em></div>
        <div class="bb83-hero-metric"><label>LINE</label>
          <b>{line:g}</b><em>bukmacher</em></div>
        <div class="bb83-hero-metric"><label>HIT RATE</label>
          <b style="color:#13ed7e">{l10['over_pct']:.0f}%</b>
          <em>L10 ({l10['over']}/{l10['n']})</em></div>
        <div class="bb83-hero-metric"><label>OPP DEF</label>
          <b>{opp_heading}</b><em>pkt tracone</em></div>
      </div>
      <div class="bb83-grade">
        <small>MATCHUP GRADE</small>
        <b>—</b><em>niekalibrowana</em>
      </div>
    </div>
    """


def _defense_html(row,opponent):
    value=row.get("Obrona: stracone pkt/mecz")
    recent=row.get("Obrona: L10 stracone")
    if opponent and pd.notna(value):
        return (
            f'<div class="bb83-defense"><h4><span>⬡</span> vs {escape(opponent)} '
            'Defense</h4><div class="bb83-defense-inner">'
            f'<div class="bb83-defense-logo">{_team_logo_html(opponent)}</div>'
            '<div class="bb83-defense-points">'
            f'<div>Rywal traci <b>{_number(value)} pkt/mecz</b></div>'
            f'<div>Ostatnie 10: <b>{_number(recent)} pkt/mecz</b></div>'
            '<div>Obrona zespołowa · bez rankingu pozycji</div>'
            '</div></div></div>'
        )
    return (
        '<div class="bb83-defense">'
        '<h4><span>⬡</span> Matchup Defense</h4>'
        '<div class="bb83-defense-inner">'
        '<div class="bb83-defense-logo">◈</div>'
        '<div class="bb83-defense-points">'
        '<div>Brak potwierdzonej obrony rywala</div>'
        '<div>Nie przypisujemy fikcyjnego rankingu</div>'
        '<div>Wykres i hit rate nadal bazują na meczach</div>'
        '</div></div></div>'
    )


def _stats_panel(frequencies,home_avg,away_avg,market,side,row,opponent):
    """All four time windows and team defense visible without scrolling."""
    cls="under" if side=="UNDER" else ""
    markup=['<div class="bb83-right-panel"><div class="bb83-rate-grid">']
    for label,part in (
        ("L5",frequencies["last5"]),
        ("L10",frequencies["last10"]),
        ("L15",frequencies["last15"]),
        ("Season",frequencies["season"])):
        wins=part["over"] if side=="OVER" else part["under"]
        percentage=part["over_pct"] if side=="OVER" else part["under_pct"]
        markup.append(
            '<div class="bb83-rate-card">'
            f'<small>{label}<br>Hit Rate</small>'
            f'<b class="{cls}">{percentage:.0f}%</b>'
            f'<em>({wins}/{part["n"]})</em>'
            '</div>'
        )
    markup.append('</div><div class="bb83-split-grid">')
    markup.extend([
        '<div class="bb83-split-card"><small>Season AVG</small>'
        f'<b>{_number(frequencies["season"]["mean"])}</b></div>',
        '<div class="bb83-split-card accent"><small>⌂ Home AVG</small>'
        f'<b>{_number(home_avg)}</b></div>',
        '<div class="bb83-split-card"><small>➤ Away AVG</small>'
        f'<b>{_number(away_avg)}</b></div>',
    ])
    markup.append("</div>")
    markup.append(_defense_html(row,opponent))
    markup.append("</div>")
    return "".join(markup)


def _take_html(name,market,line,side,full):
    count=full["over"] if side=="OVER" else full["under"]
    percentage=full["over_pct"] if side=="OVER" else full["under_pct"]
    desc=(f'<em>{side} {line:g} {escape(MARKET_TEXT[market])}</em> '
          f'wystąpił w <b>{count} z {full["n"]} meczów</b> '
          f'({percentage:.1f}%).')
    if full["n"]<10:
        desc+=(" Próba jest niewielka — nie traktuj wyniku "
               "jako prognozy następnego meczu.")
    else:
        desc+=(" To częstotliwość historyczna, nie "
               "skalibrowane prawdopodobieństwo przyszłego typu.")
    return (
        '<div class="bb83-take">'
        '<strong><span>◎</span> BestBets Take</strong>'
        f'<span>{escape(name)}: {desc}</span>'
        '</div>'
    )


def render_player_card(row,logs,season,asof,slug="bb_mvp_prop"):
    """Compact single-screen reference layout, all controls live."""
    name=str(row.get("Zawodnik") or "")
    initial_market=str(row.get("Rynek") or "PTS")
    if initial_market not in MARKET_SHORT:initial_market="PTS"
    try:
        initial_line=float(row["Linia"])
    except (KeyError,TypeError,ValueError):
        st.error("Nie udało się rozpoznać linii. Wpisz zdarzenie ponownie.")
        return
    initial_side=str(row.get("Wybór") or "OVER").upper()
    team=str(row.get("Drużyna") or "")
    person_id=row.get("_espn_id")
    games=clean_player_season(logs,name,season,asof,person_id)
    if games.empty:
        st.error("Brak zweryfikowanych występów w sezonie. "
                 "Nie pokazujemy wykresu na fikcyjnych danych.")
        return
    opponent=str(row.get("Przeciwnik") or "")
    if opponent.lower() in ("nan","none"):opponent=""

    # Render headline ahead of controls, but populate after controls have
    # resolved their current state so displayed AVG and hit rate are LIVE.
    hero=st.empty()
    market_key=f"{slug}_market"
    shortcut_key=f"{slug}_market_tabs"
    st.session_state.setdefault(market_key,initial_market)
    st.session_state.setdefault(shortcut_key,st.session_state[market_key])
    with st.container(key="bb83-controls"):
        m,l,s,shortcuts,range_col=st.columns(
            [1.05,.72,1.05,1.58,1.32],gap="small",
            vertical_alignment="bottom")
        with m:
            market=st.selectbox(
                "Rynek",list(MARKET_SHORT),
                format_func=lambda key:MARKET_TEXT[key],
                key=market_key,on_change=_sync_market_to_tabs,args=(slug,))
        with l:
            line=st.number_input(
                "Linia",min_value=.5,max_value=150.,value=initial_line,
                step=.5,format="%.1f",key=f"{slug}_line")
        with s:
            side=st.segmented_control(
                "Strona",["OVER","UNDER"],
                default=initial_side if initial_side in ("OVER","UNDER") else "OVER",
                key=f"{slug}_side")
        with shortcuts:
            st.segmented_control(
                "Szybki wybór PTS / REB / AST / 3PM / PRA",
                list(MARKET_SHORT),format_func=lambda key:"3PM" if key=="FG3M" else key,
                key=shortcut_key,on_change=_sync_tabs_to_market,args=(slug,))
        with range_col:
            period=st.segmented_control(
                "Historia",["L5","L10","L15","SEZON"],
                default="L10",key=f"{slug}_period")

    rates=observed_hit_rates(games,market,line)
    if not rates:
        st.error("Dla wybranego rynku nie ma prawidłowych statystyk.")
        return
    all_=rates["season"]
    l10=rates["last10"]
    photo=(f"https://a.espncdn.com/i/headshots/nba/players/full/{person_id}.png"
           if str(person_id or "").isdigit() else "")
    opp_def=row.get("Obrona: stracone pkt/mecz")
    if pd.isna(opp_def):opp_def=None
    hero.markdown(
        _headline_html(
            name,team,row.get("Pozycja"),opponent,photo,season,
            all_,float(line),l10,opp_def),
        unsafe_allow_html=True,
    )

    # The chart window is chosen in the control strip, not in a separate row.
    selected=games.tail({
        "L5":5,"L10":10,"L15":15}.get(period,len(games))).copy()
    if market not in selected:
        st.error("Źródło nie zawiera kolumny statystyki "+market)
        return
    selected=selected[
        pd.to_numeric(selected[market],errors="coerce").notna()].copy()
    selected=selected[pd.to_numeric(selected[market],errors="coerce")>=0]
    # Filter optional: state read now, widget rendered further down.
    venue=st.session_state.get(f"{slug}_venue","Wszystkie")
    if venue!="Wszystkie" and "MATCHUP" in selected:
        away_flag=selected["MATCHUP"].fillna("").astype(str).str.contains(
            "@",regex=False)
        selected=selected[away_flag if venue=="Wyjazd" else ~away_flag]
    opponent_games=games["MATCHUP"].fillna("").astype(str) if "MATCHUP" in games else pd.Series("",index=games.index)
    known=opponent_games.str.contains("@",regex=False)|opponent_games.str.contains("vs",case=False,regex=False)
    away=opponent_games.str.contains("@",regex=False)
    home_avg=(
        pd.to_numeric(games.loc[known & ~away,market],errors="coerce").mean()
        if known.any() else float("nan"))
    away_avg=(
        pd.to_numeric(games.loc[known & away,market],errors="coerce").mean()
        if known.any() else float("nan"))

    with st.container(key="bb83-research"):
        chart_col,stats_col=st.columns([1.75,1.07],gap="small")
        with chart_col:
            st.markdown(
                '<div class="bb83-chart-head"><strong><span>▥</span> '
                f'{escape(period if period!="SEZON" else "Season")} Games'
                f' — {escape(MARKET_TEXT[market])}</strong>'
                f'<small>Linia {line:g} · {escape(side)}</small></div>',
                unsafe_allow_html=True)
            if selected.empty:
                st.info("Brak występów dla wybranych filtrów.")
            else:
                st.plotly_chart(
                    _plot(selected,market,line),use_container_width=True,
                    key=f"{slug}_plot")
        with stats_col:
            st.markdown(
                _stats_panel(rates,home_avg,away_avg,market,side,row,opponent),
                unsafe_allow_html=True)
    if market=="PRA":
        components=games[["PTS","REB","AST"]].apply(
            pd.to_numeric,errors="coerce").dropna()
        if not components.empty:
            avg=components.mean()
            st.markdown(
                '<div class="bb83-pra-inline bbm-pra-breakdown">'
                '<strong>PRA = PTS + REB + AST</strong>'
                f'<span>{avg["PTS"]:.1f} PTS</span> + '
                f'<span>{avg["REB"]:.1f} REB</span> + '
                f'<span>{avg["AST"]:.1f} AST</span> = '
                f'<b>{avg.sum():.1f} PRA / mecz</b></div>',
                unsafe_allow_html=True)
    st.markdown(
        _take_html(name,market,float(line),side,all_),
        unsafe_allow_html=True)
    with st.expander("Filtry, próbki i metodologia",expanded=False):
        st.radio(
            "Parkiet",["Wszystkie","Dom","Wyjazd"],
            key=f"{slug}_venue",horizontal=True)
        st.caption(
            "Czerwony słupek = wynik poniżej linii, zielony = powyżej. "
            "Całkowita linia może zakończyć się zwrotem.")
        if all_["push"]:
            st.caption(f"Liczba zwrotów dla linii: {all_['push']}.")
        st.caption(str(row.get("Źródło statystyk") or "Źródło NBA/ESPN"))
        warnings=str(row.get("Uwagi") or "")
        if warnings and warnings.lower()!="nan":
            st.caption(warnings)
        cols=[key for key in (
            "GAME_DATE","MATCHUP","MIN","PTS","REB","AST","FG3M","PRA")
            if key in games]
        st.dataframe(
            games[cols].tail(30).iloc[::-1],
            hide_index=True,use_container_width=True)
