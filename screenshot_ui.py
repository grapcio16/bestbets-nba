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
from screenshot_cards import show_season_cards
from simulation_sources import historical_espn_results
from espn_player_data import detailed_espn_gamelog


def _cached_espn_player_season(player_id, name, team, season, nonce):
    """One season-long ESPN gamelog request per athlete. ESPN requests are disk-cached 6h."""
    raw, meta=detailed_espn_gamelog(player_id,name,team,season)
    return normalize_logs(raw),meta


def _safe_catalog(nonce):
    from roster_view import cached_global_player_catalog
    try:
        return cached_global_player_catalog(nonce)
    except (RuntimeError,ValueError,TypeError,KeyError) as exc:
        return pd.DataFrame(),{"missing_teams":["ALL"],"warning":str(exc)[:150]}


def _load_full_season(edited, season, nonce, get_logs):
    """Obtain real ESPN season appearances; never call a one-game fallback full."""
    from espn_player_data import full_season_team_boxscores
    catalog,coverage=_safe_catalog(nonce)
    identities={};histories={}
    candidates={}
    for row in (catalog.to_dict("records") if isinstance(catalog,pd.DataFrame) else []):
        key=norm_name(str(row.get("PLAYER_NAME") or ""))
        if key:
            candidates.setdefault(key,[]).append(row)
    names=edited["Zawodnik"].dropna().astype(str).unique().tolist()
    unresolved=[]
    for name in names:
        key=norm_name(name)
        options=candidates.get(key,[])
        if len(options)==1:
            found=options[0]
            identities[key]={
                "id":str(found.get("PLAYER_ID") or ""),
                "team":str(found.get("TEAM_ABBREVIATION") or ""),
                "position":str(found.get("POSITION") or ""),
                "source":"ESPN — sezonowy gamelog",
                "partial":False,"stale":False,
            }
        elif len(options)>1:
            identities[key]={"ambiguous":True}
        else:
            unresolved.append(name)

    def one(name,player):
        key=norm_name(name)
        if not player["id"].isdigit():
            return key,None,"Nieznany identyfikator ESPN."
        try:
            raw,meta=_cached_espn_player_season(
                player["id"],name,player["team"],season,nonce)
            return key,(raw,meta),None
        except (ValueError,KeyError,TypeError,RuntimeError) as exc:
            return key,None,str(exc)[:140]

    with ThreadPoolExecutor(max_workers=5) as pool:
        futures={
            pool.submit(one,name,identities[norm_name(name)]):norm_name(name)
            for name in names
            if norm_name(name) in identities and identities[norm_name(name)].get("id")}
        for completed in as_completed(futures):
            key,bundle,error=completed.result()
            if bundle:
                data,meta=bundle
                if data is not None and not data.empty:
                    histories[key]=data
                    identities[key]["source"]=str(meta.get("source") or "ESPN")
                    identities[key]["stale"]=bool(meta.get("stale"))
                    identities[key]["partial"]=bool(meta.get("partial") or meta.get("stale"))
                    identities[key]["source_games"]=len(data)
                else:
                    identities[key]["partial"]=True
            else:
                identities[key]["partial"]=True
                identities[key]["fetch_error"]=error or "Brak gamelogu ESPN"

    # ESPN's per-player gamelog may be unavailable, malformed or shortened.
    # Reconstruct actual performances from confirmed FINAL team boxscores,
    # grouped and fetched once per match for ALL affected players.
    weak=[key for key,v in identities.items()
          if not v.get("ambiguous") and v.get("id") and
             (v.get("partial") or len(histories.get(key,pd.DataFrame()))<10)]
    if weak:
        try:
            from simulation_sources import historical_espn_results
            finished,notes=historical_espn_results(
                season,refresh=False,lookback_months=6)
            teams={identities[k]["team"] for k in weak if identities[k].get("team")}
            if finished is not None and not finished.empty and teams:
                from espn_player_data import full_season_team_boxscores
                box,box_meta=full_season_team_boxscores(
                    finished,teams,pd.Timestamp.now(tz="UTC"))
                if not box.empty:
                    normalized=normalize_logs(box)
                    for key in weak:
                        ident=identities[key]
                        pid=ident.get("id") or ""
                        selection=normalized[
                            normalized["PLAYER_ID"].astype(str)==str(pid)
                        ].copy() if "PLAYER_ID" in normalized else pd.DataFrame()
                        if selection.empty:
                            continue
                        original=histories.get(key,pd.DataFrame())
                        combined=pd.concat([original,selection],ignore_index=True)
                        combined=combined.drop_duplicates(
                            subset=["GAME_ID","PLAYER_ID"],keep="last")
                        histories[key]=combined.sort_values("GAME_DATE")
                        ident["source"]="ESPN sezon: gamelog + zweryfikowane boxscore"
                        ident["source_games"]=len(histories[key])
                        ident["partial"]=bool(box_meta.get("partial") or notes)
                        ident["fallback_coverage"]=(
                            f'{box_meta.get("success",0)}/'
                            f'{box_meta.get("attempted",0)} meczów drużyn')
        except (ValueError,KeyError,RuntimeError,TypeError):
            pass

    # Last resort only: an explicitly PARTIAL league-wide sample. Never label
    # a single appearance '100% season' without the sample-size warning.
    still_missing=[name for name in names
                   if norm_name(name) not in histories and
                      not identities.get(norm_name(name),{}).get("ambiguous")]
    if still_missing:
        try:
            raw,meta=get_logs()
        except (ValueError,RuntimeError,KeyError,TypeError):
            raw,meta=pd.DataFrame(),{}
        if isinstance(raw,pd.DataFrame) and not raw.empty and "PLAYER_NAME" in raw:
            for name in still_missing:
                key=norm_name(name)
                sample=raw[raw["PLAYER_NAME"].map(norm_name)==key].copy()
                if sample.empty:continue
                sample=sample.sort_values("GAME_DATE")
                team=str(sample.iloc[-1]["TEAM_ABBREVIATION"])
                ids=(sample["PLAYER_ID"].dropna().astype(str).unique().tolist()
                     if "PLAYER_ID" in sample else [])
                identities[key]={
                    "id":ids[0] if len(ids)==1 else None,
                    "team":team,"position":"",
                    "source":str(meta.get("source","NBA/ESPN") if isinstance(meta,dict) else "NBA/ESPN")+
                             " — próbka NIEPEŁNA",
                    "partial":True,"stale":bool(meta.get("stale")) if isinstance(meta,dict) else True,
                }
                histories[key]=sample
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
    st.markdown("#### 📷 BestBets Screenshot Intelligence 2.0")
    st.caption(
        "Obraz służy WYŁĄCZNIE do odczytania zawodników, linii i kursów. "
        "Pobieramy rzeczywiste sezonowe logi ESPN/NBA i boxscore drużyn. "
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
        st.markdown("##### 2. Analiza wszystkich rozpoznanych zdarzeń")
        known=int(result["Występy sezon"].notna().sum())
        with_model=int((result["Status"]=="MODEL TESTOWY").sum())
        good_sample=int((pd.to_numeric(result["Występy sezon"],errors="coerce")>=10).sum())
        one_game=int((pd.to_numeric(result["Występy sezon"],errors="coerce")<=1).sum())
        a,b,c=st.columns(3)
        a.metric("Zdarzenia",len(result))
        b.metric("Historia zawodnika",f"{known}/{len(result)}")
        c.metric("Min. 10 występów",f"{good_sample}/{len(result)}")
        if one_game:
            st.warning(
                f"{one_game} pozycja/pozycje mają tylko 0–1 rozegrany występ w "
                "dostępnej bazie. Wynik 100% z jednego występu NIE jest "
                "wiarygodną oceną szans. Przedstawiamy liczebność próby.")
        if with_model==0:
            st.info("Brak wystarczających danych do prognoz v2. "
                    "Historyczne Over/Under widoczne są tylko dla "
                    "rzeczywiście pobranych występów.")
        tabs=st.tabs(["🏀 Karty zawodników i wykresy",
                      "🛡️ Obrona i jakość danych",
                      "📄 Szczegółowe statystyki"])
        with tabs[0]:
            show_season_cards(
                result,
                st.session_state.get("bb721_histories") or {},
                season,
                st.session_state.get("bb721_events") or {},
                pd.Timestamp.now(tz="UTC"))
        with tabs[1]:
            st.caption("Ocena obrony bazuje na rzeczywistych punktach traconych "
                       "przez CAŁĄ drużynę rywala. Nie zastępuje obrony "
                       "konkretnej pozycji ani potwierdzonej dostępności zawodników.")
            fields=["Zawodnik","Rynek","Przeciwnik",
                    "Występy sezon","Obrona: stracone pkt/mecz",
                    "Obrona: L10 stracone","Korekta PTS (%)",
                    "P(OVER) bez defensywy %",
                    "P(OVER) v2 %","P(UNDER) v2 %",
                    "Źródło statystyk","Uwagi"]
            st.dataframe(result[fields],hide_index=True,use_container_width=True)
            st.warning(
                "Przy braku pełnego sezonowego gamelogu NIE podstawiamy "
                "brakujących wyników. Model v2 jest niekalibrowany. "
                "Zapisane kursy nie dowodzą dodatniej wartości oczekiwanej.")
        with tabs[2]:
            st.caption("Wszystkie sezony/L5/L10/L15 w tabeli — "
                       "do porównywania i ręcznej kontroli OCR.")
            st.dataframe(result,hide_index=True,use_container_width=True)
            st.download_button(
                "Pobierz szczegóły analizy CSV",
                result.to_csv(index=False).encode("utf-8-sig"),
                file_name="bestbets_season_props_v722.csv",
                mime="text/csv",key="bb721_export")
        st.caption("Informacje o wszystkich liniach są historyczne lub "
                   "pochodzą z niekalibrowanych wariantów modelu. "
                   "Sam procent trafień historycznych nie gwarantuje wyniku "
                   "kolejnego spotkania.")

    elif not result.empty:
        st.info("Zmieniono linie lub dzień spotkań. Uruchom analizę ponownie.")
