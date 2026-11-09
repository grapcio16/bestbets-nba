"""On-demand visual intake of bookmaker screenshots (Beta, research use only)."""
from __future__ import annotations

from hashlib import sha256

import pandas as pd
import streamlit as st

from core import STAT_NAMES
from screenshot_import import EDIT_COLUMNS, batch_analyze, read_screenshot


def render_screenshot_calculator(season, get_logs):
    st.markdown("#### 📷 Skaner linii bukmacherskich — BETA")
    st.caption(
        "Jeden screenshot może zawierać wiele pozycji Over/Under. "
        "Lokalny OCR nie wysyła obrazu do zewnętrznego modelu AI. "
        "Obsługa czytelnych tabel PL/EN — inne układy wymagają ręcznych poprawek.")
    st.warning(
        "Przed analizą popraw WSZYSTKIE nazwy, linie i kursy. "
        "OCR potrafi odczytać kurs 1,92 jako 1,52 albo pomylić zawodnika. "
        "Screenshot nie potwierdza aktualności oferty ani terminu meczu.")
    upload=st.file_uploader(
        "Wgraj obraz bukmachera (PNG, JPG, WEBP; maks. 8 MB)",
        type=["png","jpg","jpeg","webp"],key="bb717_screen_upload",
        help="Nie wgrywaj ekranów z danymi osobowymi, saldem ani identyfikatorami konta.")
    market=st.selectbox(
        "Domyślny rynek na screenshotcie",list(STAT_NAMES),
        format_func=lambda k: STAT_NAMES[k],key="bb717_market")
    if "bb717_rows" not in st.session_state:
        st.session_state.bb717_rows=pd.DataFrame(columns=EDIT_COLUMNS)
    if "bb717_result" not in st.session_state:
        st.session_state.bb717_result=pd.DataFrame()
    if upload is not None:
        image_bytes=upload.getvalue()
        digest=sha256(image_bytes).hexdigest()
        if digest!=st.session_state.get("bb717_current_hash"):
            st.session_state.bb717_current_hash=digest
            st.session_state.bb717_rows=pd.DataFrame(columns=EDIT_COLUMNS)
            st.session_state.bb717_result=pd.DataFrame()
            st.session_state.pop("bb717_result_hash",None)
        with st.expander("Podgląd oryginalnego screena",expanded=False):
            st.image(image_bytes,use_container_width=True)
        if st.button("🔎 Odczytaj linie i kursy z obrazu",
                     key="bb717_recognize",type="primary"):
            try:
                frame,meta=read_screenshot(image_bytes,default_market=market)
                st.session_state.bb717_rows=frame
                st.session_state.bb717_result=pd.DataFrame()
                st.session_state["bb717_result_hash"]=None
                st.session_state["bb717_ocr_meta"]=meta
                if frame.empty:
                    st.error(meta.get("warning","Nie rozpoznano żadnej pozycji."))
                else:
                    st.success(f"Rozpoznano {len(frame)} linii. "
                               f"Nieodczytane kursy: {meta['unreadable_odds']}. "
                               "Sprawdź wszystkie komórki poniżej.")
            except (RuntimeError,ValueError) as exc:
                st.error("Nie udało się odczytać screena: "+str(exc))
    else:
        st.caption("Możesz też dodać wiersze ręcznie, bez wgrywania obrazu.")

    st.markdown("##### 1. Zweryfikuj dane — edytowalna tabela")
    st.caption("Jedna pozycja = jeden zawodnik, jedna statystyka i jedna linia. "
               "Kurs OVER/UNDER można uzupełnić osobno; nie wolno mieszać różnych linii.")
    edited=st.data_editor(
        st.session_state.bb717_rows,
        key="bb717_editor",num_rows="dynamic",
        use_container_width=True,hide_index=True,
        column_config={
            "Zawodnik":st.column_config.TextColumn("Zawodnik",required=True),
            "Rynek":st.column_config.SelectboxColumn("Rynek",options=list(STAT_NAMES),required=True),
            "Linia":st.column_config.NumberColumn("Linia",min_value=.5,max_value=150.,step=.5),
            "Kurs OVER":st.column_config.NumberColumn("OVER kurs",min_value=1.01,max_value=15.),
            "Kurs UNDER":st.column_config.NumberColumn("UNDER kurs",min_value=1.01,max_value=15.),
            "Weryfikacja OCR":st.column_config.TextColumn("Status OCR",disabled=True),
        })
    edited=edited.reindex(columns=EDIT_COLUMNS)
    if not edited.empty:
        st.caption(f"Pozycji w edytorze: {len(edited)}. "
                   "Puste kursy i nieznanych zawodników pozostawiamy bez wyliczeń.")
    confirmed=st.checkbox(
        "Sprawdziłem/am nazwy, rynki, linie i kursy z oryginalnym screenem.",
        value=False,key="bb717_verified")
    if st.button(
        "📊 Przelicz wszystkie zweryfikowane pozycje",
        key="bb717_analyze",disabled=not confirmed or edited.empty):
        with st.spinner("Analiza zawodników na podstawie dostępnych występów NBA…"):
            try:
                logs,meta=get_logs()
                if logs is None or logs.empty:
                    st.error("Brak występów NBA do oceny zrzutu.")
                    st.session_state.bb717_result=pd.DataFrame()
                else:
                    st.session_state.bb717_result=batch_analyze(
                        edited,logs,pd.Timestamp.now(tz="UTC"),min_games=10)
                    st.session_state.bb717_result_hash=sha256(
                        edited.to_csv(index=False).encode("utf-8")).hexdigest()
                    st.session_state.bb717_source_meta=str(meta.get("source","Nieznane")) if isinstance(meta,dict) else str(meta)
            except (ValueError,KeyError,TypeError,RuntimeError) as exc:
                st.error("Analiza nie powiodła się: "+str(exc)[:180])
                st.session_state.bb717_result=pd.DataFrame()
    result=st.session_state.bb717_result
    nowhash=sha256(edited.to_csv(index=False).encode("utf-8")).hexdigest()
    if not result.empty and st.session_state.get("bb717_result_hash")==nowhash:
        st.markdown("##### 2. Wyniki zbiorcze — prawdopodobieństwa TESTOWE")
        total=len(result)
        computed=int((result["Status"]=="MODEL TESTOWY").sum())
        missing=total-computed
        x,y,z=st.columns(3)
        x.metric("Zdarzenia",total)
        y.metric("Próba ≥10 występów",computed)
        z.metric("Wstrzymane",missing)
        st.caption(
            "P(OVER) i P(UNDER) są NIEKALIBROWANYMI wynikami starego modelu "
            "statystycznego, nie zweryfikowanymi szansami na wygraną. "
            "Próg = 100/kurs. Porównanie z rynkiem bez marży uwzględnia "
            "tylko dwustronne kursy z tego screena.")
        st.dataframe(result,hide_index=True,use_container_width=True,
                     height=min(680,70+max(1,total)*39))
        st.download_button(
            "Eksportuj sprawdzane pozycje i wyniki CSV",
            result.to_csv(index=False).encode("utf-8-sig"),
            file_name="bestbets_screenshot_batch.csv",
            mime="text/csv",key="bb717_export")
        st.warning(
            "Nie traktuj wyników jako rekomendacji zakładów. "
            "Nie znamy dat spotkań, rzeczywistej dostępności zawodników ani "
            "tego, czy kursy pozostały aktualne. "
            "W przyszłej wersji podłączymy niezależną kalibrację i automatyczną "
            "kontrolę oferty przed rozpoczęciem meczu.")
    elif not result.empty:
        st.info("Dane w tabeli zmieniły się od ostatniej analizy — przelicz je ponownie.")
