"""BestBets v7.21: bookmaker screenshot to real season-long player statistics.

Screenshots are input ONLY: player name, market, line, optional price.
Player history, team and opponent are independently verified from NBA/ESPN.
No generated odds, no uncalibrated 'guaranteed win' badges or blind tips.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from hashlib import sha256

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from core import STAT_NAMES, norm_name, normalize_logs
from screenshot_import import EDIT_COLUMNS, read_screenshot
from season_props import (
    analyze_season_offers, clean_player_season, upcoming_team_games,
)
from simulation_sources import historical_espn_results
from espn_player_data import detailed_espn_gamelog


@st.cache_data(ttl=3*3600, max_entries=120, show_spinner=False)
def _cached_espn_player_season(player_id, name, team, season, nonce):
    """One season-long ESPN gamelog request per athlete, only on Analyze."""
    raw, meta=detailed_espn_gamelog(player_id,name,team,season)
    return normalize_logs(raw),meta


def _safe_catalog(nonce):
    from roster_view import cached_global_player_catalog
    try:
        return cached_global_player_catalog(nonce)
    except (RuntimeError,ValueError,TypeError,KeyError) as exc:
        return pd.DataFrame(),{"missing_teams":["ALL"],"warning":str(exc)[:150]}


def _load_full_season(edited, season, nonce, get_logs):
    """Resolve roster ID and bulk-load each requested player with bounded workers.

    Fallback data is visibly marked PARTIAL. Never fabricate missing players or
    seasons from league averages. No private screenshot leaves the Streamlit app.
    """
    catalog,coverage=_safe_catalog(nonce)
    identities={}
    histories={}
    candidates={}
    rows=catalog.to_dict("records") if isinstance(catalog,pd.DataFrame) else []
    for row in rows:
        key=norm_name(str(row.get("PLAYER_NAME") or ""))
        if key:
            candidates.setdefault(key,[]).append(row)
    misses=[]
    for name in edited["Zawodnik"].dropna().astype(str).unique():
        key=norm_name(name)
        options=candidates.get(key,[])
        if len(options)==1:
            found=options[0]
            player_id=str(found.get("PLAYER_ID") or "")
            team=str(found.get("TEAM_ABBREVIATION") or "")
            identities[key]={"id":player_id,"team":team,
                             "source":"ESPN — sezonowy gamelog",
                             "partial":False,"stale":False}
        elif len(options)>1:
            identities[key]={"ambiguous":True}
        else:
            misses.append(name)
    def one(name,player):
        key=norm_name(name)
        player_id=player["id"]
        if not player_id.isdigit():
            return key,None,"Nieznany identyfikator ESPN."
        try:
            data,meta=_cached_espn_player_season(
                player_id,name,player["team"],season,nonce)
            return key,(data,meta),None
        except (ValueError,KeyError,TypeError,RuntimeError) as exc:
            return key,None,str(exc)[:130]
    tasks=[]
    with ThreadPoolExecutor(max_workers=5) as pool:
        futures={
            pool.submit(one,name,identities[norm_name(name)]):norm_name(name)
            for name in edited["Zawodnik"].dropna().astype(str).unique()
            if norm_name(name) in identities and identities[norm_name(name)].get("id")}
        for completed in as_completed(futures):
            key,bundle,error=completed.result()
            if bundle:
                data,meta=bundle
                histories[key]=data
                identities[key]["stale"]=bool(meta.get("stale",False))
                if meta.get("stale"):
                    identities[key]["partial"]=True
            else:
                misses.append(
                    next((n for n in edited["Zawodnik"].astype(str)
                          if norm_name(n)==key),key))
    if misses:
        # Existing NBA Stats can provide all game logs; its CDN/ESPN fallback
        # may be partial, hence an explicit partial label rather than all-season.
        raw,meta=get_logs()
        if raw is not None and not raw.empty:
            source=meta.get("source","Nieznane") if isinstance(meta,dict) else "Nieznane"
            for name in misses:
                key=norm_name(name)
                subset=raw[raw["PLAYER_NAME"].map(norm_name)==key].copy()
                if subset.empty:continue
                by_club=subset.sort_values("GAME_DATE")
                team=str(by_club.iloc[-1]["TEAM_ABBREVIATION"])
                ids=by_club["PLAYER_ID"].dropna().astype(str).unique().tolist() if "PLAYER_ID" in by_club else []
                identities[key]={"id":ids[0] if len(ids)==1 else None,
                                 "team":team,
                                 "source":str(source)+" — możliwa próbka częściowa",
                                 "partial":True,"stale":bool((meta or {}).get("stale"))}
                histories[key]=subset
    return histories,identities,coverage


def _player_chart(history, name, season, market, line, asof):
    g=clean_player_season(history,name,season,asof)
    if g.empty or market not in g:return
    vals=pd.to_numeric(g[market],errors="coerce")
    fig=go.Figure()
    fig.add_bar(
        x=g["GAME_DATE"],y=vals,
        marker_color=["#1fd18d" if v>line else "#ff6868" if v<line
                      else "#c4a252" for v in vals],
        customdata=g["MATCHUP"] if "MATCHUP" in g else None,
        hovertemplate="%{x|%d %b}: %{y:.0f}<extra></extra>",
        name="Wynik")
    fig.add_hline(y=line,line_dash="dash",line_color="#f7bf43",
                  annotation_text=f"Linia {line:g}")
    fig.update_layout(
        height=310,margin=dict(l=12,r=12,b=22,t=12),
        xaxis_title=None,yaxis_title=STAT_NAMES.get(market,market),
        showlegend=False,template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(fig,use_container_width=True)


def render_screenshot_calculator(season, get_logs, load_schedule=None, nonce=0,
                                  viewer_timezone=None):
    st.markdown("#### 📷 Screenshot → analiza całego sezonu i obrony rywala")
    st.caption(
        "Obraz służy WYŁĄCZNIE do odczytania zawodników, linii i kursów. "
        "Rzeczywiste statystyki pobieramy osobno z sezonowych logów ESPN/NBA. "
        "Najpierw zobaczysz częstość Over/Under w rozegranych występach, "
        "a obok testowy model po uwzględnieniu defensywy przeciwnika.")
    st.warning(
        "OCR może pomylić nazwisko, linię albo kurs. Każdy wiersz trzeba sprawdzić "
        "z oryginalnym screenem. Brak kursu nie uniemożliwia analizy historycznej.")
    upload=st.file_uploader(
        "Screenshot bukmachera (PNG, JPG, WEBP; maks. 8 MB)",
        type=["png","jpg","jpeg","webp"],key="bb717_screen_upload",
        help="Nie dodawaj screenshotów z danymi konta, saldem czy identyfikatorem użytkownika.")
    market=st.selectbox(
        "Domyślny rynek na screenshotcie",list(STAT_NAMES),
        format_func=lambda k:STAT_NAMES[k],key="bb717_market")
    tz=viewer_timezone or "Europe/Warsaw"
    local_today=pd.Timestamp.now(tz="UTC").tz_convert(tz).date()
    game_day=st.date_input(
        "Dzień meczów, których dotyczy screenshot (godzina lokalna)",
        value=local_today,key="bb721_game_date",
        help="Pozwala znaleźć realnego przeciwnika każdego zawodnika. "
             "Jeśli nie da się ustalić meczu, nie wymyślamy defensywnej korekty.")
    if "bb717_rows" not in st.session_state:
        st.session_state.bb717_rows=pd.DataFrame(columns=EDIT_COLUMNS)
    if "bb721_result" not in st.session_state:
        st.session_state.bb721_result=pd.DataFrame()
    if upload is not None:
        image_bytes=upload.getvalue()
        digest=sha256(image_bytes).hexdigest()
        if digest!=st.session_state.get("bb717_current_hash"):
            st.session_state.bb717_current_hash=digest
            st.session_state.bb717_rows=pd.DataFrame(columns=EDIT_COLUMNS)
            st.session_state.bb721_result=pd.DataFrame()
            st.session_state.pop("bb717_editor",None)
            st.session_state.pop("bb721_result_hash",None)
        with st.expander("Oryginalny screenshot",expanded=False):
            st.image(image_bytes,use_container_width=True)
        if st.button("🔎 Odczytaj linie i kursy z obrazu",
                     key="bb717_recognize",type="primary"):
            try:
                frame,meta=read_screenshot(image_bytes,default_market=market)
                st.session_state.bb717_rows=frame
                st.session_state.bb721_result=pd.DataFrame()
                st.session_state["bb721_result_hash"]=None
                st.session_state["bb717_ocr_meta"]=meta
                st.session_state.pop("bb717_editor",None)
                if frame.empty:
                    st.error(meta.get("warning","Nie rozpoznano pozycji."))
                else:
                    st.success(f"Odczytano {len(frame)} linii. "
                               f"Nierozpoznane kursy: {meta['unreadable_odds']}. "
                               "Brakujące wiersze możesz dopisać ręcznie.")
            except (RuntimeError,ValueError) as exc:
                st.error("Nie udało się odczytać obrazu: "+str(exc)[:160])
    else:
        st.caption("Możesz też ręcznie dodać wiersze bez przesyłania obrazu.")
    st.markdown("##### 1. Zweryfikuj rozpoznane nazwiska i linie")
    edited=st.data_editor(
        st.session_state.bb717_rows,key="bb717_editor",num_rows="dynamic",
        use_container_width=True,hide_index=True,
        column_config={
            "Zawodnik":st.column_config.TextColumn("Zawodnik",required=True),
            "Rynek":st.column_config.SelectboxColumn("Rynek",options=list(STAT_NAMES),required=True),
            "Linia":st.column_config.NumberColumn("Linia",min_value=.5,max_value=150.,step=.5),
            "Kurs OVER":st.column_config.NumberColumn("Kurs OVER",min_value=1.01,max_value=15.),
            "Kurs UNDER":st.column_config.NumberColumn("Kurs UNDER",min_value=1.01,max_value=15.),
            "Weryfikacja OCR":st.column_config.TextColumn("OCR",disabled=True),
        })
    edited=edited.reindex(columns=EDIT_COLUMNS)
    if not edited.empty:
        st.caption(f"{len(edited)} pozycji. Każda zostanie sprawdzona względem "
                   "rzeczywistej historii NBA/ESPN i terminarza wybranego dnia.")
    confirmed=st.checkbox(
        "Sprawdziłem/am nazwiska, rynki, linie i dostępne kursy na oryginalnym obrazie.",
        value=False,key="bb717_verified")
    config_hash=sha256(
        (edited.to_csv(index=False)+"|"+season+"|"+str(game_day)).encode("utf8")).hexdigest()
    if st.button(
        "📊 Analizuj cały sezon, przeciwników i Over/Under",
        key="bb717_analyze",disabled=edited.empty or not confirmed,type="primary"):
        with st.spinner("Weryfikuję zawodników, pobieram ich historię sezonu oraz obronę rywali…"):
            try:
                players,identities,catalog_meta=_load_full_season(
                    edited,season,nonce,get_logs)
                if load_schedule is not None:
                    sched,sched_meta=load_schedule(nonce)
                    if sched_meta.get("stale"):
                        st.warning("Terminarz jest nieaktualny — nie potwierdzamy przeciwników.")
                        events={}
                    else:
                        events=upcoming_team_games(
                            sched,game_day,tz,pd.Timestamp.now(tz="UTC"))
                else:
                    events={}
                results,warnings=historical_espn_results(season)
                if warnings or results is None or results.empty:
                    st.warning("Niekompletne statystyki defensywy ESPN. "
                               "Nie będziemy stosować korekty dla brakujących rywali.")
                    results=pd.DataFrame()
                table=analyze_season_offers(
                    edited,players,identities,events,results,
                    season,pd.Timestamp.now(tz="UTC"))
                st.session_state.bb721_result=table
                st.session_state.bb721_result_hash=config_hash
                st.session_state.bb721_histories=players
                st.session_state.bb721_ident=identities
                st.session_state.bb721_events=events
                st.session_state.bb721_catalog_meta=catalog_meta
            except (ValueError,TypeError,KeyError,RuntimeError) as exc:
                st.error("Nie można przeprowadzić zbiorczej analizy: "+str(exc)[:190])
                st.session_state.bb721_result=pd.DataFrame()
    result=st.session_state.bb721_result
    if not result.empty and st.session_state.get("bb721_result_hash")==config_hash:
        st.markdown("##### 2. Wyniki dla wszystkich zawodników")
        valid=int(result["Występy sezon"].notna().sum())
        modeled=int((result["Status"]=="MODEL TESTOWY").sum())
        x,y,z=st.columns(3)
        x.metric("Rynki ze screena",len(result))
        y.metric("Z historią sezonu",valid)
        z.metric("Model eksperymentalny",modeled)
        st.caption("OVER/UNDER sezon = rzeczywisty odsetek rozegranych WYSTĘPÓW na "
                   "tej konkretnej linii. Prognoza v2 = osobne, niekalibrowane "
                   "prawdopodobieństwo kolejnego meczu, warunkowo skorygowane "
                   "o obronę CAŁEJ drużyny przeciwnika dla PTS/PRA.")
        tabs=st.tabs(["Wyniki Over / Under","Obrona rywala i niepewność",
                      "Historia każdego zawodnika"])
        with tabs[0]:
            fields=["Zawodnik","Drużyna","Przeciwnik","Linia",
                    "Występy sezon","OVER sezon %","UNDER sezon %",
                    "OVER L10 %","UNDER L10 %","P(OVER) v2 %",
                    "P(UNDER) v2 %","Status"]
            st.dataframe(result[fields],hide_index=True,use_container_width=True,
                         height=min(710,80+len(result)*37))
        with tabs[1]:
            fields=["Zawodnik","Rynek","Przeciwnik",
                    "Obrona: stracone pkt/mecz","Obrona: L10 stracone",
                    "Korekta PTS (%)","P(OVER) bez defensywy %",
                    "P(OVER) v2 %","P(UNDER) v2 %",
                    "Źródło statystyk","Uwagi"]
            st.dataframe(result[fields],hide_index=True,use_container_width=True,
                         height=min(710,80+len(result)*37))
            st.warning(
                "Korekta rywala to hipoteza na podstawie punktów traconych "
                "przez całą drużynę. Nie jest to pomiar obrony konkretnej pozycji. "
                "NIE potwierdzono kalibracji, wpływu kontuzji ani przewagi nad kursami.")
        with tabs[2]:
            names=result["Zawodnik"].tolist()
            selected=st.selectbox("Szczegóły i wykres punktów z sezonu",
                                  names,key="bb721_selected_player")
            entry=result[result["Zawodnik"]==selected].iloc[0]
            st.caption(
                f"{selected} · {entry['Drużyna'] or 'klub nieznany'} · "
                f"linia {entry['Linia']} {entry['Rynek']} · "
                f"sezon: {entry['Występy sezon'] or 0} występów.")
            sub=(st.session_state.get("bb721_histories") or {}).get(norm_name(selected))
            event=(st.session_state.get("bb721_events") or {}).get(entry["Drużyna"])
            end=(event.get("start_utc") if event and not event.get("ambiguous")
                 else pd.Timestamp.now(tz="UTC"))
            if sub is not None and not sub.empty and pd.notna(entry["Linia"]):
                _player_chart(sub,selected,season,entry["Rynek"],float(entry["Linia"]),end)
            st.caption(str(entry["Uwagi"]))
        st.download_button(
            "Eksportuj sprawdzone statystyki sezonu i prognozy CSV",
            result.to_csv(index=False).encode("utf-8-sig"),
            file_name="bestbets_season_props_v721.csv",mime="text/csv",
            key="bb721_export")
        st.info(
            "Wybór zakładu należy do użytkownika. BestBets nie oznacza żadnej "
            "pozycji jako pewnej ani automatycznie nie wybiera Over/Under. "
            "Próbki poniżej 10 meczów nie otrzymują prognoz modelu; "
            "brakujące dane są jawnie opisane.")
    elif not result.empty:
        st.info("Zmieniono linie lub dzień spotkań. Uruchom analizę ponownie.")
