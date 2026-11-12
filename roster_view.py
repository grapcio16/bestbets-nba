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


@st.cache_data(ttl=3*3600,max_entries=3,show_spinner=False)
def cached_global_player_catalog(nonce: int = 0):
    from global_player_catalog import build_global_catalog
    return build_global_catalog()


def global_player_selector(nonce: int = 0):
    """Player-first lookup across all available NBA team rosters."""
    try:
        with st.spinner("Ładuję katalog zawodników NBA…"):
            catalog,coverage=cached_global_player_catalog(nonce)
    except Exception as exc:
        st.error("Nie udało się pobrać katalogu zawodników: "+str(exc)[:180])
        return None,None,None,{}
    if catalog.empty:
        st.warning("Nie otrzymano żadnego składu NBA. Kalkulator pozostaje niedostępny.")
        return None,None,None,coverage
    if coverage["missing_teams"]:
        st.warning("Katalog niepełny: "+str(coverage["teams_loaded"])+"/30 drużyn. "
                   "Brak danych: "+", ".join(coverage["missing_teams"])+". "
                   "Nie traktuj brakujących nazwisk jako braku zawodnika w NBA.")
    if coverage["stale_teams"]:
        st.caption("Składy z nieaktualnej kopii: "+", ".join(coverage["stale_teams"]))
    if coverage.get("sparse_teams"):
        st.warning("Częściowe składy ESPN (wymagają dalszej weryfikacji): "+
                   ", ".join(coverage["sparse_teams"]))
    # ESPN IDs distinguish players with identical names; team is determined for user.
    record_by_label={}
    for row in catalog.to_dict("records"):
        label=str(row["PLAYER_NAME"])+" ("+str(row["TEAM_ABBREVIATION"])+")"
        if label in record_by_label:
            label=label+" · ESPN "+str(row["PLAYER_ID"])
        record_by_label[label]=row
    label=st.selectbox("Wyszukaj zawodnika NBA",list(record_by_label),
                       key="bb7_global_calculator_player")
    selected=record_by_label[label]
    st.caption("Drużyna ustalona automatycznie: "+
               TEAM_FULL.get(selected["TEAM_ABBREVIATION"],selected["TEAM_ABBREVIATION"]) +
               " · Katalog: "+str(coverage["players"])+" zawodników, "+
               str(coverage["teams_loaded"])+"/30 drużyn")
    return (str(selected["PLAYER_NAME"]),str(selected["PLAYER_ID"]),
            str(selected["TEAM_ABBREVIATION"]),coverage)


def show_calculator_history_chart(sub, player: str, market: str, line: float,
                                  prediction: float | None = None):
    """Chronological real game results, selected market and optional forecast."""
    if sub is None or sub.empty or market not in sub:
        st.info("Brak rozegranych meczów do wyświetlenia wykresu.")
        return
    last=sub.sort_values("GAME_DATE").tail(20).copy()
    points=pd.to_numeric(last[market],errors="coerce")
    last=last[points.notna()].copy()
    if last.empty:
        st.info("Brak poprawnych wartości wybranej statystyki.")
        return
    xlabels=last["GAME_DATE"].dt.strftime("%d.%m.%Y").tolist()
    values=pd.to_numeric(last[market],errors="coerce").tolist()
    fig=go.Figure()
    fig.add_trace(go.Bar(
        x=xlabels,y=values,marker_color=[
            "#62C7AE" if v>line else "#EFB85C" for v in values],
        text=[f"{v:g}" for v in values],textposition="outside",
        customdata=last["MATCHUP"].fillna("—").tolist(),
        hovertemplate="Mecz: %{customdata}<br>Data: %{x}<br>Wynik: %{y}<extra></extra>",
        name="Rzeczywiste występy"
    ))
    fig.add_hline(y=float(line),line_dash="solid",line_color="#EF8E88",
                  annotation_text=f"Twoja linia: {line:g}",
                  annotation_position="bottom right")
    if prediction is not None:
        fig.add_hline(y=float(prediction),line_dash="dash",line_color="#8ECFF0",
                      annotation_text=f"Prognoza: {prediction:.1f}",
                      annotation_position="top left")
    fig.update_xaxes(type="category",categoryorder="array",categoryarray=xlabels,
                     title="Data spotkania",tickangle=-35)
    fig.update_yaxes(title=STAT_NAMES[market],rangemode="tozero")
    fig.update_layout(
        title=f"{player} — {STAT_NAMES[market]} (ostatnie dostępne mecze)",
        height=430,margin=dict(t=65,b=75,l=20,r=20),
        paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)",
        font_color="#CFDAE7",showlegend=False
    )
    st.plotly_chart(fig,use_container_width=True)
    st.caption("Zielone słupki: wynik powyżej Twojej linii. Żółte: wynik na linii "
               "lub poniżej. Czerwona linia: wybrana linia. "
               "Niebieska linia (jeśli dostępna): niekalibrowana prognoza modelu.")


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
    """Find genuine current-season athlete appearances, never a 1-game proxy.

    ESPN gamelog is primary; verified finalized team boxscores fill gaps and
    older fallback samples remain explicitly marked partial.
    """
    from espn_player_data import detailed_espn_gamelog, full_season_team_boxscores
    from simulation_sources import historical_espn_results
    from season_props import clean_player_season
    frames=[];notes=[];source="ESPN — pełna historia"
    try:
        athlete,meta=detailed_espn_gamelog(player_id,name,team,season)
        if not athlete.empty:
            frames.append(normalize_logs(athlete))
            source=str(meta.get("source") or source)
            if meta.get("partial") or meta.get("stale"):
                notes.append("Indywidualny gamelog ESPN jest potencjalnie niepełny.")
    except (ValueError,KeyError,TypeError,RuntimeError) as exc:
        notes.append("Gamelog ESPN niedostępny: "+str(exc)[:80])
    count=sum(len(frame) for frame in frames)
    if count<10 or notes:
        try:
            finals,warning=historical_espn_results(
                season,lookback_months=6)
            recovered,coverage=full_season_team_boxscores(
                finals,{team},pd.Timestamp.now(tz="UTC"))
            if not recovered.empty:
                indexed=normalize_logs(recovered)
                matched=indexed[indexed["PLAYER_ID"].astype(str)==str(player_id)]
                if not matched.empty:
                    frames.append(matched)
                    source="ESPN gamelog + sezonowe boxscore drużyn"
                    if coverage.get("partial") or warning:
                        notes.append("Nie wszystkie zespołowe boxscore zostały potwierdzone.")
        except (ValueError,KeyError,TypeError,RuntimeError) as exc:
            notes.append("Niepełne wyniki drużyny ESPN: "+str(exc)[:80])
    if not frames:
        try:
            sample,meta=cached_team_logs(team,season,nonce)
            if sample is not None and not sample.empty:
                frames.append(normalize_logs(sample))
                source=str(meta.get("source","ESPN próba częściowa"))
                notes.append("Dostępne tylko wycinkowe wyniki drużyny.")
        except (ValueError,KeyError,TypeError,RuntimeError):
            pass
    if not frames:
        return pd.DataFrame(),{
            "source":"Brak historii","partial":True,"coverage":"0 występów",
            "warning":" ".join(notes)}
    raw=pd.concat(frames,ignore_index=True)
    if "PLAYER_ID" in raw:
        found=raw[raw["PLAYER_ID"].astype(str)==str(player_id)]
    else:
        found=pd.DataFrame()
    if found.empty:
        found=raw[raw["PLAYER_NAME"].map(norm_name)==norm_name(name)]
    unique=found.drop_duplicates(subset=["GAME_ID","PLAYER_ID"],keep="last")
    valid=clean_player_season(
        unique,name,season,pd.Timestamp.now(tz="UTC"),player_id=player_id)
    if len(valid)<5:
        notes.append("Bardzo mała próbka meczów — procenty nie mogą być interpretowane jako przyszła szansa.")
    return valid,{
        "source":source,
        "coverage":f'{len(valid)} rozegranych występów tego sezonu',
        "partial":bool(notes),
        "warning":" ".join(notes),
        "stale":False,
    }


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
