"""Modern, original player prop cards for BestBets Screenshot Intelligence.

Design language: compact season hit-rate cards + one large interactive
green/red game-by-game chart, not an imitation of any particular brand.
All displayed historical frequencies remain explicitly separate from the
uncalibrated forecast for the next game.
"""
from __future__ import annotations

import math
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from core import STAT_NAMES, norm_name
from season_props import clean_player_season, observed_hit_rates


def _value(v, suffix="%", precision=0):
    try:
        x=float(v)
        return f"{x:.{precision}f}{suffix}" if math.isfinite(x) else "—"
    except (ValueError,TypeError):
        return "—"


def _n(v):
    try:
        return int(v) if pd.notna(v) else 0
    except (ValueError,TypeError):
        return 0


def _label(row):
    return (f"{row['Zawodnik']} · {row['Rynek']} "
            f"{_value(row['Linia'],suffix='',precision=1)}")


def show_season_cards(result, histories, season, events, now):
    """One compact summary per screenshot line, then an expanded hero chart."""
    st.markdown("### 🏀 Linie zawodników — analiza Over / Under")
    st.caption("Zielony = historyczne OVER, czerwony = historyczne UNDER. "
               "Wskaźnik sezonowy mierzy odsetek ROZEGRANYCH występów, "
               "nie gwarancję trafienia. Prognozy modelu oznaczone osobno.")
    size=len(result)
    if size==0:
        st.info("Nie ma jeszcze zweryfikowanych zdarzeń do pokazania.")
        return
    for start in range(0,size,2):
        cols=st.columns(2)
        for pos in range(start,min(start+2,size)):
            row=result.iloc[pos]
            with cols[pos-start]:
                with st.container(border=True):
                    title=str(row["Zawodnik"] or "Nieznany zawodnik")
                    st.markdown(f"**{title}**")
                    st.caption(f"{row.get('Drużyna') or '—'} · "
                               f"{STAT_NAMES.get(row.get('Rynek'),row.get('Rynek') or '—')} "
                               f"· linia {_value(row.get('Linia'),suffix='',precision=1)} "
                               f"· vs {row.get('Przeciwnik') or 'nieustalony'}")
                    n=_n(row.get("Występy sezon"))
                    a,b=st.columns(2)
                    a.metric("OVER sezon",_value(row.get("OVER sezon %")))
                    b.metric("UNDER sezon",_value(row.get("UNDER sezon %")))
                    st.caption(f"Próba: **{n} występów** · "
                               f"OVER L10 {_value(row.get('OVER L10 %'))} · "
                               f"UNDER L10 {_value(row.get('UNDER L10 %'))}")
                    if n<5:
                        st.warning("Za mało meczów: procenty są niestabilne.")
                    elif n<10:
                        st.caption("Niewystarczająca próba do prognozy v2.")
                    if row.get("Status")=="MODEL TESTOWY":
                        st.caption(
                            "Prognoza v2 (NIEKALIBROWANA): "
                            f"Over {_value(row.get('P(OVER) v2 %'),precision=1)} · "
                            f"Under {_value(row.get('P(UNDER) v2 %'),precision=1)}")
                    else:
                        st.caption("Prognoza v2: niedostępna — nie podajemy wymyślonych procentów.")

    options=list(range(size))
    chosen=st.selectbox("Szczegółowa karta i interaktywny wykres",
                         options,format_func=lambda i:_label(result.iloc[i]),
                         key="bb722_focus")
    row=result.iloc[chosen]
    key=str(row["Zawodnik"])
    market=str(row["Rynek"])
    line=row.get("Linia")
    with st.container(border=True):
        st.markdown(f"### {key}")
        st.caption(
            f"{row.get('Drużyna') or '—'} · {row.get('Pozycja') or '—'} · "
            f"{STAT_NAMES.get(market,market)} · "
            f"przeciwnik: {row.get('Przeciwnik') or 'niepotwierdzony'}")
        s1,s2,s3,s4=st.columns(4)
        s1.metric("Linia",_value(line,suffix='',precision=1))
        s2.metric("Średnia sezonu",_value(row.get("Śr. sezon"),suffix='',precision=1))
        s3.metric("OVER / sezon",_value(row.get("OVER sezon %")))
        s4.metric("UNDER / sezon",_value(row.get("UNDER sezon %")))
        s5,s6,s7,s8=st.columns(4)
        for col,label,field in zip(
            (s5,s6,s7,s8),
            ("L5 OVER","L10 OVER","L15 OVER","SEZON OVER"),
            ("OVER L5 %","OVER L10 %","OVER L15 %","OVER sezon %"),
        ):
            col.metric(label,_value(row.get(field)))
        n=_n(row.get("Występy sezon"))
        st.caption(f"Liczba rozegranych występów: {n} · "
                   f"źródło: {row.get('Źródło statystyk') or 'nieznane'}")
        if n<5:
            st.error(
                "Próbka jest bardzo mała. Przykładowo 1/1 = 100% historycznie, "
                "ale nie mówi nic wiarygodnego o przyszłym meczu.")
        elif n<10:
            st.warning("Mniej niż 10 występów — brak prognozy modelu v2.")
        if not pd.isna(row.get("P(OVER) v2 %")):
            m1,m2=st.columns(2)
            m1.metric("Model v2: P(OVER)",_value(row.get("P(OVER) v2 %"),precision=1))
            m2.metric("Model v2: P(UNDER)",_value(row.get("P(UNDER) v2 %"),precision=1))
            st.caption("To liczby niekalibrowanego modelu badawczego, "
                       "nie potwierdzone prawdopodobieństwa wygranej.")
        else:
            st.info("Model nie wyliczył wiarygodnej prognozy. "
                    "Historyczne częstości są dostępne tylko dla zaobserwowanych występów.")

        if pd.isna(line):
            st.warning("Brak prawidłowej linii na tym screenshotcie.")
            return
        history=(histories or {}).get(norm_name(key))
        evt=(events or {}).get(str(row.get("Drużyna") or ""))
        cutoff=(evt.get("start_utc") if isinstance(evt,dict) and
                not evt.get("ambiguous") else now)
        game=clean_player_season(history,key,season,cutoff)
        if game.empty or market not in game:
            st.info("Nie ma zweryfikowanych spotkań do narysowania wykresu.")
            return
        period=st.radio("Zakres wykresu",
                        ["L5","L10","L15","SEZON"],horizontal=True,
                        key="bb722_period")
        scope=({"L5":5,"L10":10,"L15":15}.get(period))
        displayed=game.tail(scope).copy() if scope else game.copy()
        selected_team=st.selectbox("Rozgrywki dom / wyjazd",
                                   ["Wszystkie","Dom","Wyjazd"],
                                   key="bb722_venue")
        if "MATCHUP" in displayed:
            venue=displayed["MATCHUP"].astype(str)
            if selected_team=="Dom":
                displayed=displayed[~venue.str.contains("@",regex=False)]
            elif selected_team=="Wyjazd":
                displayed=displayed[venue.str.contains("@",regex=False)]
        if displayed.empty:
            st.info("Brak występów spełniających wybrane filtry.")
            return
        values=pd.to_numeric(displayed[market],errors="coerce")
        displayed=displayed[values.notna()].copy()
        if displayed.empty:
            st.info("Brak poprawnych wartości statystyki.")
            return
        values=pd.to_numeric(displayed[market],errors="coerce")
        colors=["#29d4a0" if float(v)>float(line)
                else "#ef646d" if float(v)<float(line)
                else "#f3c361" for v in values]
        dates=pd.to_datetime(displayed["GAME_DATE"],utc=True)
        labels=[d.strftime("%d.%m") for d in dates]
        opponents=(displayed["MATCHUP"].astype(str).tolist()
                   if "MATCHUP" in displayed else [""]*len(displayed))
        fig=go.Figure()
        fig.add_trace(go.Bar(
            x=list(range(len(displayed))),y=values.tolist(),
            marker=dict(color=colors,line=dict(width=0)),
            text=[f"{v:g}" for v in values],textposition="outside",
            customdata=[[date,opp] for date,opp in zip(labels,opponents)],
            hovertemplate="%{customdata[0]} · %{customdata[1]}<br>"
                          "Wynik: %{y:g}<extra></extra>",name="Wynik"))
        fig.add_hline(y=float(line),line=dict(color="#f3c361",width=2,dash="dash"),
                      annotation_text=f"Linia {float(line):g}",
                      annotation_font_color="#f3c361")
        fig.update_layout(
            height=335,template="plotly_dark",bargap=.25,
            xaxis=dict(tickmode="array",tickvals=list(range(len(labels))),
                       ticktext=labels,showgrid=False,
                       title=None,zeroline=False),
            yaxis=dict(title=STAT_NAMES.get(market,market),rangemode="tozero",
                       showgrid=True,gridcolor="rgba(255,255,255,.08)"),
            showlegend=False,
            paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)",
            margin=dict(l=20,r=20,t=35,b=25),
        )
        st.plotly_chart(fig,use_container_width=True,
                        key="bb722_chart")
        selected_rates=observed_hit_rates(displayed,market,line)
        if selected_rates:
            current=selected_rates["season"]
            st.caption(f"Na wykresie: {current['over']}/{current['n']} OVER "
                       f"({current['over_pct']:.1f}%), "
                       f"{current['under']}/{current['n']} UNDER "
                       f"({current['under_pct']:.1f}%), "
                       f"{current['push']} zwrotów. "
                       "Zmiana filtrów wpływa na wykres, nie na prognozę v2.")
        if pd.notna(row.get("Obrona: stracone pkt/mecz")):
            st.caption("Rywal traci średnio "+
                       _value(row.get("Obrona: stracone pkt/mecz"),suffix=" pkt",precision=1)+
                       " na mecz · ostatnie 10: "+
                       _value(row.get("Obrona: L10 stracone"),suffix=" pkt",precision=1))
        st.caption(str(row.get("Uwagi") or ""))
