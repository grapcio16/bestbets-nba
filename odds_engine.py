"""Pure odds-market normalization, identical-line comparison and transparent edge math.

No invented prices. No web access, no Streamlit state. No bets are placed.
Market probabilities are experimental and must not be presented as calibrated value.
"""
from __future__ import annotations
from datetime import datetime, timezone
import math
import pandas as pd
from core import norm_name, calc_projection, prop_probability, STAT_NAMES
from quality_engine import walkforward_error, cautious_probability, quality_check
from teams import TEAM_MAP

PROP_MAP = {
 'player_points':'PTS','player_rebounds':'REB','player_assists':'AST',
 'player_threes':'FG3M','player_points_rebounds_assists':'PRA'
}
MARKET_LABELS = {'h2h':'Zwycięzca meczu','totals':'Suma punktów','spreads':'Handicap punktowy',
 'PTS':'Punkty gracza','REB':'Zbiórki gracza','AST':'Asysty gracza','FG3M':'Celne trójki gracza',
 'PRA':'Punkty + zbiórki + asysty'}
LABELS = {
 'Mecz':'Spotkanie NBA i drużyny gospodarz/gość',
 'Początek (PL)':'Początek spotkania według strefy Europe/Warsaw',
 'Rynek':'Rodzaj zdarzenia, np. punkty gracza albo suma punktów meczu',
 'Zawodnik':'Gracz, którego dotyczą kursy i statystyki',
 'Linia':'Warunek zakładu; porównujemy kursy tylko dla identycznej linii',
 'Wariant':'OVER = więcej niż linia; UNDER = mniej niż linia, dla wyniku meczu nazwa drużyny',
 'Bukmacher':'Dostawca oferty kursowej; niekoniecznie dostępny w Polsce',
 'Najwyższy kurs':'Największy kurs dziesiętny dla dokładnie tego samego zdarzenia, linii i wariantu',
 'Najniższy kurs':'Najmniejszy kurs dziesiętny w porównywanej grupie',
 'Liczba firm':'Liczba różnych firm oferujących dany wariant i linię',
 'Różnica kursów (%)':'Procentowa różnica między najwyższym i najniższym kursem: (max/min−1)×100',
 'Aktualizacja (UTC)':'Czas ostatniej aktualizacji rynku podany przez dostawcę API',
 'Prognoza':'Wartość statystyki wyliczona z wcześniejszych meczów, minut i opcjonalnie matchupu',
 'Minuty':'Przewidywany czas gry wyliczony z historii zawodnika; nie jest oficjalny',
 'Szansa modelu (%)':'Szacowane prawdopodobieństwo wyniku według eksperymentalnego modelu; niezweryfikowane',
 'Próg kursu (%)':'Minimalna szansa na trafienie wynikająca z kursu: 100/kurs',
 'Przewaga (pp)':'Szansa modelu minus próg kursu, w punktach procentowych',
 'EV model (%)':'Modelowy zwrot oczekiwany za 1 jednostkę: (p×kurs−1)×100%; zależy od trafności modelu',
 'Próba':'Liczba wcześniejszych występów gracza użytych do prognozy',
 'Status':'Sygnalizuje brak kompletnych danych, małą próbę lub ograniczenia źródeł',
 'Ocena danych':'WSTRZYMAJ = nieaktualny kurs lub mecz już rozpoczęty; OSTROŻNIE = istotne braki i ryzyka; WERYFIKUJ = mniej sygnałów ostrzegawczych. Żaden status nie oznacza polecenia zakładu.',
 'Powody ostrożności':'Powody obniżenia oceny jakości danych i prognozy, np. niepewna kontuzja lub mała próba.',
 'MAE walk-forward':'Średni błąd bezwzględny poprzednich prognoz zawodnika, wyłącznie na późniejszych meczach.',
 'Testy walk-forward':'Liczba sprawdzonych poprzednich prognoz; nigdy nie korzysta z późniejszych wyników.',
 'Szansa ostrożna (%)':'Heurystyczne przyciągnięcie surowego prawdopodobieństwa do 50%. NIE JEST to kalibracja ani zweryfikowana szansa.',
 'EV ostrożne (%)':'Teoretyczne EV policzone z heurystycznej, ostrożniejszej szansy. Nie jest to dowód zyskowności.',
}

def _valid_float(v):
    try:
        x=float(v)
        return x if math.isfinite(x) else None
    except (TypeError,ValueError): return None


def _iso(v):
    try:
        ts=pd.to_datetime(v,utc=True,errors='coerce')
        return ts.isoformat() if not pd.isna(ts) else ''
    except (ValueError,TypeError):return ''


def normalized_offers(featured=None, props=None):
    """Produce one canonical row per bettable outcome, preserving real bookmaker info.

    h2h: line is None. spreads: line is from outcome (not normalized across sides).
    props: player name is the outcome description; market is one of PROP_MAP.
    """
    rows=[]
    if isinstance(featured,pd.DataFrame) and not featured.empty:
        for row in featured.to_dict('records'):
            odds=_valid_float(row.get('odds'))
            market=str(row.get('market') or '').lower()
            if not odds or odds<=1.0 or market not in ('h2h','totals','spreads'):continue
            line=_valid_float(row.get('line'))
            if market!='h2h' and line is None:continue
            selection=str(row.get('name') or '').strip()
            if not selection:continue
            rows.append(dict(event_id=str(row.get('event_id') or ''),
                start_utc=_iso(row.get('start_utc')),home_team=str(row.get('home_team') or ''),
                away_team=str(row.get('away_team') or ''),market=market,player='',
                line=line,selection=selection,bookmaker=str(row.get('bookmaker') or ''),
                bookmaker_key=str(row.get('bookmaker_key') or ''),odds=odds,
                updated=_iso(row.get('market_updated') or row.get('book_updated'))))
    if isinstance(props,pd.DataFrame) and not props.empty:
        for row in props.to_dict('records'):
            market=PROP_MAP.get(str(row.get('market') or ''))
            selection=str(row.get('side') or '').strip().title()
            odds=_valid_float(row.get('odds'))
            line=_valid_float(row.get('line'))
            player=str(row.get('player') or '').strip()
            if not market or selection not in ('Over','Under') or odds is None or odds<=1 or line is None or not player:continue
            rows.append(dict(event_id=str(row.get('event_id') or ''),
                start_utc=_iso(row.get('start_utc')),home_team=str(row.get('home_team') or ''),
                away_team=str(row.get('away_team') or ''),market=market,player=player,
                line=line,selection=selection,bookmaker=str(row.get('bookmaker') or ''),
                bookmaker_key=str(row.get('bookmaker_key') or ''),odds=odds,
                updated=_iso(row.get('updated'))))
    fields=['event_id','start_utc','home_team','away_team','market','player','line',
            'selection','bookmaker','bookmaker_key','odds','updated']
    df=pd.DataFrame(rows,columns=fields)
    if df.empty:return df
    df=df[df['event_id'].ne('') & df['bookmaker_key'].ne('')].copy()
    return df.drop_duplicates(subset=['event_id','market','player','line','selection','bookmaker_key'],keep='last').reset_index(drop=True)


def best_prices(offers):
    """Compare only identical game, market, player, point line and side.

    Returns each best offer and range/count, without grouping different lines together.
    """
    cols=['Mecz','Początek (PL)','Rynek','Zawodnik','Linia','Wariant','Bukmacher',
          'Najwyższy kurs','Najniższy kurs','Liczba firm','Różnica kursów (%)',
          'Aktualizacja (UTC)','event_id','market','player','selection','line','odds']
    if offers is None or offers.empty:return pd.DataFrame(columns=cols)
    group=['event_id','market','player','line','selection']
    rows=[]
    for _,g in offers.groupby(group,dropna=False,sort=False):
        g=g.sort_values(['odds','bookmaker'],ascending=[False,True])
        best=g.iloc[0]; low=float(g['odds'].min()); high=float(best['odds'])
        start=pd.to_datetime(best['start_utc'],utc=True,errors='coerce')
        local=start.tz_convert('Europe/Warsaw').strftime('%d.%m %H:%M') if pd.notna(start) else '—'
        rows.append({'Mecz':f"{best['away_team']} @ {best['home_team']}",
            'Początek (PL)':local,'Rynek':MARKET_LABELS.get(best['market'],best['market']),
            'Zawodnik':best['player'] or '—','Linia':best['line'] if pd.notna(best['line']) else '—',
            'Wariant':best['selection'],'Bukmacher':best['bookmaker'],
            'Najwyższy kurs':round(high,3),'Najniższy kurs':round(low,3),
            'Liczba firm':int(g['bookmaker_key'].nunique()),
            'Różnica kursów (%)':round(100*(high/low-1),2),
            'Aktualizacja (UTC)':best['updated'] or 'brak daty',
            'event_id':best['event_id'],'market':best['market'],
            'player':best['player'],'selection':best['selection'],
            'line':best['line'],'odds':high,'_start_utc':best['start_utc'],'_sort_utc':best['start_utc']})
    out=pd.DataFrame(rows)
    return out.sort_values(['_sort_utc','Rynek','Zawodnik'],kind='stable').drop(columns=['_sort_utc']).reset_index(drop=True)


def edge_metrics(p,odds):
    """Probability edge in percentage points versus break-even and EV in percent.
    These are NOT the same measure; +5 pp does not mean 5% ROI.
    """
    p=float(p); o=float(odds)
    if not (math.isfinite(p) and 0<=p<=1 and math.isfinite(o) and o>1):
        raise ValueError('Nieprawidłowa szansa lub kurs')
    breakeven=1/o
    return {'p_model_pct':round(p*100,2),'p_break_even_pct':round(100*breakeven,2),
            'edge_pp':round(100*(p-breakeven),2),
            'ev_pct':round(100*(p*o-1),2),'fair_odds':round(1/p,3) if p else None}


def player_edges(best,logs,injuries=None,team_context=None,averages=None, now=None):
    """Use player's NBA game logs, only on player props for their currently-listed team.

    Do not rank missing-data or out players.  A positive number is uncalibrated.
    Integer lines can push and are excluded: binary win/loss formula is insufficient.
    """
    extra=['Prognoza','Minuty','Szansa modelu (%)','Próg kursu (%)',
           'Przewaga (pp)','EV model (%)','Próba','Status','Ocena danych','Powody ostrożności',
           'MAE walk-forward','Testy walk-forward','Szansa ostrożna (%)','EV ostrożne (%)']
    if best is None or best.empty or logs is None or logs.empty:
        return pd.DataFrame(columns=list(best.columns if best is not None else [])+extra)
    d=best[best['market'].isin(STAT_NAMES) & best['player'].notna()].copy()
    if d.empty:return pd.DataFrame(columns=list(best.columns)+extra)
    hist_by_name={norm_name(n):g.sort_values('GAME_DATE') for n,g in logs.groupby('PLAYER_NAME')}
    injury_map={}
    if isinstance(injuries,pd.DataFrame) and not injuries.empty:
        injury_map={norm_name(r['player']):str(r.get('status','')) for _,r in injuries.iterrows()}
    projections={};diagnostics={};rows=[]
    for r in d.to_dict('records'):
        hist=hist_by_name.get(norm_name(r['player']))
        if hist is None or len(hist)<5:continue
        status=injury_map.get(norm_name(r['player']),'Brak wpisu ESPN')
        if any(x in status.lower() for x in ('out','inactive','suspended','injured reserve')):continue
        abbr=str(hist.iloc[-1]['TEAM_ABBREVIATION'])
        home=TEAM_MAP.get(r['Mecz'].split(' @ ')[-1],'')
        away=TEAM_MAP.get(r['Mecz'].split(' @ ')[0],'')
        # Avoid matching props to traded player's old team or unrelated game.
        if home and away and abbr not in (home,away):continue
        opponent=away if abbr==home else home
        line=_valid_float(r['line'])
        if line is None or abs(line-round(line))<1e-6:continue
        key=(norm_name(r['player']),r['market'],opponent)
        if key not in projections:
            try:projections[key]=calc_projection(hist,r['market'],opponent,team_context,averages)
            except (ValueError,KeyError):continue
        p=projections[key]
        side=r['selection'].upper()
        if side not in ('OVER','UNDER'):continue
        chance=prop_probability(p,line,side)
        m=edge_metrics(chance,r['odds'])
        quality_key=(norm_name(r['player']),r['market'])
        if quality_key not in diagnostics:
            diagnostics[quality_key]=walkforward_error(hist,r['market'])
        qc=quality_check(hist,r['market'],status,r.get('Aktualizacja (UTC)'),
                         r.get('_start_utc',r.get('start_utc','')),now=now,diag=diagnostics[quality_key])
        stress=cautious_probability(chance,p['sample_size'])
        rows.append({**r,'Prognoza':p['prediction'],'Minuty':p['estimated_minutes'],
            'Szansa modelu (%)':m['p_model_pct'],'Próg kursu (%)':m['p_break_even_pct'],
            'Przewaga (pp)':m['edge_pp'],'EV model (%)':m['ev_pct'],
            'Próba':p['sample_size'],'Status':status+' · model NIEKALIBROWANY',
            'Ocena danych':qc['level'],
            'Powody ostrożności':'; '.join(qc['flags']) if qc['flags'] else 'Brak podstawowych flag',
            'MAE walk-forward':qc['diagnostics']['mae'],
            'Testy walk-forward':qc['diagnostics']['n'],
            'Szansa ostrożna (%)':round(100*stress,2),
            'EV ostrożne (%)':round(100*(stress*float(r['odds'])-1),2),
            '_quality_rank':qc['rank']})
    if not rows:return pd.DataFrame(columns=list(best.columns)+extra)
    # Sorting by DATA QUALITY rather than the biggest unverified probability edge.
    return (pd.DataFrame(rows).sort_values(['_quality_rank','EV ostrożne (%)'],
                ascending=[True,False]).drop(columns=['_quality_rank']).reset_index(drop=True))


def legend_for(columns):
    return [(c,LABELS[c]) for c in columns if c in LABELS]
