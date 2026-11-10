"""Lean Player Props UI. No OCR, bookmaker tables or phantom probability grades.

Natural query → confirm roster identity → real season data → analytical card.
Source fetches occur only when a user explicitly requests an analysis.
"""
from __future__ import annotations

from hashlib import sha256
from html import escape

import pandas as pd
import streamlit as st

from core import norm_name
from prop_search import parse_prop_batch, resolve_catalog_player
from screenshot_ui import _load_full_season, _safe_catalog
from season_props import analyze_season_offers, upcoming_team_games
from simulation_sources import historical_espn_results
from mvp_player_card import render_player_card

EXAMPLES=(
    "Jayson Tatum over 25.5 points",
    "Jayson Tatum under 3.5 assists",
    "Jayson Tatum over 2.5 three-pointers",
    "Jayson Tatum over 7.5 rebounds",
)


def _preset(value):
    st.session_state["bb_mvp_search_text"]=value
    # Changing a query invalidates the old result; never reuse unrelated lines.
    st.session_state.pop("bb_mvp_search_results",None)
    st.session_state.pop("bb_mvp_search_parse",None)


def _match_proposals(queries,catalog):
    names=[]
    proposals=[]
    for query in queries:
        resolved=resolve_catalog_player(query["name_input"],catalog)
        proposals.append({
            "Zawodnik":resolved["name"],
            "Kierunek":query["side"],"Rynek":query["market"],
            "Linia":query["line"],"Kurs OVER":None,"Kurs UNDER":None,
            "Dopasowanie":resolved["quality"],
            "_id":resolved["id"],"_team":resolved.get("team") or "",
            "_input":query["name_input"],
        })
        names.append(resolved["name"])
    return pd.DataFrame(proposals)


def _run_research(offers,season,nonce,day,zone,load_schedule,get_logs):
    histories,identities,coverage=_load_full_season(
        offers,season,nonce,get_logs)
    events={}
    schedule_notes=[]
    try:
        fixture,meta=load_schedule(nonce)
        if isinstance(meta,dict) and meta.get("stale"):
            schedule_notes.append("Terminarz nieaktualny; brak pewnego matchup.")
        else:
            events=upcoming_team_games(
                fixture,day,zone,pd.Timestamp.now(tz="UTC"))
    except (ValueError,TypeError,KeyError,RuntimeError) as exc:
        schedule_notes.append("Terminarz niedostępny: "+str(exc)[:100])
    try:
        history,issues=historical_espn_results(season)
        if issues:
            schedule_notes.append("Wyniki drużyn mogą być niepełne.")
            history=pd.DataFrame()
    except (ValueError,TypeError,KeyError,RuntimeError):
        history=pd.DataFrame()
        schedule_notes.append("Brak potwierdzonej defensywy rywali.")
    result=analyze_season_offers(
        offers,histories,identities,events,history,
        season,pd.Timestamp.now(tz="UTC"))
    result["Wybór"]=offers["Kierunek"].astype(str).to_numpy()
    result["_espn_id"]=[
        (identities.get(norm_name(name)) or {}).get("id")
        for name in result["Zawodnik"]
    ]
    return result,histories,events,schedule_notes


def render_player_props(season,nonce,timezone,load_schedule,get_logs):
    st.markdown("""
    <div class="bbm-hero-search">
      <div class="bbm-kicker">PLAYER PROPS · BESTBETS INTELLIGENCE</div>
      <h2>Find the line. Know the numbers.</h2>
      <p>Wpisz zawodnika, OVER/UNDER, linię i rynek. Zobacz zweryfikowaną
      historię, a nie procent wyliczony z jednego losowego występu.</p>
    </div>""",unsafe_allow_html=True)
    if "bb_mvp_search_text" not in st.session_state:
        st.session_state["bb_mvp_search_text"]=""
    with st.form("bb_mvp_search_form",border=False):
        term=st.text_input(
            "🔎 Wyszukaj zawodnika i rynek",
            placeholder="Jayson Tatum over 25.5 points",
            key="bb_mvp_search_text")
        submitted=st.form_submit_button(
            "🔎 Analizuj zawodnika",type="primary",
            use_container_width=True)
    st.caption("Szybkie przykłady:")
    chips=st.columns(4,gap="small")
    for i,(col,example) in enumerate(zip(chips,EXAMPLES)):
        with col:
            st.button(
                ("PTS" if i==0 else "AST" if i==1 else
                 "3PM" if i==2 else "REB")+
                " · "+example.split("over ")[-1].split("under ")[-1].split(" ")[0],
                key=f"bbm_example_{i}",use_container_width=True,
                on_click=_preset,args=(example,),
                help=example)
    zone=timezone or "Europe/Warsaw"
    with st.expander("📆 Dzień meczu i wiele zdarzeń",expanded=False):
        day=st.date_input(
            "Dzień lokalny spotkań",
            pd.Timestamp.now(tz="UTC").tz_convert(zone).date(),
            key="bb_mvp_analysis_day")
        st.caption("Możesz wkleić wiele wierszy oddzielonych enterem lub średnikiem. "
                   "Dla różnych spotkań wybierz właściwy dzień.")
    if "bb_mvp_analysis_day" not in st.session_state:
        day=pd.Timestamp.now(tz="UTC").tz_convert(zone).date()
    else:
        day=st.session_state["bb_mvp_analysis_day"]
    sig=sha256((str(term)+"|"+str(day)+"|"+season).encode("utf8")).hexdigest()

    if submitted:
        try:
            parsed,errors=parse_prop_batch(term,max_items=12)
        except ValueError as exc:
            parsed=[];errors=[str(exc)]
        for error in errors:
            st.warning(error)
        if not parsed:
            st.session_state.pop("bb_mvp_search_parse",None)
            if not errors:st.info("Wpisz co najmniej jedno zdarzenie.")
        else:
            with st.spinner("Weryfikuję aktualne składy NBA…"):
                catalog,cov=_safe_catalog(nonce)
                offers=_match_proposals(parsed,catalog)
            st.session_state["bb_mvp_search_parse"]=(offers,sig)
            st.session_state.pop("bb_mvp_search_results",None)
            # Exact, unique roster matches need only ONE search click.
            # Suggested/ambiguous matches still require explicit verification.
            if not offers.empty and bool(
                (offers["Dopasowanie"]=="exact").all()):
                with st.spinner("Pobieram sezonowe występy i analizę rywala…"):
                    try:
                        table,histories,events,issues=_run_research(
                            offers,season,nonce,day,zone,load_schedule,get_logs)
                        st.session_state["bb_mvp_search_results"]={
                            "signature":sig,"table":table,
                            "histories":histories,"events":events,
                            "issues":issues}
                    except (ValueError,RuntimeError,KeyError,TypeError) as exc:
                        st.warning("Nie udało się pobrać historii: "+str(exc)[:160])

    parsed=st.session_state.get("bb_mvp_search_parse")
    if not parsed or parsed[1]!=sig:
        if not submitted:
            st.markdown(
                '<div class="bbm-note">Wyszukaj zdarzenie powyżej. '
                'Wykres zostanie zbudowany wyłącznie na rzeczywistych '
                'występach wybranego zawodnika.</div>',
                unsafe_allow_html=True)
        return
    offers=parsed[0]
    unknown=offers[offers["Dopasowanie"].isin(
        ["ambiguous","unknown","no_catalog"])]
    if not unknown.empty:
        st.error(
            "Nie znaleziono jednoznacznie: "+
            ", ".join(unknown["Zawodnik"].astype(str))+
            ". Popraw imię i nazwisko, a następnie wyszukaj ponownie.")
        return
    suggested=offers[offers["Dopasowanie"]=="suggested"]
    if not suggested.empty:
        st.warning(
            "Dopasowanie po literówce: "+
            ", ".join(f'{r["_input"]} → {r["Zawodnik"]}'
                      for r in suggested.to_dict("records"))+
            ". Sprawdź, czy to właściwi zawodnicy.")
        if not st.checkbox(
            "Potwierdzam sugerowane nazwiska i linie",
            key="bb_mvp_confirm_names"):
            return
    else:
        st.caption("✓ Zawodnik i rynek rozpoznane w aktualnym katalogu NBA.")
    if len(offers)>1:
        with st.expander(f"Sprawdź {len(offers)} rozpoznanych zdarzeń",
                         expanded=False):
            st.dataframe(offers[["Zawodnik","Kierunek","Rynek","Linia"]],
                         hide_index=True,use_container_width=True)
    has_current=(st.session_state.get("bb_mvp_search_results") or {}).get(
        "signature")==sig
    if st.button(
        "↻ Odśwież wyniki" if has_current else "📊 Pokaż analizę i wykresy",
        type="secondary" if has_current else "primary",
        key="bb_mvp_fetch_full",use_container_width=True):
        with st.spinner("Pobieram realne sezonowe wyniki zawodników…"):
            try:
                table,histories,events,issues=_run_research(
                    offers,season,nonce,day,zone,load_schedule,get_logs)
                st.session_state["bb_mvp_search_results"]={
                    "signature":sig,"table":table,
                    "histories":histories,"events":events,
                    "issues":issues,
                }
            except (ValueError,RuntimeError,KeyError,TypeError) as exc:
                st.error("Nie udało się pobrać występów: "+str(exc)[:180])
                st.session_state.pop("bb_mvp_search_results",None)

    saved=st.session_state.get("bb_mvp_search_results")
    if not saved or saved["signature"]!=sig:return
    result=saved["table"]
    if result is None or result.empty:
        st.error("Brak potwierdzonych statystyk dla tych typów.")
        return
    missing=int(result["Występy sezon"].isna().sum())
    if missing:
        st.warning(f"{missing}/{len(result)} pozycji nie ma poprawnej historii. "
                   "Nie podajemy dla nich nieistniejących procentów.")
    ready=result[result["Występy sezon"].notna()].copy()
    if ready.empty:
        with st.expander("Problemy źródeł danych",expanded=True):
            st.dataframe(result[["Zawodnik","Status","Uwagi"]],
                         hide_index=True,use_container_width=True)
        return
    if len(ready)>1:
        index=st.selectbox(
            "Wybierz kartę zawodnika",
            list(ready.index),
            format_func=lambda i:(
                f'{result.loc[i,"Zawodnik"]} · '
                f'{result.loc[i,"Wybór"]} {result.loc[i,"Linia"]} '
                f'{result.loc[i,"Rynek"]}'),
            key="bb_mvp_search_selected")
    else:
        index=ready.index[0]
    row=result.loc[index]
    name=str(row["Zawodnik"])
    if st.button(
        ("★ Usuń z ulubionych" if any(
            f.get("name")==name for f in
            st.session_state.get("bb_mvp_favorite_players",[]))
         else "☆ Dodaj zawodnika do ulubionych"),
        key="bb_mvp_favorite_person"):
        favorites=list(st.session_state.get("bb_mvp_favorite_players",[]))
        favorites=[f for f in favorites if f.get("name")!=name] if any(
            f.get("name")==name for f in favorites) else favorites+[{
                "name":name,"team":str(row.get("Drużyna") or "")}]
        st.session_state["bb_mvp_favorite_players"]=favorites
        st.rerun()
    group=saved["histories"].get(norm_name(name))
    event=saved["events"].get(str(row.get("Drużyna") or ""))
    asof=(
        event.get("start_utc") if isinstance(event,dict) and
        not event.get("ambiguous") else pd.Timestamp.now(tz="UTC"))
    render_player_card(
        row,group,season,asof,slug=f"bb_mvp_prop_{index}")

    if saved["issues"]:
        with st.expander("Źródła i ograniczenia meczu",expanded=False):
            for item in saved["issues"]:
                st.caption(str(item))
