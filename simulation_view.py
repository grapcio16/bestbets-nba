"""Visual BestBets v6.1 page; Streamlit only, no side effects on import outside app."""
from __future__ import annotations
import html
from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import streamlit as st
from simulation_engine import (TEAM_NAMES,advanced_ratings,completed_team_scores,
    matchup_means,legacy_matchup_means,select_matchup_means,eligible_roster,simulate_game,match_real_odds)
from simulation_sources import historical_espn_results
from teams import standardize_teams
from odds_fetcher import automatic_odds
from team_logos import logo_data_uri, refresh_logos_in_background, cached_official_count
from espn_player_data import matchup_espn_logs
from roster_data import team_roster
from matchup_roster import roster_projection_table
from forecast_quality import quality_report
from simulation_data_audit import matchup_audit, venue_research_candidate
from availability_context import matchup_injuries,player_minutes_brief
from rotation_intelligence import minutes_trends, rotation_report
from simulation_lines import score_line_probabilities, quoted_price_diagnostics, scenario_line_table
from concurrent.futures import ThreadPoolExecutor, as_completed


def esc(x):return html.escape(str(x),quote=True)

def logo_html(code):
    """Always renders a local image, never a hotlinked NBA CDN URL."""
    url = logo_data_uri(code)
    return (f'<img src="{esc(url)}" alt="{esc(TEAM_NAMES.get(code, code))}" '
            'loading="lazy" style="width:64px;height:64px;object-fit:contain" />') if url else '🏀'

@st.cache_data(ttl=60*60,max_entries=5,show_spinner=False)
def build_sims(games,advanced,history,logs,injuries,research_mode=False):
    """Process every upcoming game, returning simulation summaries AND all player means."""
    ratings=advanced_ratings(advanced)
    history_by_team=completed_team_scores(history)
    summary=[];players_by_game={};unavailable=[]
    league_avg={}
    if not advanced.empty:
        for k in ('PACE','DEF_RATING','OFF_RATING'):
            if k in advanced.columns:
                z=pd.to_numeric(advanced[k],errors='coerce').dropna()
                if not z.empty:league_avg[k]=float(z.median())
    for _,row in games.iterrows():
        g=row.to_dict()
        mean=select_matchup_means(g['home'],g['away'],ratings,history_by_team,
                                  research_mode=research_mode)
        if mean is None:
            unavailable.append({'game_id':g.get('game_id'),'game':g['away']+' @ '+g['home'],
                'reason':'Brak NBA advanced i zbyt mało zakończonych meczów ESPN (min. 4 na drużynę).'})
            continue
        try:
            alternative_method=legacy_matchup_means if research_mode else matchup_means
            alternate=alternative_method(g['home'],g['away'],ratings,history_by_team)
            h=eligible_roster(logs,g['home'],g['away'],injuries,ratings,league_avg,asof=g['start_utc'])
            a=eligible_roster(logs,g['away'],g['home'],injuries,ratings,league_avg,asof=g['start_utc'])
            s,pl,_,_=simulate_game(g,mean,h,a)
            s['quality_check']=quality_report(g,mean,alternate,history_by_team)
            summary.append(s);players_by_game[str(g['game_id'])]=pl
        except (ValueError,KeyError,TypeError) as ex:
            unavailable.append({'game_id':g.get('game_id'),'game':g['away']+' @ '+g['home'],'reason':str(ex)})
    return summary,players_by_game,unavailable


def team_form_diagnostics(hist, code, asof=None, games=10):
    """Actual recent team results, never a proxy for player availability or pace."""
    if hist is None or hist.empty:
        return {}
    records=hist.copy()
    records["start_utc"]=pd.to_datetime(records["start_utc"],utc=True,errors="coerce")
    records=records[(records["status_code"]==3)&
                    ((records["home"]==code)|(records["away"]==code))]
    if asof is not None:
        cutoff=pd.to_datetime(asof,utc=True,errors="coerce")
        records=records[records["start_utc"]<cutoff]
    records=records.sort_values("start_utc").tail(games)
    out=[]
    for g in records.to_dict("records"):
        try:
            home=str(g["home"])==code
            scored=float(g["home_score"] if home else g["away_score"])
            conceded=float(g["away_score"] if home else g["home_score"])
            opponent=g["away"] if home else g["home"]
            if min(scored,conceded)<55:
                continue
            out.append((scored,conceded,opponent))
        except (ValueError,KeyError,TypeError):
            continue
    if not out:
        return {}
    recent=out[-5:]
    return {
        "played":len(out),
        "wins_last5":sum(p>allowed for p,allowed,_ in recent),
        "games_last5":len(recent),
        "scored_last5":round(float(np.mean([p for p,_,_ in recent])),1),
        "allowed_last5":round(float(np.mean([a for _,a,_ in recent])),1),
        "opponents_last5":", ".join(o for _,_,o in recent),
    }


def team_scoring_history(hist, code, games=10):
    """Historical points scored, not the simulation's predicted outcome."""
    records=completed_team_scores(hist).get(code, [])
    values=[float(record[1]) for record in sorted(records,key=lambda x:x[0])[-games:]]
    return {'mean':round(float(np.mean(values)),1),'games':len(values)} if values else None


@st.cache_data(ttl=3*3600,max_entries=8,show_spinner=False)
def matchup_players_cached(season, g, hist, advanced, nonce, research_mode=False, cache_revision='v716'):
    """Fetch selected teams ONLY; streamlit and per-event disk cache prevent repeats."""
    selected, source=matchup_espn_logs(hist,g,games_per_team=7)
    if selected.empty:return pd.DataFrame(),source
    from core import normalize_logs
    try:
        logs=normalize_logs(selected)
    except (ValueError,KeyError,TypeError) as exc:
        return pd.DataFrame(),{'source':'ESPN','warning':'Niepełne statystyki zawodników: '+str(exc)[:150]}
    single=pd.DataFrame([g])
    # Only earlier observed minutes; separate context, never a points multiplier.
    trend=minutes_trends(logs,g['start_utc'],g['home'],g['away'])
    extra=dict(source) if isinstance(source,dict) else {'source':str(source)}
    extra['minutes_trends']=trend.to_dict('records')
    # Injury data is deliberately not fetched for EVERY matchup/card.
    # Without a recent confirmed report, availability stays unverified.
    _,per_game,_=build_sims(single,advanced,hist,logs,pd.DataFrame(),research_mode)
    return per_game.get(str(g['game_id']),pd.DataFrame()),extra

@st.cache_data(ttl=12*3600,max_entries=60,show_spinner=False)
def selected_team_roster(code, nonce):
    """Load roster only on game-details interaction, never when listing games."""
    return team_roster(code,refresh=nonce>0)


def matchup_roster_tables(g, player_table, nonce):
    """Load two cached ESPN rosters concurrently after selecting a specific game."""
    rosters={}
    notices={}
    codes=(str(g['away']),str(g['home']))
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures={pool.submit(selected_team_roster,code,nonce):code for code in codes}
        for future in as_completed(futures):
            code=futures[future]
            try:
                rows,metadata=future.result()
                rosters[code]=rows
                notices[code]=str(metadata.get('warning') or '') if metadata.get('stale') else ''
            except Exception as exc:
                notices[code]='Nie udało się pobrać aktualnego składu: '+str(exc)[:130]
    tables={}
    diagnostics={}
    for code in codes:
        tables[code],diagnostics[code]=roster_projection_table(
            rosters.get(code),player_table,code)
    return tables,diagnostics,notices


def local_timezone():
    chosen=st.session_state.get('viewer_tz_override','Automatyczna')
    browser=getattr(st.context,'timezone',None) or 'UTC'
    try:return ZoneInfo(browser if chosen=='Automatyczna' else chosen)
    except (ZoneInfoNotFoundError,KeyError,ValueError):return timezone.utc


def game_card(sim,g,hist):
    h,a=sim['home'],sim['away']
    date=pd.to_datetime(g['start_utc'],utc=True).tz_convert(local_timezone()).strftime('%d.%m.%Y • %H:%M')
    pct_h=float(sim['home_win_pct']);pct_a=float(sim['away_win_pct'])
    # HTML is constructed only from trusted static team names, sanitized dates and numeric simulations.
    st.markdown(f'''<div class="bb-gamecard">
      <div class="bb-gamehead">🏀 {esc(date)} <span>5 000 symulacji</span></div>
      <div class="bb-versus">
        <div>{logo_html(a)}<strong>{esc(TEAM_NAMES.get(a,a))}</strong><small>Goście · średnia z symulacji</small><b>{sim['away_points']:.1f} pkt</b></div>
        <span class="bb-at">VS</span>
        <div>{logo_html(h)}<strong>{esc(TEAM_NAMES.get(h,h))}</strong><small>Gospodarze · średnia z symulacji</small><b>{sim['home_points']:.1f} pkt</b></div>
      </div>
      <div class="bb-winbar"><div style="width:{pct_a:.1f}%;background:#E8AD58"></div><div style="width:{pct_h:.1f}%;background:#62C7AE"></div></div>
      <div class="bb-winlabels"><span>{pct_a:.1f}% • {esc(a)}</span><span>{pct_h:.1f}% • {esc(h)}</span></div>
      <div class="bb-gamefooter">Średnia suma punktów <b>{sim['total_points']:.1f}</b> · Model typuje: <b>{esc(TEAM_NAMES.get(sim['winner'],sim['winner']))}</b></div>
      <div style="font-size:10px;color:#90a4be;margin-top:6px">Procenty = udział zwycięstw w 5 000 symulacji. Duże liczby przy drużynach = prognozowane średnie punkty, a nie aktualny wynik.</div>
    </div>''',unsafe_allow_html=True)
    st.caption('Wariant wyniku tej karty: '+str(sim.get('source','Nieznany'))+
               ' · próbka: '+str(sim.get('sample') or 'zaawansowane metryki drużyn')+
               '. Statystyki nie są skalibrowanymi prawdopodobieństwami.')
    qc=sim.get('quality_check') or {}
    if qc.get('alerts'):
        st.warning('Kontrola prognozy: '+' • '.join(qc['alerts'][:4])+
                   '. To sygnały niepewności, a nie pewne typy.')
    elif qc:
        st.caption('Kontrola modelu: brak dodatkowych alertów jakości danych. '
                   'Nie oznacza to skalibrowanej szansy wygranej.')
    away_hist=team_scoring_history(hist,a)
    home_hist=team_scoring_history(hist,h)
    if away_hist and home_hist:
        st.caption(f"Historyczna średnia zdobytych punktów (ostatnie dostępne mecze): "
            f"{TEAM_NAMES.get(a,a)} {away_hist['mean']:.1f} pkt ({away_hist['games']} meczów) · "
            f"{TEAM_NAMES.get(h,h)} {home_hist['mean']:.1f} pkt ({home_hist['games']} meczów). "
            "To dane historyczne, NIE prognoza.")


@st.dialog('🏀 Szczegóły meczu i statystyki zawodników', width='large')
def show_game_details(sim, g, player_table, advanced, hist, player_meta=None,
                      roster_tables=None, roster_diagnostics=None, roster_notices=None,
                      research_mode=False, injury_table=None, injury_meta=None):
    """One-click modal. Player statistics are the FIRST view, not below the cards."""
    home, away = sim['home'], sim['away']
    st.markdown(f'### {TEAM_NAMES.get(away,away)} — {TEAM_NAMES.get(home,home)}')
    st.caption('5 000 symulacji • model eksperymentalny • nie jest to pewny wynik meczu')
    st.markdown('<div class="bb-versus" style="max-width:560px;margin:0 auto 12px">'
        + f'<div>{logo_html(away)}<strong>{esc(TEAM_NAMES.get(away,away))}</strong></div>'
        + '<span class="bb-at">VS</span>'
        + f'<div>{logo_html(home)}<strong>{esc(TEAM_NAMES.get(home,home))}</strong></div>'
        + '</div>', unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric('Szansa gości', f"{sim['away_win_pct']:.1f}%")
    c1.caption('Udział wygranych gości w symulacji, nie szansa potwierdzona.')
    c2.metric('Szansa gospodarzy', f"{sim['home_win_pct']:.1f}%")
    c2.caption('Udział wygranych gospodarzy w symulacji, nie szansa potwierdzona.')
    c3.metric('Średni wynik', f"{sim['away_points']:.1f} : {sim['home_points']:.1f}")
    c3.caption('Punkty gości : gospodarzy, średnia z 5 000 prób.')
    c4.metric('Średnia suma', f"{sim['total_points']:.1f} pkt")
    c4.caption(f"80% symulacji: {sim['total_p10']}–{sim['total_p90']} pkt.")
    st.caption(f"Źródło modelu: {sim['source']}. {sim.get('warning','')}")
    qc=sim.get('quality_check') or {}
    if qc.get('alternate_available'):
        st.caption('Kontrola wrażliwości — drugi wariant modelu: '
                   f"{qc['alternate_away']:.1f} : {qc['alternate_home']:.1f} "
                   '(goście : gospodarze). '
                   f"Różnica handicapów {qc['margin_disagreement']:.1f} pkt. "
                   'Wariant nie jest gwarantowanie dokładniejszy.')
    if qc.get('alerts'):
        st.warning('Ograniczenia tej prognozy: '+' • '.join(qc['alerts']))
    past_away=team_scoring_history(hist,away)
    past_home=team_scoring_history(hist,home)
    if past_away and past_home:
        aa,hh=st.columns(2)
        aa.metric('Średnia zdobytych pkt — goście (historia)',f"{past_away['mean']:.1f} pkt")
        aa.caption(f"Ostatnie {past_away['games']} rozegranych meczów, bez symulacji")
        hh.metric('Średnia zdobytych pkt — gospodarze (historia)',f"{past_home['mean']:.1f} pkt")
        hh.caption(f"Ostatnie {past_home['games']} rozegranych meczów, bez symulacji")
    with st.expander('📈 Audyt danych: próba 5/10/20, dom/wyjazd, obrona, tempo i zmienność',expanded=False):
        st.caption('Wszystkie liczby wyliczono WYŁĄCZNIE z zakończonych meczów przed datą analizowanego spotkania. '
                   'Używanie większej próby nie gwarantuje dokładniejszej prognozy. '
                   'To informacje badawcze — NIE są dodatkowymi mnożnikami symulacji.')
        report_rows, audit_flags=matchup_audit(hist,g,advanced)
        st.dataframe(report_rows,hide_index=True,use_container_width=True)
        st.caption('Historia 5/10/20 to liczba dostępnych meczów z ostatnich N; '
                   '„U siebie / wyjazd” to liczba rzeczywistych spotkań w miejscu odpowiadającym meczowi. '
                   'Odchylenie sumy = rzeczywista zmienność punktów.')
        if audit_flags:
            st.warning('Ograniczenia danych: '+' • '.join(audit_flags[:5]))
        candidate=venue_research_candidate(hist,g)
        if candidate is not None:
            st.caption('Dodatkowa hipoteza badawcza (bez wpływu na wynik meczu): '
                       f"historyczne splity dom/wyjazd sugerują średnie "
                       f"{candidate['away']:.1f} : {candidate['home']:.1f}. "
                       f"Próba venue: gospodarze {candidate['venue_samples'][0]} / "
                       f"goście {candidate['venue_samples'][1]}. "
                       'Nie jest to skalibrowany ani produkcyjny model.')
        else:
            st.caption('Nie uruchomiono hipotezy dom/wyjazd: '
                       'brak minimum 4 zakończonych spotkań w odpowiednich lokalizacjach dla obu drużyn.')
    from match_context import matchup_schedule_context
    contexts=matchup_schedule_context(hist,g)
    st.markdown('#### Odpoczynek i intensywność terminarza')
    st.caption('Dane oparte na faktycznie zakończonych spotkaniach ESPN. '
               'Daty wg strefy NBA ET; to nie jest pełna analiza podróży. '
               'Liczby te NIE zmieniają na razie symulacji.')
    for side,code in (('away',away),('home',home)):
        ctx=contexts[side]
        if not ctx.get('available'):
            st.caption(TEAM_NAMES.get(code,code)+': '+ctx.get('reason','Brak danych'))
        else:
            st.caption(f"{TEAM_NAMES.get(code,code)}: "
                       f"odpoczynek {ctx['rest_days']} dzień/dni · "
                       f"back-to-back: {'TAK' if ctx['back_to_back'] else 'NIE'} · "
                       f"{ctx['games_in_4_days']} mecz(e) w ciągu 4 dni · "
                       f"ostatnie {ctx['played_last5']} spotkań: "
                       f"{ctx['wins_last5']} wygranych, "
                       f"średnia różnica {ctx['margin_last5']:+.1f} pkt.")
    st.markdown('#### Forma ostatnich meczów — dane rzeczywiste')
    st.caption('Poniższe statystyki są kontekstem, a nie dodatkowym '
               'mnożnikiem prawdopodobieństw. Nie potwierdzają dostępności '
               'zawodników w dniu meczu.')
    ac=advanced_ratings(advanced)
    for code in (away,home):
        form=team_form_diagnostics(hist,code,asof=g.get('start_utc'))
        st.markdown('**'+TEAM_NAMES.get(code,code)+'**')
        if form:
            st.caption(f"Ostatnie {form['games_last5']} meczów: "
                       f"{form['wins_last5']} zwycięstw · "
                       f"zdobyte {form['scored_last5']:.1f} pkt/mecz · "
                       f"stracone {form['allowed_last5']:.1f} pkt/mecz · "
                       f"ry wale: {form['opponents_last5']}".replace('ry wale','rywale'))
        else:
            st.caption('Brak wystarczających zakończonych spotkań.')
        if code in ac:
            v=ac[code]
            st.caption(f"NBA advanced: tempo {v['pace']:.1f} posiadań/48 min · "
                       f"OFF Rating {v['off']:.1f} · DEF Rating {v['def']:.1f}")
        else:
            st.caption('Tempo posiadań, OFF i DEF Rating: brak zweryfikowanych '
                       'danych NBA advanced, nie szacujemy ich z punktów.')
    if player_meta:
        st.caption('Dane zawodników: '+str(player_meta.get('source','ESPN'))+
                   ' · '+str(player_meta.get('coverage','')))
    report,report_meta=matchup_injuries(injury_table,home,away,injury_meta)
    st.markdown('#### Statusy zawodników — raport ESPN')
    if report.empty:
        st.info('Brak rozpoznanych informacji o kontuzjach obu drużyn. '
                'To NIE oznacza, że wszyscy zawodnicy są dostępni.')
    else:
        st.dataframe(report,hide_index=True,use_container_width=True,
                     height=min(290,52+len(report)*36))
    if report_meta.get('stale'):
        st.warning('ESPN: dane kontuzji z nieaktualnej pamięci podręcznej.')
    st.caption(report_meta.get('warning','Statusy wymagają potwierdzenia.'))
    if report.empty:
        st.caption('Dostępność kluczowych zawodników przed meczem pozostaje niepotwierdzona.')


    # Only render the selected section. Stats are immediately visible by default.
    view = st.radio('Pokaż szczegóły',
                     ['👥 Zawodnicy', '🩺 Rotacja i absencje',
                      '🎯 Linie i wrażliwość', '📊 Rozkład punktów',
                      '💹 Kursy bukmacherów'],
                     horizontal=True, key=f"bb61_detail_view_{g['game_id']}")
    if view == '🩺 Rotacja i absencje':
        st.markdown('#### Dostępność i ostatnia rotacja — analiza badawcza')
        st.caption('Rzeczywiste minuty z ostatnich 3/7 występów, '
                   'historyczne minuty modelu, wpisy ESPN i pozycje z katalogu drużyny. '
                   'To nie jest potwierdzony skład przedmeczowy.')
        prior=pd.DataFrame((player_meta or {}).get('minutes_trends') or [])
        details,teams,alerts=rotation_report(
            player_table,report,home,away,rosters=roster_tables,
            trends=prior,injury_meta=report_meta,player_meta=player_meta)
        if not teams.empty:
            for team in (away,home):
                snap=teams[teams['Drużyna']==team].iloc[0]
                st.markdown('**'+TEAM_NAMES.get(team,team)+'**')
                a,b,c=st.columns(3)
                a.metric('Zawodnicy z prognozą minut',int(snap['Zawodnicy z projekcją minut']))
                exposure=snap['Minuty modelu: Out/Doubtful']
                b.metric('Historyczne minuty pod ryzykiem',
                         f"{exposure:.1f}" if pd.notna(exposure) else "Brak danych")
                c.metric('Zmienność rotacji (≥4 min)',
                         int(snap['Zawodnicy z wahaniem minut >=4']))
                if not snap['Dane statusu aktualne']:
                    st.caption('Brak świeżego raportu ESPN dla tego meczu. '
                               'Brak wpisu nie potwierdza dostępności.')
                else:
                    doubt=snap['Minuty modelu: Questionable/DTD']
                    st.caption(f"Minuty zawodników Questionable/Day-to-day "
                               f"w historycznej projekcji: {doubt:.1f}. "
                               'To NIE są minuty na pewno stracone.')
        if details.empty:
            st.info('Nie udało się połączyć historii minut z raportem obu drużyn.')
        else:
            filter_status=st.selectbox(
                'Pokaż zawodników',
                ['Wszyscy','Zgłoszone problemy','Wyraźna zmiana minut'],
                key=f"bb716_rotation_filter_{g['game_id']}")
            visible=details.copy()
            if filter_status=='Zgłoszone problemy':
                visible=visible[visible['Ocena statusu'].isin(
                    ['Out','Doubtful','Questionable','Day-to-day','Probable','Sprzeczne wpisy'])]
            elif filter_status=='Wyraźna zmiana minut':
                visible=visible[pd.to_numeric(
                    visible['Zmiana 3 vs 7'],errors='coerce').abs()>=4]
            if visible.empty:
                st.info('Brak zawodników spełniających filtr w dostępnej próbce.')
            else:
                st.dataframe(visible,hide_index=True,use_container_width=True,
                             height=min(620,60+len(visible)*36))
                st.caption('Zmiana minut = średnia z ostatnich 3 minus średnia z '
                           'maksymalnie 7 wcześniejszych występów. Przy mniej niż '
                           '5 występach nie oceniamy trendu.')
        for note in alerts:
            st.caption('⚠️ '+note)
        st.info('**Model bez zmian:** raport rotacji nie koryguje wyniku ani szans '
                'zwycięstwa. Potrzebna jest niezależna walidacja na historycznych '
                'statusach zapisanych przed meczami.')
        return
    if view == '👥 Zawodnicy':
        st.markdown('#### Forma i przewidywane minuty kluczowych zawodników')
        brief=player_minutes_brief(player_table,home,away,report)
        if brief.empty:
            st.info('Nie udało się potwierdzić wystarczającej historii minut zawodników.')
        else:
            st.dataframe(brief,hide_index=True,use_container_width=True)
            st.caption('Minuty to prognoza na podstawie ostatnich występów, '
                       'nie potwierdzona rotacja ani pierwsza piątka.')
            at_risk=brief[brief['Status kontuzji'].str.contains(
                r'out|doubtful|questionable|inactive|suspended',
                case=False,regex=True,na=False)]
            if not at_risk.empty:
                names=', '.join(at_risk['Zawodnik'].astype(str).head(5))
                st.warning('Uwaga na status zawodników: '+names+
                           '. Minuty i statystyki są szacunkami historycznymi; '
                           'symulacja drużyn NIE koryguje aktualnie wyniku '
                           'o absencje. Sprawdź oficjalny raport przed meczem.')
        st.markdown('#### Zawodnicy w składach i dostępne prognozy')
        st.caption('Katalog ESPN pokazuje zawodników przypisanych do drużyny, NIE oficjalną listę '
                   'aktywnych na ten mecz. Brak historii występów oznacza puste wartości statystyk.')
        player_df = player_table if isinstance(player_table, pd.DataFrame) else pd.DataFrame()
        tables = roster_tables or {}
        diagnostics = roster_diagnostics or {}
        notices = roster_notices or {}
        for code in (away,home):
            st.markdown(f'**{TEAM_NAMES.get(code,code)}**')
            df=tables.get(code)
            details=diagnostics.get(code,{})
            if df is None:
                df=player_df[player_df['Drużyna']==code] if not player_df.empty else pd.DataFrame()
            if details.get('roster_available'):
                st.caption(f"Skład ESPN: {details['roster_count']} zawodników · "
                           f"z prognozą: {details['projected']} · "
                           f"bez dostatecznej historii: {details['missing']}.")
                if details.get('not_on_roster'):
                    st.caption('Pominięto prognozy dla zawodników spoza bieżącego katalogu ESPN: '+
                               str(details['not_on_roster'])+'.')
            if notices.get(code):
                st.warning(str(notices[code]))
            if df.empty:
                st.info('Nie udało się uzyskać zawodników lub wystarczających logów tej drużyny.')
            else:
                st.dataframe(df,hide_index=True,use_container_width=True,
                             height=min(500,52+len(df)*36))
        if player_meta and player_meta.get('warning'):
            st.caption(str(player_meta['warning']))
        st.caption('PTS = punkty • REB = zbiórki • AST = asysty • 3PM = celne trójki. '
                   'Prognozy powstały z dostępnych logów i uproszczonego modelu, '
                   'nie są potwierdzonymi statystykami następnego meczu. '
                   'Status składu nie potwierdza udziału w spotkaniu.')
        return

    # The detailed score distribution and odds comparison are computed ONLY
    # when the user selects that view, keeping the player screen responsive.
    ratings = advanced_ratings(advanced)
    history_by_team = completed_team_scores(hist)
    mean = select_matchup_means(home,away,ratings,history_by_team,
                                research_mode=research_mode)
    if mean is None:
        st.warning('Brak wystarczających danych do ponownego obliczenia rozkładu wyniku.')
        return
    recomputed, _, home_draws, away_draws = simulate_game(g, mean)
    # Never show an odds or score distribution calculated with a different
    # model from the game card. This catches research-toggle/cache drift.
    if (recomputed['home_win_pct'] != sim['home_win_pct'] or
        recomputed['away_win_pct'] != sim['away_win_pct'] or
        abs(recomputed['total_points']-sim['total_points'])>0.11):
        st.error('Niespójność wariantu modelu: szczegóły nie odpowiadają '
                 'prognozie z karty meczu. Odśwież stronę przed analizą.')
        return

    if view == '🎯 Linie i wrażliwość':
        st.markdown('#### Linie bukmachera na dokładnie 5 000 symulowanych wyników')
        st.caption('Wpisz WŁASNĄ linię. Nie pobieramy ani nie zgadujemy kursów. '
                   'Każda liczba procentowa poniżej jest częstością z bieżącego '
                   'modelu 5000 przebiegów, nie skalibrowaną szansą wygranej.')
        kind=st.radio('Rynek do zbadania',
                      ['Suma punktów (Over/Under)',
                       'Handicap gospodarzy'],
                      horizontal=True,key=f"bb719_market_{g['game_id']}")
        is_total=kind.startswith('Suma')
        if is_total:
            raw=st.text_input('Suma punktów — wpisz linię bukmachera',
                              value='',placeholder='np. 228,5',
                              key=f"bb719_total_{g['game_id']}")
        else:
            raw=st.text_input(
                'Handicap gospodarzy '+TEAM_NAMES.get(home,home)+' (ze znakiem)',
                value='',placeholder='np. -6,5 lub +4,5',
                key=f"bb719_spread_{g['game_id']}")
            st.caption('Handicap −6,5 gospodarzy: trzeba wygrać co najmniej 7 pkt. '
                       'Dla gości pokazujemy przeciwną stronę tego samego rynku.')
        if not raw.strip():
            st.info('Wpisz linię z aktualnego kursu bukmachera, aby '
                    'policzyć częstość jej pokrycia w symulacji.')
            return
        try:
            entered=float(raw.replace(',','.').replace(' ',''))
            # The second market is not shown; a neutral reference is used
            # internally only because the shared function returns both markets.
            total_line=entered if is_total else float(sim['total_points'])
            handicap=0.0 if is_total else entered
            sampled=score_line_probabilities(
                home_draws,away_draws,total_line,handicap)
        except (ValueError,TypeError) as exc:
            st.warning('Nieprawidłowa linia: '+str(exc)[:140])
            return
        first=sampled['total_over'] if is_total else sampled['home_cover']
        second=sampled['total_under'] if is_total else sampled['away_cover']
        push=sampled['total_push'] if is_total else sampled['spread_push']
        label_a='Over' if is_total else TEAM_NAMES.get(home,home)+' pokryje'
        label_b='Under' if is_total else TEAM_NAMES.get(away,away)+' pokryje'
        m1,m2,m3=st.columns(3)
        m1.metric(label_a,f'{100*first:.1f}%')
        m2.metric(label_b,f'{100*second:.1f}%')
        m3.metric('Zwrot przy równej linii',f'{100*push:.1f}%')
        st.caption(f'{sampled["n"]} przebiegów · '
                   'całkowite linie mogą zakończyć się zwrotem, '
                   'dlatego OVER + UNDER + ZWROT = 100%. '
                   'Przebiegi współdzielą te same założenia modelowe.')
        if is_total:
            st.caption(f'80% SYMULOWANYCH sum: {sampled["total_p10"]:.0f}–'
                       f'{sampled["total_p90"]:.0f} pkt. '
                       f'Średnia: {sampled["total_mean"]:.1f} pkt.')
        else:
            st.caption('Różnica punktów gospodarze − goście: '
                       f'średnia {sampled["margin_mean"]:+.1f}, '
                       f'80% symulacji {sampled["margin_p10"]:+.0f} '
                       f'do {sampled["margin_p90"]:+.0f}.')
        # Simulation sampling error, NOT the much larger, unmeasured model error.
        sampling_uncertainty=1.96*(max(0.0,first*(1-first))/sampled['n'])**.5
        st.caption(f'Orientacyjny błąd MONTE CARLO dla pierwszej strony: '
                   f'±{100*sampling_uncertainty:.1f} pp (95%, gdyby model był poprawny). '
                   'Nie obejmuje błędu danych, kalibracji, kontuzji i samego modelu.')
        c1,c2=st.columns(2)
        price_one=c1.text_input('Kurs pierwszej strony (opcjonalny)',
            value='',placeholder='np. 1,85',
            key=f"bb719_odds_first_{g['game_id']}")
        price_two=c2.text_input('Kurs drugiej strony (opcjonalny)',
            value='',placeholder='np. 1,91',
            key=f"bb719_odds_second_{g['game_id']}")
        prices=[]
        for label,p,quote in ((label_a,first,price_one),(label_b,second,price_two)):
            try:
                detail=quoted_price_diagnostics(p,push,quote)
                if detail is not None:
                    prices.append({'Strona':label,
                       'Kurs (wpisany ręcznie)':detail['odds'],
                       'Próg rentowności %':round(100*detail['conditional_break_even'],1),
                       'EV modelowe %':round(detail['model_ev_pct'],1)})
            except ValueError as exc:
                st.warning('Kurs '+label+': '+str(exc))
        if prices:
            st.dataframe(pd.DataFrame(prices),hide_index=True,use_container_width=True)
            st.warning('EV jest wyłącznie wynikiem NIEKALIBROWANEGO modelu '
                       'i nie dowodzi rzeczywistej przewagi nad bukmacherem. '
                       'Kursów nie zweryfikowano w czasie rzeczywistym.')
        # Immutable *downloadable* pregame evidence for tomorrow's manual
        # comparison: no persistent user-bet storage or account information.
        evidence=[]
        timestamp=pd.Timestamp.now(tz='UTC')
        start=pd.to_datetime(g['start_utc'],utc=True,errors='coerce')
        for side,p,quote in ((label_a,first,price_one),(label_b,second,price_two)):
            optional=None
            try:
                optional=quoted_price_diagnostics(p,push,quote)
            except ValueError:
                pass
            evidence.append({
                'generated_at_utc':timestamp.isoformat(),
                'tipoff_utc':start.isoformat() if pd.notna(start) else '',
                'pregame':bool(pd.notna(start) and timestamp<start),
                'event_id':str(g['game_id']),
                'away':away,'home':home,
                'model_source':str(sim['source']),
                'model_id':'research_form_v74' if research_mode else 'legacy_v72',
                'n_simulations':sampled['n'],
                'market':'TOTAL' if is_total else 'HOME_HANDICAP',
                'line':entered,'side':side,
                'model_probability_uncalibrated':round(p,4),
                'push_probability':round(push,4),
                'bookmaker_quote_unverified':optional['odds'] if optional else None,
                'break_even_if_quote':round(optional['conditional_break_even'],4) if optional else None,
                'model_ev_pct_uncalibrated':round(optional['model_ev_pct'],2) if optional else None,
            })
        if pd.notna(start) and timestamp>=start:
            st.warning('Mecz rozpoczął się lub minął termin rozpoczęcia. '
                       'Zapis NIE jest dowodem prognozy przedmeczowej.')
        st.download_button(
            '💾 Zapisz analizę linii CSV do jutrzejszego rozliczenia',
            pd.DataFrame(evidence).to_csv(index=False).encode('utf-8-sig'),
            file_name=f"bestbets_line_{str(g['game_id'])}.csv",
            mime='text/csv',key=f"bb719_export_{g['game_id']}")
        st.caption('CSV zawiera datę odczytu, ID meczu, źródło modelu, '
                   'wpisaną linię i procenty przed spotkaniem. '
                   'Nie przechowujemy Twojego kuponu ani danych konta.')
        with st.expander('🔬 Wrażliwość na wybór modelu — porównaj warianty',expanded=False):
            st.caption('Porównanie wyłącznie na zakończonych meczach PRZED '
                       'rozpoczęciem spotkania. Każdy wariant ma własne 5000 prób. '
                       'Modele są skorelowane i NIE są niezależnym konsensusem.')
            if st.button('Przelicz alternatywne modele',
                         key=f"bb719_sensitivity_{g['game_id']}"):
                with st.spinner('Przeliczam warianty historyczne…'):
                    comparisons,interpretation=scenario_line_table(
                        g,hist,advanced,total_line,handicap,sim,
                        home_draws,away_draws)
                st.session_state[f"bb719_comparison_{g['game_id']}"]=(
                    raw,kind,research_mode,str(sim['source']),comparisons,interpretation)
            stored=st.session_state.get(f"bb719_comparison_{g['game_id']}")
            if stored and stored[:4]==(raw,kind,research_mode,str(sim['source'])):
                table,interpretation=stored[4],stored[5]
                cols=(['Wariant','Średnia suma','Suma OVER (%)']
                      if is_total else
                      ['Wariant','Średni handicap','Gospodarze pokryją (%)'])
                st.dataframe(table[cols],hide_index=True,use_container_width=True)
                if interpretation.get('available'):
                    disagreement=(interpretation['total_spread_pp']
                                  if is_total else interpretation['cover_spread_pp'])
                    st.metric('Rozbieżność wariantów',f'{disagreement:.1f} pp',
                              help='Różnica maksimum minus minimum; nie jest to błąd statystyczny ani przedział ufności.')
                st.warning(interpretation['warning'])
            else:
                st.caption('Porównanie uruchamia się wyłącznie po kliknięciu. '
                           'Zmiana linii wymaga ponownego obliczenia.')
        return

    if view == '📊 Rozkład punktów':
        total = home_draws + away_draws
        fig = go.Figure()
        fig.add_trace(go.Histogram(x=total, nbinsx=28, marker_color='#EFC078',
                                   name='Suma punktów', opacity=.91))
        fig.add_vline(x=float(total.mean()), line_dash='dash', line_color='#5AD0BC',
                      annotation_text=f'Średnia: {total.mean():.1f}')
        fig.update_layout(title='Suma punktów — 5 000 symulacji',
                          xaxis_title='Łącznie punktów w meczu',
                          yaxis_title='Liczba symulacji', height=360,
                          paper_bgcolor='rgba(0,0,0,0)',
                          plot_bgcolor='rgba(0,0,0,0)',
                          font_color='#D7E4F2',showlegend=False,
                          margin=dict(l=20,r=20,t=55,b=30))
        st.plotly_chart(fig, use_container_width=True)
        st.caption('Wysokość słupka = ile spośród 5 000 prób dało wynik w tym przedziale. Zielona linia = średnia suma punktów (nie linia bukmachera).')
        return

    st.markdown('#### Kursy bukmacherów na ten mecz')
    try:
        key = str(st.secrets.get('ODDS_API_KEY','')).strip()
    except Exception:
        key = ''
    import os
    key = key or os.getenv('ODDS_API_KEY','').strip()
    status = None
    try:
        odds, _, status = automatic_odds(key)
        if odds is not None and not odds.empty:
            comparison = match_real_odds(odds, g, sim, home_draws, away_draws)
            if not comparison.empty:
                st.dataframe(comparison, hide_index=True, use_container_width=True)
                st.caption('Przewaga (pp) = szansa modelu − (100/kurs). EV (%) = 100 × (szansa modelu × kurs − 1). Dodatnie EV nie potwierdza zysku bez kalibracji modelu.')
            else:
                st.info('Brak opublikowanej oferty na dokładnie ten mecz i rynek.')
        else:
            st.info('Brak aktualnych kursów z podłączonych źródeł. Model nie wymyśla cen.')
    except Exception as exc:
        st.warning('Nie udało się pobrać kursów: '+str(exc)[:180])
    if status and status.get('featured',{}).get('stale'):
        st.warning('Kursy są z nieaktualnej kopii — zweryfikuj ofertę u bukmachera.')
    if not key:
        st.caption('Aby włączyć pełne porównanie, uruchom USTAW_KLUCZ_API.bat i wpisz swój klucz z the-odds-api.com. Nie udostępniaj klucza publicznie.')


def render_simulations(season,nonce,load_schedule,load_dataset,load_logs,load_injuries):
    st.markdown('### 🏀 Symulacje NBA — 5 000 przebiegów dla każdego spotkania')
    st.caption('Karty pokazują 5 000 symulacji wyniku i osobne średnie punktów drużyn. '
               'Po kliknięciu szczegółów automatycznie pobieramy historię graczy WYŁĄCZNIE dwóch wybranych drużyn. '
               'Model jest eksperymentalny.')
    st.markdown('''<div class="bb-panel"><strong>Co pokazujemy?</strong>
    <p>Pełne nazwy drużyn oraz pobrane herby (lub lokalne oznaczenia zastępcze), szansę zwycięstwa obu drużyn, średni przewidywany wynik i łączną sumę punktów. Kliknij przycisk pod dowolnym meczem, aby otworzyć jego wyniki i statystyki zawodników bez przewijania przez pozostałe mecze. Jeśli brakuje danych, model nie wyświetla fikcyjnego wyniku.</p></div>''',unsafe_allow_html=True)
    research_mode=st.toggle(
        'Eksperymentalny model: ważona forma i siła rywali',
        value=False,key='bb74_research_form',
        help='Do badań, nie potwierdzona poprawa: wynik na 131 meczach '
             'poprawił MAE sumy, ale pogorszył skuteczność zwycięzcy.'
    )
    if research_mode:
        st.warning('Tryb badawczy: ważona forma i przybliżona siła przeciwników. '
                   'W testach model miał gorszą trafność zwycięzców niż stary. '
                   'Nie uwzględnia jeszcze potwierdzonych składów i kontuzji.')
    else:
        st.caption('Domyślny model v7.2. Tryb badawczy można włączyć powyżej.')
    with st.expander('🔬 Głębsze dane — ustawienia badawcze',expanded=False):
        extended=st.toggle(
            'Pobierz wcześniejsze miesiące bieżącego sezonu (maksymalnie 6)',
            value=False,key='bb715_older_history',
            help='Domyślnie 3 miesiące; rozszerzenie nie łączy różnych sezonów ani nie zmienia wariantu modelu.')
        if st.button('Spróbuj pobrać NBA Advanced: tempo / OFF / DEF',key='bb715_advanced_refresh'):
            try:
                updated,meta=load_dataset('Drużyny • advanced (pace/def)',season,nonce)
                if updated is None or updated.empty or meta.get('stale'):
                    st.warning('Nie udało się uzyskać aktualnych NBA Advanced. '
                               'Stare dane nie zastąpią bieżących statystyk.')
                else:
                    st.success(f"Pobrano aktualne NBA Advanced ({len(updated)} drużyn). "
                               "Model może je wykorzystać w kolejnych prognozach.")
            except Exception as exc:
                st.warning('NBA Advanced niedostępne z hostingu: '+str(exc)[:160])
        st.caption('NBA Stats bywa blokowane w chmurze. Pobieranie tylko po kliknięciu; '
                   'nie przeliczamy retrospektywnie wcześniej zapisanych prognoz.')
    days=st.select_slider('Pokaż nadchodzące mecze przez',options=[1,3,5,7,10,14],value=1,format_func=lambda d:f'{d} dni')
    try:
        schedule,sm=load_schedule(nonce)
    except Exception as e:
        st.error('Terminarz niedostępny: '+str(e));return
    now=pd.Timestamp.now(tz='UTC')
    games=schedule[(schedule['start_utc']>=now)&(schedule['start_utc']<=now+pd.Timedelta(days=days))&(schedule['status_code']==1)].copy()
    games=games.sort_values('start_utc').drop_duplicates('game_id')
    if games.empty:
        st.info(f'W terminie następnych {days} dni nie ma zaplanowanych spotkań NBA (lub terminarz jest niekompletny).');return
    st.caption(f"Terminarz: {sm.get('source','?')} · {len(games)} spotkań · godziny lokalne użytkownika")
    refresh_logos_in_background()
    st.caption(f'Herby: {cached_official_count()}/30 pobranych i zapisanych lokalnie. Pozostałe drużyny mają dołączone graficzne identyfikatory; źródła ESPN → NBA CDN są sprawdzane automatycznie w tle.')
    # Load team context first. Do not fetch player logs or injuries for every match
    # while the user is only browsing the game cards.
    advanced=pd.DataFrame();hist=pd.DataFrame()
    with st.spinner('Pobieram dane drużyn i zakończone mecze…'):
        warnings=[]
        # Simulation overview must not wait for stats.nba.com (often blocked in cloud).
        # Use previously fetched, labeled NBA advanced metrics if cached; otherwise
        # calculate team expectations from completed ESPN games.
        try:
            from sources import read_cache
            cached_adv,am=read_cache('extended-Drużyny • advanced (pace/def)-'+season,12*3600)
            if cached_adv and not (am and am.get('stale')):
                advanced=standardize_teams(pd.DataFrame(cached_adv))
            elif cached_adv:
                warnings.append('NBA advanced jest nieaktualne: odrzucono przeterminowaną kopię '
                                'i użyto zakończonych spotkań ESPN.')
            else:
                warnings.append('NBA advanced nie jest zapisane lokalnie — użyto danych meczowych ESPN.')
        except Exception as e:
            warnings.append('NBA advanced niedostępne: '+str(e)[:130])
        try:hist,msg=historical_espn_results(season,refresh=nonce>0,
                                                lookback_months=6 if extended else 3)
        except Exception as e:msg='ESPN wyniki: '+str(e)
        if msg:warnings.append(msg)
    for warn in warnings:st.caption('⚠️ '+warn)
    st.caption(f"Historia do symulacji: {len(hist)} zweryfikowanych finałów, "
               f"okno {'maks. 6' if extended else 'maks. 3'} miesięcy bieżącego sezonu. "
               "Ostatnich 12 spotkań drużyny używa model domyślny; "
               "dla starszych meczów rozszerzenie pomaga tylko wtedy, gdy sezon już trwa wystarczająco długo.")
    # Scores are simulated immediately; player estimates are loaded only for
    # the selected game in its details dialog, never across all upcoming games.
    summary,_,missing=build_sims(games,advanced,hist,pd.DataFrame(),pd.DataFrame(),research_mode)
    other=[]
    # Capture BOTH models before tipoff, even if the user viewed only one.
    # The storage key is (ESPN game_id, model_id). Never rewrite a snapshot.
    try:
        from tracker_storage import save,tracker_backend
        other,_,_=build_sims(games,advanced,hist,pd.DataFrame(),pd.DataFrame(),
                             not research_mode)
        active_id='research_form_v74' if research_mode else 'legacy_v72'
        other_id='legacy_v72' if research_mode else 'research_form_v74'
        for record in summary:
            record['model_id']=active_id
        for record in other:
            record['model_id']=other_id
        cfg=tracker_backend()
        result=save(summary+other,season,config=cfg)
        st.caption('Tracker: zapisano '+str(result['saved'])+
                   ' nowych prognoz przed rozpoczęciem meczu '
                   '(modele podstawowy i eksperymentalny osobno). '
                   'Źródło danych: '+cfg['label']+'.')
    except Exception as exc:
        st.warning('Nie udało się zapisać prognoz. Sprawdź konfigurację magazynu danych w ustawieniach serwera.')

    # Make the research toggle objectively observable. A label change alone is
    # not enough: display BOTH baseline and research forecasts and their deltas.
    if summary and other:
        baseline={str(x['game_id']):x for x in (other if research_mode else summary)}
        experimental={str(x['game_id']):x for x in (summary if research_mode else other)}
        compare=[]
        for g in games.to_dict('records'):
            key=str(g['game_id'])
            b=baseline.get(key);r=experimental.get(key)
            if b and r:
                compare.append({
                    'Mecz':g['away']+' @ '+g['home'],
                    'Suma v7.2':b['total_points'],
                    'Suma badawcza':r['total_points'],
                    'Różnica sumy':round(r['total_points']-b['total_points'],1),
                    'P(gospodarze) v7.2':b['home_win_pct'],
                    'P(gospodarze) badawcza':r['home_win_pct'],
                    'Różnica pp':round(r['home_win_pct']-b['home_win_pct'],1),
                })
        if compare:
            cf=pd.DataFrame(compare)
            st.markdown('#### Co zmienia przełącznik eksperymentalnego modelu?')
            st.caption('Aktywny wariant: '+(
                'WAŻONA FORMA + SIŁA RYWALI (badawczy)' if research_mode
                else 'MODEL PODSTAWOWY v7.2')+
                '. Prognozy obu wariantów na TYCH SAMYCH meczach. '
                'Różnice to efekt innych średnich, a nie potwierdzona poprawa.')
            if ((cf['Różnica sumy'].abs()<.05)&
                    (cf['Różnica pp'].abs()<.05)).all():
                st.warning('Oba warianty zwracają te same liczby przy obecnej historii. '
                           'Najczęściej oznacza to brak wystarczających meczów do '
                           'korekty formy lub brak różnicy po zaokrągleniu. '
                           'Przełącznik NIE zapewnia wtedy innego wyniku.')
            else:
                changed=int(((cf['Różnica sumy'].abs()>=.05) |
                             (cf['Różnica pp'].abs()>=.05)).sum())
                st.caption(f'Wariant badawczy zmienia wynik w {changed}/{len(cf)} meczach.')
            with st.expander('Porównaj liczbowe różnice dla każdego meczu',
                             expanded=research_mode):
                st.dataframe(cf,hide_index=True,use_container_width=True)
        else:
            st.info('Nie udało się policzyć dwóch wariantów na tych samych meczach.')
    else:
        st.warning('Porównanie modeli niedostępne z aktualną próbą; '
                   'nie zakładamy, że warianty są zgodne.')
    st.caption('Szybki widok: prognozy drużyn. W szczegółach sprawdzisz własne linie sum i handicapów, porównasz modele oraz obejrzysz statystyki zawodników. Procenty nie są skalibrowane.')
    done={str(s['game_id']):s for s in summary}
    b1,b2,b3=st.columns(3)
    b1.metric('Mecze w terminarzu',len(games),help='Zaplanowane spotkania w wybranym okresie')
    b1.caption('Liczba spotkań z aktualnego terminarza.')
    b2.metric('Pełne symulacje',f'{len(done)} × 5 000',help='Dla każdego spotkania liczono osobno 5000 przebiegów')
    b2.caption('Symulacje bazujące na dostępnych statystykach drużyn.')
    b3.metric('Brak danych',len(missing))
    b3.caption('Mecze bez minimalnych danych; nie generujemy sztucznych prognoz.')
    st.markdown('#### Mecze i przewidywany wynik')
    st.caption('Żółty pasek = szansa gości · zielony = szansa gospodarzy. Wyniki to średnie z symulacji, nie wynik rzeczywisty.')
    for i,(_,g) in enumerate(games.iterrows()):
        sid=str(g['game_id']);sim=done.get(sid)
        if sim:
            game_card(sim,g,hist)
            cbtn, _ = st.columns([3, 1])
            with cbtn:
                if st.button('📊 Szczegóły meczu i statystyki zawodników',
                             key=f'open_sim_{sid}', use_container_width=True, type='primary'):
                    players=pd.DataFrame()
                    player_meta={}
                    with st.spinner('Pobieram ostatnie mecze wyłącznie tych dwóch drużyn…'):
                        try:
                            players,player_meta=matchup_players_cached(season,g.to_dict(),hist,advanced,nonce,
                                                                      research_mode)
                        except Exception as exc:
                            player_meta={'source':'ESPN','warning':'Błąd pobierania: '+str(exc)[:180]}
                    tables,diagnostics,notices=matchup_roster_tables(
                        g.to_dict(),players,nonce)
                    injury_rows=pd.DataFrame()
                    injury_meta={}
                    try:
                        injury_rows,injury_meta=load_injuries(nonce)
                    except Exception:
                        injury_meta={'stale':True}
                    show_game_details(sim,g.to_dict(),players,advanced,hist,player_meta,
                                      tables,diagnostics,notices,research_mode,
                                      injury_rows,injury_meta)
        else:
            a=TEAM_NAMES.get(g['away'],g['away']);h=TEAM_NAMES.get(g['home'],g['home'])
            start=g['start_utc'].tz_convert(local_timezone()).strftime('%d.%m %H:%M')
            st.warning(f'{a} @ {h} · {start} — brak danych do symulacji; meczu nie pominięto w terminarzu.')
    if missing:
        st.caption('Nie wszystkie mecze mogą otrzymać prognozę. Potrzebne są prawdziwe statystyki drużyn, a nie sztuczne domyślne wartości.')
