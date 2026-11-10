"""Unified BestBets premium player cards for natural search, OCR and manual props.

All charts are derived from real completed NBA games. A plot-wide market/line
change recalculates *observed* rates immediately. The speculative model result
is displayed only for the exact analyzed market/line, never reused on edits.
"""
from __future__ import annotations

from html import escape
import math

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from core import STAT_NAMES, norm_name
from season_props import clean_player_season, observed_hit_rates

MARKET_TABS = {
    "PTS":"PTS", "REB":"REB", "AST":"AST", "FG3M":"3PM", "PRA":"PRA",
}


def _number(v, digits=0, tail=""):
    try:
        f=float(v)
        if math.isfinite(f):
            return f"{f:.{digits}f}{tail}"
    except (ValueError,TypeError):
        pass
    return "—"


def _count(value):
    try:
        return int(value) if pd.notna(value) else 0
    except (TypeError,ValueError):
        return 0


def _label(row):
    side=str(row.get("Wybór") or "").strip().upper()
    return (f"{row['Zawodnik']} · {side+' ' if side in ('OVER','UNDER') else ''}"
            f"{str(row.get('Rynek') or 'PTS')} "
            f"{_number(row.get('Linia'),1)}")


def _histogram_summary(row):
    return (f"{_count(row.get('Występy sezon'))} meczów · "
            f"Over L10 {_number(row.get('OVER L10 %'),0,'%')} · "
            f"Under L10 {_number(row.get('UNDER L10 %'),0,'%')}")


def _summary_cards(result):
    for block in range(0,len(result),2):
        grid=st.columns(2)
        for index in range(block,min(block+2,len(result))):
            row=result.iloc[index]
            with grid[index-block]:
                name=escape(str(row.get("Zawodnik") or "Nieznany"))
                team=escape(str(row.get("Drużyna") or "—"))
                market=escape(str(row.get("Rynek") or "PTS"))
                opponent=escape(str(row.get("Przeciwnik") or "?"))
                side=str(row.get("Wybór") or "").upper()
                cls="under" if side=="UNDER" else "over"
                side_title=(side+" " if side in ("OVER","UNDER") else "")+_number(
                    row.get("Linia"),1)
                side_str=escape(side_title)
                rate=(_number(row.get("UNDER sezon %"),0,"%")
                      if side=="UNDER" else
                      _number(row.get("OVER sezon %"),0,"%"))
                over=_number(row.get("OVER sezon %"),0,"%")
                under=_number(row.get("UNDER sezon %"),0,"%")
                n=_count(row.get("Występy sezon"))
                alert=("PRÓBA NIEWYSTARCZAJĄCA" if n<10 else
                       "CZĘSTOŚĆ HISTORYCZNA")
                st.markdown(f"""
                <div class="bb-prop-hero" style="padding:18px;margin:0 0 12px">
                  <div class="bb-prop-top">
                    <div><div class="bb-prop-name" style="font-size:20px">{name}</div>
                      <div class="bb-prop-subtitle">{team} · vs {opponent} · {market}</div></div>
                    <span class="bb-prop-label {cls}">{side_str} {market}</span>
                  </div>
                  <div class="bb-prop-strip" style="grid-template-columns:repeat(3,minmax(0,1fr))">
                    <div class="bb-prop-tile"><span class="name">OVER / sezon</span>
                      <span class="val over">{escape(over)}</span></div>
                    <div class="bb-prop-tile"><span class="name">UNDER / sezon</span>
                      <span class="val under">{escape(under)}</span></div>
                    <div class="bb-prop-tile"><span class="name">Występy</span>
                      <span class="val">{n}</span></div>
                  </div>
                  <div class="bb-prop-subtitle" style="margin-top:11px">
                     {escape(alert)} · wybrany kierunek: {escape(rate)}
                  </div>
                </div>
                """,unsafe_allow_html=True)


def _bar_chart(data, market, line, side):
    dates=pd.to_datetime(data["GAME_DATE"],errors="coerce",utc=True)
    numbers=pd.to_numeric(data[market],errors="coerce")
    matches=(data["MATCHUP"].astype(str).tolist()
             if "MATCHUP" in data else [""]*len(data))
    series=[float(v) for v in numbers]
    colors=["#2cddb1" if v>line else "#fa6478" if v<line else "#f6be64"
            for v in series]
    labels=[date.strftime("%d/%m") for date in dates]
    indices=list(range(len(data)))
    chart=go.Figure()
    chart.add_trace(go.Bar(
        x=indices,y=series,
        marker=dict(color=colors,line=dict(width=0)),
        text=[f"{v:g}" for v in series],textposition="outside",
        textfont=dict(color="#e6eeff",size=12,family="Space Grotesk"),
        customdata=[[day,match] for day,match in zip(labels,matches)],
        hovertemplate="<b>%{customdata[0]}</b> · %{customdata[1]}<br>"
                      "Statystyka: <b>%{y:g}</b><extra></extra>",
        name="Rzeczywiste występy"))
    chart.add_hline(
        y=line,line=dict(color="#f6be64",width=2,dash="dash"),
        annotation_text=f"LINIA {line:g}",
        annotation_position="top left",
        annotation_font=dict(color="#f9d58f",size=12))
    top=max(max(series,default=0),line)*1.22+1
    chart.update_layout(
        height=385,bargap=.23,
        margin=dict(l=12,r=10,t=36,b=20),
        xaxis=dict(tickmode="array",tickvals=indices,ticktext=labels,
                   tickfont=dict(size=11,color="#95accf"),
                   showgrid=False,zeroline=False,title=None),
        yaxis=dict(range=[0,top],tickfont=dict(color="#8da7d0"),
                   gridcolor="rgba(150,176,223,.11)",gridwidth=1,
                   showline=False,zeroline=False,title=None),
        font=dict(family="DM Sans",color="#eaf2ff"),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        showlegend=False,
        hoverlabel=dict(bgcolor="#132645",font_color="#e7f5ff"),
        dragmode=False,
    )
    return chart


def show_season_cards(result, histories, season, events, now, key_prefix="bb722"):
    st.markdown("### Player Props Intelligence")
    st.caption(
        "Oryginalny panel BestBets. Zielone słupki oznaczają historyczne OVER, "
        "czerwone UNDER, a bursztynowa linia wskazuje próg. "
        "Częstości występów nie są skalibrowanymi szansami wygranej.")
    if result is None or result.empty:
        st.info("Brak rozpoznanych zdarzeń do pokazania.")
        return
    _summary_cards(result)
    focus=st.selectbox(
        "🔎 Wybierz zdarzenie do pełnej analizy",
        list(range(len(result))),
        format_func=lambda i:_label(result.iloc[i]),
        key=key_prefix+"_focus")
    row=result.iloc[focus]
    name=str(row.get("Zawodnik") or "Nieznany")
    original_market=str(row.get("Rynek") or "PTS")
    original_line=row.get("Linia")
    if pd.isna(original_line):
        st.warning("Brak prawidłowej linii. Popraw ją w wyszukiwarce lub OCR.")
        return
    name_key=norm_name(name)
    history=(histories or {}).get(name_key)
    team=str(row.get("Drużyna") or "")
    event=(events or {}).get(team)
    asof=(event.get("start_utc") if isinstance(event,dict) and
          not event.get("ambiguous") else now)
    games=clean_player_season(history,name,season,asof)
    if games.empty:
        st.error("Brak rzeczywistych sezonowych boxscore dla tego zawodnika. "
                 "Nie pokazujemy fikcyjnych wykresów ani procentów.")
        return

    st.markdown("#### Personalizuj rynek i linię")
    col_market,col_line,col_side=st.columns([1.2,1,1.05],vertical_alignment="bottom")
    unique=f"{key_prefix}_{focus}"
    with col_market:
        market=st.selectbox(
            "Rodzaj statystyki",
            list(MARKET_TABS),
            index=list(MARKET_TABS).index(original_market)
                  if original_market in MARKET_TABS else 0,
            format_func=lambda k:f"{MARKET_TABS[k]} · {STAT_NAMES[k]}",
            key=unique+"_market")
    with col_line:
        line=st.number_input(
            "Linia bukmachera",value=float(original_line),
            min_value=.5,max_value=150.,step=.5,format="%.1f",
            key=unique+"_line")
    with col_side:
        preferred=str(row.get("Wybór") or "").upper()
        side=st.radio(
            "Kierunek",options=["OVER","UNDER"],horizontal=True,
            index=1 if preferred=="UNDER" else 0,
            key=unique+"_side")
    try:
        observed=observed_hit_rates(games,market,line)
    except ValueError:
        observed=None
    if not observed:
        st.error("Brak potwierdzonych statystyk tego rynku w sezonie.")
        return
    season_data=observed["season"];l5=observed["last5"]
    l10=observed["last10"];l15=observed["last15"]
    n=season_data["n"]
    season_over=season_data["over_pct"];season_under=season_data["under_pct"]
    over_width=max(0,min(100,season_over))
    under_width=max(0,min(100,season_under))
    cls="under" if side=="UNDER" else "over"
    rate=season_under if side=="UNDER" else season_over
    safe_name=escape(name);safe_team=escape(team)
    safe_position=escape(str(row.get("Pozycja") or "—"))
    safe_rival=escape(str(row.get("Przeciwnik") or "nieustalony"))
    st.markdown(f"""
    <div class="bb-prop-hero">
      <div class="bb-eyebrow">PLAYER PERFORMANCE · ZWERYFIKOWANE MECZE</div>
      <div class="bb-prop-top">
        <div>
          <div class="bb-prop-name">{safe_name}</div>
          <div class="bb-prop-subtitle">{safe_team} · {safe_position}
          &nbsp; / &nbsp; vs {safe_rival}</div>
        </div>
        <span class="bb-prop-label {cls}">{side} {line:g} · {MARKET_TABS[market]}</span>
      </div>
      <div class="bb-prop-strip">
        <div class="bb-prop-tile">
          <span class="name">Średnia sezonu</span>
          <span class="val">{_number(season_data['mean'],1)}</span>
          <span class="desc">{n} występów</span>
        </div>
        <div class="bb-prop-tile">
          <span class="name">OVER / sezon</span>
          <span class="val over">{season_over:.1f}%</span>
          <span class="desc">{season_data['over']}/{n} meczów</span>
        </div>
        <div class="bb-prop-tile">
          <span class="name">UNDER / sezon</span>
          <span class="val under">{season_under:.1f}%</span>
          <span class="desc">{season_data['under']}/{n} meczów</span>
        </div>
        <div class="bb-prop-tile">
          <span class="name">Wybrany {side}</span>
          <span class="val {cls}">{rate:.1f}%</span>
          <span class="desc">HIT RATE, nie prognoza</span>
        </div>
      </div>
      <div class="bb-highlight-bar">
        <span class="over" style="width:{over_width:.3f}%"></span>
        <span class="under" style="width:{under_width:.3f}%"></span>
      </div>
    </div>
    """,unsafe_allow_html=True)

    fast=st.columns(4)
    for col,label,part in zip(
        fast,("L5","L10","L15","SEZON"),
        (l5,l10,l15,season_data)):
        with col:
            col.metric(
                label+" · "+side,
                _number(part["under_pct"] if side=="UNDER" else
                        part["over_pct"],0,"%"),
                help=(f"{part['under'] if side=='UNDER' else part['over']} "
                      f"trafień z {part['n']} rzeczywistych występów"))
    if n<5:
        st.error(
            f"Tylko {n} rzeczywistych występów. "
            "100% z 1/1 nie jest wiarygodną oceną przyszłego meczu.")
    elif n<10:
        st.warning(f"Próba {n} występów — model v2 wymaga minimum 10 meczów.")
    if season_data["push"]:
        st.caption(f"Zwroty przy całkowitej linii: {season_data['push']} "
                   f"({season_data['push_pct']:.1f}%). OVER + UNDER + ZWROT = 100%.")

    f1,f2,f3=st.columns([1,1,1])
    with f1:
        period=st.radio(
            "Okres na wykresie",["L5","L10","L15","SEZON"],
            horizontal=True,key=unique+"_period")
    with f2:
        venue=st.selectbox(
            "Dom / wyjazd",["Wszystkie","Dom","Wyjazd"],
            key=unique+"_venue")
    with f3:
        opponents=[str(x) for x in games["OPPONENT"].dropna().unique()
                   if str(x)] if "OPPONENT" in games else []
        opponent_filter=st.selectbox(
            "Przeciwko",["Wszystkim"]+sorted(set(opponents)),
            key=unique+"_opponent")
    take={"L5":5,"L10":10,"L15":15}.get(period)
    shown=games.tail(take).copy() if take else games.copy()
    if venue!="Wszystkie" and "MATCHUP" in shown:
        away=shown["MATCHUP"].astype(str).str.contains("@",regex=False)
        shown=shown[away if venue=="Wyjazd" else ~away]
    if opponent_filter!="Wszystkim" and "OPPONENT" in shown:
        shown=shown[shown["OPPONENT"].astype(str)==opponent_filter]
    shown=shown[pd.to_numeric(shown[market],errors="coerce").notna()]
    if shown.empty:
        st.info("Dla tej kombinacji filtrów brak zakończonych występów.")
    else:
        st.plotly_chart(
            _bar_chart(shown,market,line,side),use_container_width=True,
            key=unique+"_plot")
        rates=observed_hit_rates(shown,market,line)
        group=rates["season"]
        st.caption(
            f"WYŚWIETLANY WYKRES: {group['over']}/{group['n']} OVER "
            f"({group['over_pct']:.1f}%) · {group['under']}/{group['n']} UNDER "
            f"({group['under_pct']:.1f}%) · {group['push']} zwrotów. "
            "Filtry zmieniają wykres i te liczby, nie średnie sezonowe powyżej.")

    st.markdown("#### Model badawczy i matchup")
    # The saved OCR estimate can include opponent defense. Changing the market
    # or line invalidates the research estimate; don't reuse stale numbers.
    unchanged=(market==original_market and
               math.isclose(line,float(original_line),abs_tol=1e-7))
    model_over=row.get("P(OVER) v2 %")
    model_under=row.get("P(UNDER) v2 %")
    if unchanged and pd.notna(model_over) and pd.notna(model_under):
        a,b=st.columns(2)
        a.metric("Prediction Engine 2.0 · OVER",
                 _number(model_over,1,"%"))
        b.metric("Prediction Engine 2.0 · UNDER",
                 _number(model_under,1,"%"))
    elif n>=10 and not math.isclose(line,round(line),abs_tol=1e-8):
        try:
            from prediction_engine_v2 import forecast_v2
            recalculated=forecast_v2(
                games,market,line,asof,min_games=10,draws=2048)
            a,b=st.columns(2)
            a.metric("v2 OVER · bez korekty rywala",
                     f"{100*recalculated['p_over']:.1f}%")
            b.metric("v2 UNDER · bez korekty rywala",
                     f"{100*recalculated['p_under']:.1f}%")
            st.caption(
                "Po zmianie rynku lub linii model przeliczono od nowa "
                "bez dopasowania defensywy rywala. Wersja NIEKALIBROWANA.")
        except (ValueError,TypeError,KeyError) as exc:
            st.caption("Model v2 nie może ocenić tej konfiguracji: "+str(exc)[:130])
    else:
        st.caption(
            "Niewystarczająca historia lub całkowita linia — "
            "brak dwustanowej prognozy v2 (możliwy zwrot).")
    pts_allowed=row.get("Obrona: stracone pkt/mecz")
    if unchanged and pd.notna(pts_allowed):
        c1,c2=st.columns(2)
        c1.metric("Rywal traci · pkt na mecz",
                  _number(pts_allowed,1))
        c2.metric("Rywal traci · ostatnie 10",
                  _number(row.get("Obrona: L10 stracone"),1))
        st.caption("To statystyka całej drużyny, nie obrona konkretnej pozycji.")
    elif unchanged:
        st.caption("Nie ma zweryfikowanej korekty obrony przeciwnika.")
    if "MIN" in games:
        mins=pd.to_numeric(games["MIN"],errors="coerce").dropna()
        if not mins.empty:
            st.caption(
                f"Minuty: średnia sezonu {mins.mean():.1f} · "
                f"L5 {mins.tail(5).mean():.1f}. "
                "Minuty i dostępność zawodnika mogą zmienić przyszły wynik.")
    if unchanged:
        st.caption(str(row.get("Uwagi") or ""))
    st.info(
        "Historyczny hit rate to odsetek rozegranych meczów. "
        "Wynik modelu jest eksperymentalny i niekalibrowany. "
        "Żaden z nich nie stanowi gwarancji trafienia typu.")


def show_manual_player_card(history,player,market,line,season,team="",position=""):
    """Identical premium experience in manually selected player calculator."""
    from season_props import SEASON_RESULT_COLUMNS
    timestamp=pd.Timestamp.now(tz="UTC")
    data=clean_player_season(history,player,season,timestamp)
    if data.empty:
        st.warning("Nie udało się pobrać sezonowych występów zawodnika.")
        return
    rates=observed_hit_rates(data,market,line)
    if not rates:
        st.warning("Brak rzeczywistych statystyk dla tego rynku.")
        return
    row={c:None for c in SEASON_RESULT_COLUMNS}
    row.update({
        "Zawodnik":player,
        "Drużyna":team or str(data.iloc[-1]["TEAM_ABBREVIATION"]),
        "Pozycja":position or "—",
        "Przeciwnik":None,
        "Rynek":market,"Linia":float(line),
        "Występy sezon":rates["season"]["n"],
        "OVER sezon %":rates["season"]["over_pct"],
        "UNDER sezon %":rates["season"]["under_pct"],
        "Śr. sezon":rates["season"]["mean"],
        "Źródło statystyk":"ESPN/NBA — rzeczywiste mecze",
        "Uwagi":"Brak automatycznego matchupu dla ręcznej analizy.",
        "Status":"TYLKO HISTORIA",
    })
    for n in (5,10,15):
        v=rates[f"last{n}"]
        row[f"OVER L{n} %"]=v["over_pct"]
        row[f"UNDER L{n} %"]=v["under_pct"]
    show_season_cards(
        pd.DataFrame([row],columns=SEASON_RESULT_COLUMNS),
        {norm_name(player):data},season,{},timestamp,
        key_prefix="bb723_manual")
