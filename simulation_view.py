"""Visual BestBets v6.1 page; Streamlit only, no side effects on import outside app."""
from __future__ import annotations
import html
from datetime import datetime, timezone
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import streamlit as st
from simulation_engine import (TEAM_NAMES,advanced_ratings,completed_team_scores,
    matchup_means,legacy_matchup_means,eligible_roster,simulate_game,match_real_odds)
from simulation_sources import historical_espn_results
from teams import standardize_teams
from odds_fetcher import automatic_odds
from team_logos import logo_data_uri, refresh_logos_in_background, cached_official_count
from espn_player_data import matchup_espn_logs
from roster_data import team_roster
from matchup_roster import roster_projection_table
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
        method=matchup_means if research_mode else legacy_matchup_means
        mean=method(g['home'],g['away'],ratings,history_by_team)
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
def matchup_players_cached(season, g, hist, advanced, nonce):
    """Fetch selected teams ONLY; streamlit and per-event disk cache prevent repeats."""
    selected, source=matchup_espn_logs(hist,g,games_per_team=7)
    if selected.empty:return pd.DataFrame(),source
    from core import normalize_logs
    try:
        logs=normalize_logs(selected)
    except (ValueError,KeyError,TypeError) as exc:
        return pd.DataFrame(),{'source':'ESPN','warning':'Niepełne statystyki zawodników: '+str(exc)[:150]}
    single=pd.DataFrame([g])
    # Injury data is deliberately not fetched for EVERY matchup/card.
    # Without a recent confirmed report, availability stays unverified.
    _,per_game,_=build_sims(single,advanced,hist,logs,pd.DataFrame())
    return per_game.get(str(g['game_id']),pd.DataFrame()),source


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


def game_card(sim,g,hist):
    h,a=sim['home'],sim['away']
    date=pd.to_datetime(g['start_utc'],utc=True).tz_convert('Europe/Warsaw').strftime('%d.%m.%Y • %H:%M')
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
    away_hist=team_scoring_history(hist,a)
    home_hist=team_scoring_history(hist,h)
    if away_hist and home_hist:
        st.caption(f"Historyczna średnia zdobytych punktów (ostatnie dostępne mecze): "
            f"{TEAM_NAMES.get(a,a)} {away_hist['mean']:.1f} pkt ({away_hist['games']} meczów) · "
            f"{TEAM_NAMES.get(h,h)} {home_hist['mean']:.1f} pkt ({home_hist['games']} meczów). "
            "To dane historyczne, NIE prognoza.")


@st.dialog('🏀 Szczegóły meczu i statystyki zawodników', width='large')
def show_game_details(sim, g, player_table, advanced, hist, player_meta=None,
                      roster_tables=None, roster_diagnostics=None, roster_notices=None):
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
    past_away=team_scoring_history(hist,away)
    past_home=team_scoring_history(hist,home)
    if past_away and past_home:
        aa,hh=st.columns(2)
        aa.metric('Średnia zdobytych pkt — goście (historia)',f"{past_away['mean']:.1f} pkt")
        aa.caption(f"Ostatnie {past_away['games']} rozegranych meczów, bez symulacji")
        hh.metric('Średnia zdobytych pkt — gospodarze (historia)',f"{past_home['mean']:.1f} pkt")
        hh.caption(f"Ostatnie {past_home['games']} rozegranych meczów, bez symulacji")
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

    # Only render the selected section. Stats are immediately visible by default.
    view = st.radio('Pokaż szczegóły',
                    ['👥 Zawodnicy', '📊 Rozkład punktów', '💹 Kursy bukmacherów'],
                    horizontal=True, key=f"bb61_detail_view_{g['game_id']}")
    if view == '👥 Zawodnicy':
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
    st.caption(f"Terminarz: {sm.get('source','?')} · {len(games)} spotkań · godziny w Polsce")
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
            if cached_adv:
                advanced=standardize_teams(pd.DataFrame(cached_adv))
                if am and am.get('stale'):
                    warnings.append('NBA advanced: użyto starszej zapisanej kopii.')
            else:
                warnings.append('NBA advanced nie jest zapisane lokalnie — użyto danych meczowych ESPN.')
        except Exception as e:
            warnings.append('NBA advanced niedostępne: '+str(e)[:130])
        try:hist,msg=historical_espn_results(season,refresh=nonce>0)
        except Exception as e:msg='ESPN wyniki: '+str(e)
        if msg:warnings.append(msg)
    for warn in warnings:st.caption('⚠️ '+warn)
    # Scores are simulated immediately; player estimates are loaded only for
    # the selected game in its details dialog, never across all upcoming games.
    summary,_,missing=build_sims(games,advanced,hist,pd.DataFrame(),pd.DataFrame(),research_mode)
    # Freeze predictions at first observed pregame run; never rewrite them.
    # Persistence is local only: may be erased by Streamlit Cloud redeploys.
    try:
        from pathlib import Path
        from performance_tracker import store_forecasts
        archive=Path(__file__).resolve().parent/'data'/'pregame_forecasts.sqlite3'
        result=store_forecasts(archive,season,summary)
        st.caption('Tracker: zapisano '+str(result['saved'])+
                   ' nowych prognoz przed pierwszym gwizdkiem. '
                   'Baza lokalna — po restarcie hostingu wpisy mogą zniknąć.')
    except Exception as exc:
        st.warning('Tracker nie mógł zapisać prognoz: '+str(exc)[:145])

    st.caption('Szybki widok: mecze i wyniki drużyn. Statystyki zawodników pobierane są automatycznie po kliknięciu szczegółów wybranego meczu.')
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
                            players,player_meta=matchup_players_cached(season,g.to_dict(),hist,advanced,nonce)
                        except Exception as exc:
                            player_meta={'source':'ESPN','warning':'Błąd pobierania: '+str(exc)[:180]}
                    tables,diagnostics,notices=matchup_roster_tables(
                        g.to_dict(),players,nonce)
                    show_game_details(sim,g.to_dict(),players,advanced,hist,player_meta,
                                      tables,diagnostics,notices)
        else:
            a=TEAM_NAMES.get(g['away'],g['away']);h=TEAM_NAMES.get(g['home'],g['home'])
            start=g['start_utc'].tz_convert('Europe/Warsaw').strftime('%d.%m %H:%M')
            st.warning(f'{a} @ {h} · {start} — brak danych do symulacji; meczu nie pominięto w terminarzu.')
    if missing:
        st.caption('Nie wszystkie mecze mogą otrzymać prognozę. Potrzebne są prawdziwe statystyki drużyn, a nie sztuczne domyślne wartości.')
