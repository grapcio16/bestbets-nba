"""Natural-language BestBets Player Props search — verified season-only NBA data.

Input can be one query or multiple newline-separated offers. This UI never
guesses sportsbook odds and requires the user to approve fuzzy athlete matches.
The same research pipeline serves screenshot OCR and natural-language inputs.
"""
from __future__ import annotations

from hashlib import sha256
import html

import pandas as pd
import streamlit as st

from core import STAT_NAMES
from prop_search import parse_prop_batch, resolve_catalog_player
from screenshot_ui import _load_full_season, _safe_catalog
from screenshot_cards import show_season_cards
from season_props import analyze_season_offers, upcoming_team_games
from simulation_sources import historical_espn_results


def _prepare_rows(queries,catalog):
    values=[]
    for query in queries:
        match=resolve_catalog_player(query["name_input"],catalog)
        values.append({
            "Zawodnik":match["name"],
            "Kierunek":query["side"],
            "Rynek":query["market"],
            "Linia":query["line"],
            "Kurs OVER":None,
            "Kurs UNDER":None,
            "Dopasowanie":{
                "exact":"Dokładnie",
                "suggested":f"Sugerowane · {round(100*match['confidence'])}%",
                "ambiguous":"Niejednoznaczny — popraw",
                "unknown":"Nie znaleziono — popraw",
                "no_catalog":"Katalog niedostępny — sprawdź",
            }.get(match["quality"],"Sprawdź"),
        })
    return pd.DataFrame(values)


def render_natural_prop_search(season,get_logs,load_schedule,nonce,timezone):
    st.markdown("""
    <div class="bb-search-hero">
      <div class="bb-eyebrow">PLAYER PROPS · BESTBETS SEARCH</div>
      <div class="bb-search-title">Wpisz typ. Sprawdź każdy występ.</div>
      <div class="bb-search-description">
      Zamiast przeszukiwać tabele, wpisz zawodnika, OVER lub UNDER, linię
      oraz rodzaj statystyki. Każda analiza korzysta z realnej historii sezonu NBA.
      </div>
      <div class="bb-search-examples">
        <span>Jayson Tatum over 25,5 points</span>
        <span>Jayson Tatum under 3,5 assists</span>
        <span>Jayson Tatum over 2,5 three point</span>
        <span>Jayson Tatum over 7,5 rebounds</span>
      </div>
    </div>
    """,unsafe_allow_html=True)
    search=st.text_area(
        "🔎 Wyszukaj typy zawodników",
        value="",
        placeholder="Jayson Tatum over 25,5 points\n"
                    "Jayson Tatum under 3,5 assists\n"
                    "Jayson Tatum over 2,5 three point\n"
                    "Jayson Tatum over 7,5 rebounds",
        height=128,key="bb723_search_text",
        help="Jeden typ w wierszu, maksymalnie 12 typów. Akceptujemy przecinek "
             "lub kropkę oraz także polskie powyżej/poniżej.")
    first,second=st.columns([1,2])
    with first:
        submitted=st.button("🔎 Wyszukaj zdarzenia",type="primary",
                            use_container_width=True,key="bb723_parse")
    with second:
        st.caption("Wpisy typu *Jason Tatum uver 25,5 point* są rozpoznawane, "
                   "ale ewentualne dopasowanie nazwiska trzeba potwierdzić.")
    if submitted:
        try:
            queries,errors=parse_prop_batch(search)
        except ValueError as exc:
            queries=[];errors=[str(exc)]
        if errors:
            for e in errors:
                st.warning(e)
        if queries:
            with st.spinner("Weryfikuję zawodników w katalogu NBA…"):
                catalog,coverage=_safe_catalog(nonce)
                rows=_prepare_rows(queries,catalog)
            st.session_state["bb723_rows"]=rows
            st.session_state["bb723_parsed_text"]=search
            st.session_state.pop("bb723_editor",None)
            st.session_state.pop("bb723_results",None)
            st.session_state.pop("bb723_result_sig",None)
        elif not errors:
            st.info("Wpisz przynajmniej jedno zdarzenie.")
    if "bb723_rows" not in st.session_state:
        st.info("Wpisz typ powyżej i wybierz „Wyszukaj zdarzenia”. "
                "Następnie możesz przejść do wykresu i pełnej historii.")
        return
    if st.session_state.get("bb723_parsed_text")!=search:
        st.info("Treść wyszukiwarki zmieniła się — kliknij „Wyszukaj zdarzenia” "
                "ponownie, aby wykorzystać nowe linie.")
        return

    st.markdown("#### Zweryfikuj odczytane zdarzenia")
    st.caption("Nazwiska sugerowane po literówce i błędne dopasowania możesz "
               "poprawić w tabeli. Kursy są dobrowolne i nie wpływają na "
               "historyczny odsetek Over/Under.")
    edited=st.data_editor(
        st.session_state["bb723_rows"],
        key="bb723_editor",
        use_container_width=True,hide_index=True,num_rows="dynamic",
        column_config={
            "Zawodnik":st.column_config.TextColumn("Zawodnik",required=True),
            "Kierunek":st.column_config.SelectboxColumn(
                "Strona",options=["OVER","UNDER"],required=True),
            "Rynek":st.column_config.SelectboxColumn(
                "Rynek",options=list(STAT_NAMES),required=True),
            "Linia":st.column_config.NumberColumn(
                "Linia",min_value=.5,max_value=150.,step=.5,required=True),
            "Kurs OVER":st.column_config.NumberColumn(
                "Kurs Over",min_value=1.01,max_value=100.),
            "Kurs UNDER":st.column_config.NumberColumn(
                "Kurs Under",min_value=1.01,max_value=100.),
            "Dopasowanie":st.column_config.TextColumn(
                "Rozpoznanie",disabled=True),
        })
    viewer=timezone or "Europe/Warsaw"
    day=st.date_input(
        "Dzień analizowanych spotkań (strefa lokalna)",
        value=pd.Timestamp.now(tz="UTC").tz_convert(viewer).date(),
        key="bb723_selected_day")
    verified=st.checkbox(
        "Potwierdzam nazwiska (w tym dopasowania literówek), kierunki, "
        "rodzaj statystyk i linie.",
        value=False,key="bb723_verified")
    sig=sha256((
        edited.to_csv(index=False)+"|"+str(day)+"|"+season
    ).encode("utf-8")).hexdigest()
    analyze=st.button(
        "📈 Pokaż wykresy i procenty Over / Under",
        type="primary",use_container_width=True,
        key="bb723_analyze",disabled=not verified or edited.empty)
    if analyze:
        with st.spinner("Pobieram rzeczywiste występy sezonu i dane rywali…"):
            try:
                players,identities,catalog_meta=_load_full_season(
                    edited,season,nonce,get_logs)
                if load_schedule:
                    sched,meta=load_schedule(nonce)
                    if isinstance(meta,dict) and meta.get("stale"):
                        events={}
                        st.warning("Terminarz nie jest aktualny. "
                                   "Nie ustalamy przeciwników na podstawie niepewnych danych.")
                    else:
                        events=upcoming_team_games(
                            sched,day,viewer,pd.Timestamp.now(tz="UTC"))
                else:
                    events={}
                finals,notes=historical_espn_results(season)
                if notes or finals is None or finals.empty:
                    finals=pd.DataFrame()
                    st.warning("Brak potwierdzonych danych o obronie drużyn. "
                               "Nie stosujemy przybliżonych korekt rywala.")
                result=analyze_season_offers(
                    edited,players,identities,events,finals,
                    season,pd.Timestamp.now(tz="UTC"))
                # Preserve user-picked OVER/UNDER, not an automatic recommendation.
                result["Wybór"]=edited["Kierunek"].astype(str).to_numpy()
                st.session_state["bb723_results"]=(result,players,events)
                st.session_state["bb723_result_sig"]=sig
            except (ValueError,KeyError,TypeError,RuntimeError) as exc:
                st.error("Analiza danych nie powiodła się: "+str(exc)[:190])
                st.session_state.pop("bb723_results",None)

    data=st.session_state.get("bb723_results")
    if not data:return
    if st.session_state.get("bb723_result_sig")!=sig:
        st.info("Zmieniłeś linię, zawodnika lub datę. "
                "Ponownie uruchom analizę, aby aktualizować wyniki.")
        return
    frame,players,events=data
    if frame.empty:
        st.warning("Brak prawidłowych zdarzeń.")
        return
    num=int(frame["Występy sezon"].notna().sum())
    enough=int((pd.to_numeric(frame["Występy sezon"],errors="coerce")>=10).sum())
    a,b,c=st.columns(3)
    a.metric("Analizowane rynki",str(len(frame)))
    b.metric("Z historią",f"{num}/{len(frame)}")
    c.metric("Min. 10 spotkań",f"{enough}/{len(frame)}")
    if num==0:
        st.warning("Nie pobrano wiarygodnej historii dla tych zawodników. "
                   "Nie zastępujemy danych sztucznym prawdopodobieństwem.")
    tabs=st.tabs(["📊 Wykres i karta premium","🛡️ Obrona / źródła",
                  "📄 Pełne zestawienie"])
    with tabs[0]:
        show_season_cards(
            frame,players,season,events,pd.Timestamp.now(tz="UTC"),
            key_prefix="bb723_search")
    with tabs[1]:
        cols=["Zawodnik","Rynek","Linia","Przeciwnik",
              "Obrona: stracone pkt/mecz","Obrona: L10 stracone",
              "Korekta PTS (%)","Występy sezon",
              "Źródło statystyk","Uwagi"]
        st.dataframe(frame[[x for x in cols if x in frame]],
                     hide_index=True,use_container_width=True)
    with tabs[2]:
        st.dataframe(frame,hide_index=True,use_container_width=True)
        st.download_button(
            "Eksportuj analizę CSV",
            frame.to_csv(index=False).encode("utf-8-sig"),
            file_name="bestbets_search_props_v723.csv",
            mime="text/csv",key="bb723_csv")
    st.caption("Historyczne występy ≠ przyszłe prawdopodobieństwo. "
               "Model v2 jest badawczy i niekalibrowany; bez realnych "
               "danych nie wyświetlamy prognoz.")
