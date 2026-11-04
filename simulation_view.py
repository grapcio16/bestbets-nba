"""Visual BestBets v6.1 page; Streamlit only, no side effects on import outside app."""
from __future__ import annotations
import html
from datetime import datetime, timezone
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import streamlit as st
from simulation_engine import (TEAM_NAMES,advanced_ratings,completed_team_scores,
    matchup_means,eligible_roster,simulate_game,match_real_odds)
from simulation_sources import historical_espn_results
from teams import standardize_teams
from odds_fetcher import automatic_odds
from team_logos import logo_data_uri, refresh_logos_in_background, cached_official_count


def esc(x):return html.escape(str(x),quote=True)

def logo_html(code):
    """Always renders a local image, never a hotlinked NBA CDN URL."""
    url = logo_data_uri(code)
    return (f'<img src="{esc(url)}" alt="{esc(TEAM_NAMES.get(code, code))}" '
            'loading="lazy" style="width:64px;height:64px;object-fit:contain" />') if url else '🏀'

@st.cache_data(ttl=30*60,show_spinner=False)
def build_sims(games,advanced,history,logs,injuries):
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
        mean=matchup_means(g['home'],g['away'],ratings,history_by_team)
        if mean is None:
            unavailable.append({'game_id':g.get('game_id'),'game':g['away']+' @ '+g['home'],
                'reason':'Brak NBA advanced i zbyt mało zakończonych meczów ESPN (min. 4 na drużynę).'})
            continue
        try:
            h=eligible_roster(logs,g['home'],g['away'],injuries,ratings,league_avg,asof=g['start_utc'])
            a=eligible_roster(logs,g['away'],g['home'],injuries,ratings,league_avg,asof=g['start_utc'])
            s,pl,_,_=simulate_game(g,mean,h,a)
            summary.append(s);players_by_game[str(g['game_id'])]=pl
        except (ValueError,KeyError,TypeError) as ex:
            unavailable.append({'game_id':g.get('game_id'),'game':g['away']+' @ '+g['home'],'reason':str(ex)})
    return summary,players_by_game,unavailable


def game_card(sim,g):
    h,a=sim['home'],sim['away']
    date=pd.to_datetime(g['start_utc'],utc=True).tz_convert('Europe/Warsaw').strftime('%d.%m.%Y • %H:%M')
    pct_h=float(sim['home_win_pct']);pct_a=float(sim['away_win_pct'])
    # HTML is constructed only from trusted static team names, sanitized dates and numeric simulations.
    st.markdown(f'''<div class="bb-gamecard">
      <div class="bb-gamehead">🏀 {esc(date)} <span>5 000 symulacji</span></div>
      <div class="bb-versus">
        <div>{logo_html(a)}<strong>{esc(TEAM_NAMES.get(a,a))}</strong><small>Goście</small><b>{sim['away_points']:.1f}</b></div>
        <span class="bb-at">VS</span>
        <div>{logo_html(h)}<strong>{esc(TEAM_NAMES.get(h,h))}</strong><small>Gospodarze</small><b>{sim['home_points']:.1f}</b></div>
      </div>
      <div class="bb-winbar"><div style="width:{pct_a:.1f}%;background:#E8AD58"></div><div style="width:{pct_h:.1f}%;background:#62C7AE"></div></div>
      <div class="bb-winlabels"><span>{pct_a:.1f}% • {esc(a)}</span><span>{pct_h:.1f}% • {esc(h)}</span></div>
      <div class="bb-gamefooter">Średnia suma punktów <b>{sim['total_points']:.1f}</b> · Model typuje: <b>{esc(TEAM_NAMES.get(sim['winner'],sim['winner']))}</b></div>
      <div style="font-size:10px;color:#90a4be;margin-top:6px">Procenty = udział zwycięstw w 5 000 symulacji. Duże liczby przy drużynach = prognozowane średnie punkty, a nie aktualny wynik.</div>
    </div>''',unsafe_allow_html=True)


@st.dialog('🏀 Szczegóły meczu i statystyki zawodników', width='large')
def show_game_details(sim, g, player_table, advanced, hist):
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

    # Only render the selected section. Stats are immediately visible by default.
    view = st.radio('Pokaż szczegóły',
                    ['👥 Zawodnicy', '📊 Rozkład punktów', '💹 Kursy bukmacherów'],
                    horizontal=True, key=f"bb61_detail_view_{g['game_id']}")
    if view == '👥 Zawodnicy':
        st.markdown('#### Średnie statystyki zawodników z 5 000 symulacji')
        player_df = player_table if isinstance(player_table, pd.DataFrame) else pd.DataFrame()
        if player_df.empty:
            st.info('Brak pełnych logów zawodników dla tego meczu. Model nie generuje wymyślonych statystyk.')
        else:
            for code in (away, home):
                df = player_df[player_df['Drużyna'] == code]
                st.markdown(f'**{TEAM_NAMES.get(code,code)}**')
                if df.empty:
                    st.info('Brak wystarczających logów zawodników tej drużyny.')
                else:
                    st.dataframe(df, hide_index=True, use_container_width=True,
                                 height=min(450, 52+len(df)*36))
        st.caption('PTS = punkty • REB = zbiórki • AST = asysty • 3PM = trafione trójki • Minuty = prognozowany czas gry. Wyniki indywidualne pochodzą z modelu i dostępnych logów, nie z oficjalnego składu przedmeczowego.')
        return

    # The detailed score distribution and odds comparison are computed ONLY
    # when the user selects that view, keeping the player screen responsive.
    ratings = advanced_ratings(advanced)
    history_by_team = completed_team_scores(hist)
    mean = matchup_means(home, away, ratings, history_by_team)
    if mean is None:
        st.warning('Brak wystarczających danych do ponownego obliczenia rozkładu wyniku.')
        return
    _, _, home_draws, away_draws = simulate_game(g, mean)

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
    st.markdown('### 🏀 Symulacje NBA — 5 000 meczów dla każdego spotkania')
    st.caption('Każdy widoczny mecz jest symulowany dokładnie 5 000 razy. To eksperymentalny model, nie oficjalne przewidywania NBA ani skalibrowane prawdopodobieństwa zakładów.')
    st.markdown('''<div class="bb-panel"><strong>Co pokazujemy?</strong>
    <p>Pełne nazwy drużyn oraz pobrane herby (lub lokalne oznaczenia zastępcze), szansę zwycięstwa obu drużyn, średni przewidywany wynik i łączną sumę punktów. Kliknij przycisk pod dowolnym meczem, aby otworzyć jego wyniki i statystyki zawodników bez przewijania przez pozostałe mecze. Jeśli brakuje danych, model nie wyświetla fikcyjnego wyniku.</p></div>''',unsafe_allow_html=True)
    days=st.select_slider('Pokaż nadchodzące mecze przez',options=[1,3,5,7,10,14],value=7,format_func=lambda d:f'{d} dni')
    try:
        schedule,sm=load_schedule(nonce)
    except Exception as e:
        st.error('Terminarz niedostępny: '+str(e));return
    now=pd.Timestamp.now(tz='UTC')
    games=schedule[(schedule['start_utc']>=now)&(schedule['start_utc']<=now+pd.Timedelta(days=days))&(schedule['status_code']==1)].copy()
    games=games.sort_values('start_utc').drop_duplicates('game_id')
    if games.empty:
        st.info(f'W terminie następnych {days} dni nie ma zaplanowanych spotkań NBA (lub terminarz jest niekompletny).');return
    st.caption(f"Terminarz: {sm.get('source','?')} · {len(games)} spotkań · godziny w Polsce")
    refresh_logos_in_background()
    st.caption(f'Herby: {cached_official_count()}/30 pobranych i zapisanych lokalnie. Pozostałe drużyny mają dołączone graficzne identyfikatory; źródła ESPN → NBA CDN są sprawdzane automatycznie w tle.')
    advanced=pd.DataFrame();hist=pd.DataFrame();logs=pd.DataFrame();inj=pd.DataFrame()
    with st.spinner('Pobieram statystyki drużyn, historię meczów i dostępne logi…'):
        warnings=[]
        try:
            advanced,am=load_dataset('Drużyny • advanced (pace/def)',season,nonce)
            advanced=standardize_teams(advanced)
            if am.get('stale'):warnings.append('NBA advanced — użyto starszej kopii danych.')
        except Exception as e:warnings.append('Brak NBA advanced: '+str(e)[:150])
        try:hist,msg=historical_espn_results(season,refresh=nonce>0)
        except Exception as e:msg='ESPN wyniki: '+str(e)
        if msg:warnings.append(msg)
        try:
            raw,lm=load_logs(season,nonce)
            from core import normalize_logs
            logs=normalize_logs(raw)
            if lm.get('coverage'):warnings.append('Logi NBA CDN są częściowe — statystyki zawodników mogą być niekompletne.')
        except Exception as e:warnings.append('Brak logów zawodników: '+str(e)[:150])
        try:inj,im=load_injuries(nonce)
        except Exception as e:warnings.append('Brak raportu ESPN: '+str(e)[:150])
    for warn in warnings:st.caption('⚠️ '+warn)
    summary,player_tables,missing=build_sims(games,advanced,hist,logs,inj)
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
            game_card(sim,g)
            cbtn, _ = st.columns([3, 1])
            with cbtn:
                if st.button('📊 Szczegóły meczu i statystyki zawodników',
                             key=f'open_sim_{sid}', use_container_width=True, type='primary'):
                    show_game_details(sim,g.to_dict(),player_tables.get(sid),advanced,hist)
        else:
            a=TEAM_NAMES.get(g['away'],g['away']);h=TEAM_NAMES.get(g['home'],g['home'])
            start=g['start_utc'].tz_convert('Europe/Warsaw').strftime('%d.%m %H:%M')
            st.warning(f'{a} @ {h} · {start} — brak danych do symulacji; meczu nie pominięto w terminarzu.')
    if missing:
        st.caption('Nie wszystkie mecze mogą otrzymać prognozę. Potrzebne są prawdziwe statystyki drużyn, a nie sztuczne domyślne wartości.')
