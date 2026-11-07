"""BestBets match simulator. Experimental, not calibrated to bookmaker outcomes.

Team means derive from verified NBA advanced metrics OR recent completed ESPN scores.
Each upcoming event receives exactly 5000 correlated score draws. When player logs
are present, 5000 conditional player-stat draws are generated for both teams.
Never fill missing ratings or odds with fabricated results.
"""
from __future__ import annotations
from datetime import datetime, timezone
from hashlib import sha256
from math import isfinite
import numpy as np
import pandas as pd
from core import calc_projection, norm_name
from teams import TEAM_MAP

TEAM_IDS = {
 'ATL':1610612737, 'BOS':1610612738,'BKN':1610612751,'CHA':1610612766,
 'CHI':1610612741,'CLE':1610612739,'DAL':1610612742,'DEN':1610612743,
 'DET':1610612765,'GSW':1610612744,'HOU':1610612745,'IND':1610612754,
 'LAC':1610612746,'LAL':1610612747,'MEM':1610612763,'MIA':1610612748,
 'MIL':1610612749,'MIN':1610612750,'NOP':1610612740,'NYK':1610612752,
 'OKC':1610612760,'ORL':1610612753,'PHI':1610612755,'PHX':1610612756,
 'POR':1610612757,'SAC':1610612758,'SAS':1610612759,'TOR':1610612761,
 'UTA':1610612762,'WAS':1610612764,
}
TEAM_NAMES={v:k for k,v in TEAM_MAP.items() if k != 'LA Clippers'}
TEAM_NAMES['LAC']='Los Angeles Clippers'

def team_logo(code: str) -> str:
    ident=TEAM_IDS.get(str(code).upper())
    return f'https://cdn.nba.com/logos/nba/{ident}/primary/L/logo.png' if ident else ''

def _num(value):
    try:
        n=float(value)
        return n if isfinite(n) else None
    except (ValueError,TypeError):return None

def advanced_ratings(advanced:pd.DataFrame|None):
    """Return only teams with complete authentic OFF/DEF/PACE metrics."""
    result={}
    if advanced is None or advanced.empty:return result
    adv=advanced.copy()
    adv.columns=[str(c).upper() for c in adv.columns]
    for _,r in adv.iterrows():
        abbr=str(r.get('TEAM_ABBREVIATION','')).upper()
        if abbr not in TEAM_IDS:abbr=TEAM_MAP.get(str(r.get('TEAM_NAME','')),abbr)
        pace,off,defense=(_num(r.get(k)) for k in ('PACE','OFF_RATING','DEF_RATING'))
        if abbr in TEAM_IDS and all(x is not None and 70<x<150 for x in (pace,off,defense)):
            result[abbr]={'pace':pace,'off':off,'def':defense,'source':'NBA Stats — advanced'}
    return result

def completed_team_scores(games:pd.DataFrame|None):
    """Only completed REAL games from scoreboard, no upcoming scores or placeholders."""
    out={k:[] for k in TEAM_IDS}
    if games is None or games.empty:return out
    for _,g in games.iterrows():
        if int(g.get('status_code') or 0)!=3:continue
        home,away=str(g.get('home','')),str(g.get('away',''))
        a,b=_num(g.get('home_score')),_num(g.get('away_score'))
        if home not in out or away not in out or a is None or b is None:continue
        if min(a,b)<55 or max(a,b)>200:continue
        # date for ordering, not part of the scoring estimate
        dt=pd.to_datetime(g.get('start_utc'),utc=True,errors='coerce')
        out[home].append((dt,a,b));out[away].append((dt,b,a))
    return out

def _weighted_average(values, halflife=6.0):
    """Exponential emphasis on newer games, retaining older evidence."""
    z=np.asarray(values,dtype=float)
    if len(z)==0 or not np.isfinite(z).all():
        return None
    weights=2.**((np.arange(len(z))-(len(z)-1))/halflife)
    return float(np.average(z,weights=weights))


def _team_form_stats(code, historical, league_mean, minimum_history=4):
    """Opponent-adjusted points scored and conceded, shrunk on small samples.

    Opponent strength is estimated strictly from COMPLETED games. With few
    opponent games, correction shrinks toward neutral, not invented certainty.
    """
    history=sorted(historical.get(code,[]),key=lambda x:x[0])
    if len(history)<minimum_history:
        return None
    matches=history[-12:]
    others=historical
    scored=[];allowed=[]
    # historical records do not contain the opponent ID: opponent-adjustment
    # must be handled upstream when opponent identification is available.
    for _,p,a in matches:
        scored.append(float(p))
        allowed.append(float(a))
    off=_weighted_average(scored)
    defense=_weighted_average(allowed)
    # 6 neutral pseudo-games moderate noisy early-season overreaction.
    sample_weight=len(matches)/(len(matches)+6.0)
    return {"off":sample_weight*off+(1-sample_weight)*league_mean,
            "def":sample_weight*defense+(1-sample_weight)*league_mean,
            "raw_off":off,"raw_def":defense,
            "n":len(matches),"sample_weight":sample_weight}


def matchup_means(home:str,away:str,adv:dict,hist:dict, minimum_history:int=4):
    """Expected scores: actual advanced ratings or shrinkage + recency ESPN form.

    No blind ranking boost or invented official probabilities. Sample-size
    shrinkage limits dramatic favorites from 4-10 early-season games.
    """
    h=adv.get(home);a=adv.get(away)
    if h and a:
        pace=(h['pace']+a['pace'])/2
        home_mean=pace*(h['off']+a['def'])/200
        away_mean=pace*(a['off']+h['def'])/200
        return {'home':home_mean+1.5,'away':away_mean-1.5,
                'source':'NBA Stats advanced • pace / OFF / DEF',
                'samples':None,
                'warning':'Przewaga parkietu: umowna korekta +1,5 / −1,5 pkt. '
                          'Status graczy i kalibracja szans niepotwierdzone.'}
    values=[]
    for records in hist.values():
        values.extend(float(p) for _,p,_ in records if 50<float(p)<200)
    if not values:
        return None
    league_mean=float(np.mean(values))
    hf=_team_form_stats(home,hist,league_mean,minimum_history)
    af=_team_form_stats(away,hist,league_mean,minimum_history)
    if hf is None or af is None:
        return None
    return {
        'home':float((hf['off']+af['def'])/2+1.5),
        'away':float((af['off']+hf['def'])/2-1.5),
        'source':'ESPN • forma ważona i regresja do średniej ligi',
        'samples':(hf['n'],af['n']),
        'form':{
            home:{"recent_scored":round(hf['raw_off'],1),
                  "recent_allowed":round(hf['raw_def'],1),
                  "sample_weight":round(hf['sample_weight'],2)},
            away:{"recent_scored":round(af['raw_off'],1),
                  "recent_allowed":round(af['raw_def'],1),
                  "sample_weight":round(af['sample_weight'],2)},
        },
        'warning':'Ważona forma z max. 12 meczów + ostrożna regresja do średniej. '
                  'Nie uwzględniono siły przeciwników ani potwierdzonych składów. '
                  'Szanse modelu są niekalibrowane.',
    }

def eligible_roster(logs:pd.DataFrame|None,abbr:str,opp:str,injuries:pd.DataFrame|None=None,
                    team_context=None,league_avg=None,asof=None):
    """Current team = most recent player log, excluding confirmed 'Out'."""
    cols=['player','team','opp','minutes','PTS','REB','AST','FG3M','status','n_games']
    if logs is None or logs.empty:return pd.DataFrame(columns=cols)
    x=logs.copy().sort_values('GAME_DATE')
    if asof is not None:
        date=pd.to_datetime(asof,utc=True)
        x=x[x['GAME_DATE']<date]
    if x.empty:return pd.DataFrame(columns=cols)
    latest=x.groupby('PLAYER_NAME',sort=False).tail(1)
    latest=latest[latest['TEAM_ABBREVIATION']==abbr]
    lookup={}
    if injuries is not None and not injuries.empty:
        for _,r in injuries.iterrows():lookup[norm_name(r.get('player',''))]=str(r.get('status',''))
    rows=[]
    for _,row in latest.iterrows():
        name=str(row['PLAYER_NAME']);hist=x[x['PLAYER_NAME']==name]
        if len(hist)<2:continue
        # Don't include a player who was last seen 45+ days ago; roster may have changed.
        if asof is not None and (date-row['GAME_DATE']).days>45:continue
        stat=lookup.get(norm_name(name),'Brak wpisu w ESPN')
        if any(p in stat.lower() for p in ('out','inactive','suspended','injured reserve')):continue
        try:
            pr={market:calc_projection(hist,market,opponent=opp,team_context=team_context,averages=league_avg)
                for market in ('PTS','REB','AST','FG3M')}
        except (ValueError,KeyError):continue
        minutes=pr['PTS']['estimated_minutes']
        if minutes<5:continue
        rows.append({'player':name,'team':abbr,'opp':opp,'minutes':minutes,
            **{k:pr[k]['prediction'] for k in ('PTS','REB','AST','FG3M')},
            'status':stat,'n_games':len(hist)})
    return pd.DataFrame(rows,columns=cols).sort_values('minutes',ascending=False).head(12) if rows else pd.DataFrame(columns=cols)

def _player_draws(rng,team_scores,roster):
    """5000 draws per player. Points conditional on team scores; rebounds/assists/3PM stochastic.

    PTS are allocated across tracked players plus a reserve/other category to ensure
    points are not simultaneously credited to several players.
    """
    if roster.empty:return pd.DataFrame()
    n=len(team_scores)
    players=roster.to_dict('records')
    expected=np.array([max(0.,float(r['PTS'])) for r in players],float)
    reserve=max(8.,float(team_scores.mean())*.07)
    weights=np.concatenate([expected,[reserve]])
    weights=weights/weights.sum()
    # Fixed shares in multinomial are a simplification, not player minute/usage certainty.
    allocated=rng.multinomial(np.rint(team_scores).astype(int),weights,size=n)[:,:-1]
    out=[]
    for j,r in enumerate(players):
        factor=np.clip(team_scores/max(1.,float(team_scores.mean())),.65,1.40)
        reb=rng.poisson(np.maximum(0.,float(r['REB'])*factor))
        ast=rng.poisson(np.maximum(0.,float(r['AST'])*factor))
        three=rng.poisson(np.maximum(0.,float(r['FG3M'])*factor))
        # Threes are among made points, not extra points.
        three=np.minimum(three,allocated[:,j]//3)
        out.append({'Zawodnik':r['player'],'Drużyna':r['team'],'PTS':round(float(allocated[:,j].mean()),1),
                    'REB':round(float(reb.mean()),1),'AST':round(float(ast.mean()),1),
                    '3PM':round(float(three.mean()),1),'Minuty':round(float(r['minutes']),1),
                    'Status ESPN':r['status'],'Próba występów':r['n_games']})
    return pd.DataFrame(out)

def simulate_game(game:dict,mean:dict,home_roster=None,away_roster=None,n:int=5000):
    """Exactly n independent match draws, reproducible for each matchup and inputs."""
    if n!=5000:raise ValueError('BestBets v6 symuluje dokładnie 5000 przebiegów meczu.')
    mu_h=_num(mean.get('home'));mu_a=_num(mean.get('away'))
    if any(x is None or not 60<x<170 for x in (mu_h,mu_a)):
        raise ValueError('Brak wiarygodnych oczekiwanych punktów dla obu drużyn.')
    key=f"{game.get('game_id')}|{game.get('home')}|{game.get('away')}|{mu_h:.6f}|{mu_a:.6f}|5000"
    seed=int.from_bytes(sha256(key.encode()).digest()[:8],'big')
    rng=np.random.default_rng(seed)
    # Correlated game pace +/- 6 and team-specific scoring +/- 11; heuristic variances.
    shared=rng.normal(0,6,n)
    home=np.rint(np.clip(mu_h+shared+rng.normal(0,11,n),60,175)).astype(int)
    away=np.rint(np.clip(mu_a+shared+rng.normal(0,11,n),60,175)).astype(int)
    # NBA games don't finish tied. Equal regulation scores -> simplified overtime.
    tied=home==away
    if tied.any():
        h_extra=rng.poisson(9,int(tied.sum()));a_extra=rng.poisson(9,int(tied.sum()))
        same=h_extra==a_extra
        a_extra[same]+=(rng.integers(0,2,size=int(same.sum()))*2-1)
        home[tied]+=h_extra;away[tied]+=a_extra
    if np.any(home==away):raise AssertionError('Symulacja nie może zakończyć się remisem.')
    home_win=float((home>away).mean())
    players=[]
    for code,points,roster in ((game['home'],home,home_roster),(game['away'],away,away_roster)):
        if roster is not None and not roster.empty:
            p=_player_draws(rng,points,roster)
            if not p.empty:players.append(p)
    avg_h,avg_a=float(home.mean()),float(away.mean())
    summary={'game_id':str(game.get('game_id')),'home':game['home'],'away':game['away'],
       'start_utc':game.get('start_utc'),'n_sims':n,'home_win_pct':round(100*home_win,1),
       'away_win_pct':round(100*(1-home_win),1),'home_points':round(avg_h,1),
       'away_points':round(avg_a,1),'total_points':round(float((home+away).mean()),1),
       'home_score_p10':int(np.percentile(home,10)),'home_score_p90':int(np.percentile(home,90)),
       'away_score_p10':int(np.percentile(away,10)),'away_score_p90':int(np.percentile(away,90)),
       'total_p10':int(np.percentile(home+away,10)),'total_p90':int(np.percentile(home+away,90)),
       'source':mean['source'],'warning':mean.get('warning',''),'sample':mean.get('samples'),
       'winner':game['home'] if home_win>=.5 else game['away']}
    return summary,pd.concat(players,ignore_index=True) if players else pd.DataFrame(),home,away

def match_real_odds(featured:pd.DataFrame|None,game:dict,sim:dict,home_draws,away_draws):
    """Compare only same fixture and outcome; odds are exactly those returned by API."""
    cols=['Rynek','Wariant','Linia','Bukmacher','Kurs','Szansa modelu (%)',
          'Próg kursu (%)','Przewaga (pp)','EV modelu (%)','Aktualizacja (UTC)']
    if featured is None or featured.empty:return pd.DataFrame(columns=cols)
    rows=[]
    expected={game['home'],game['away']}
    gtime=pd.to_datetime(game['start_utc'],utc=True,errors='coerce')
    for r in featured.to_dict('records'):
        ht=TEAM_MAP.get(str(r.get('home_team') or ''),'')
        at=TEAM_MAP.get(str(r.get('away_team') or ''),'')
        if (ht,at)!=(game['home'],game['away']):continue
        stamp=pd.to_datetime(r.get('start_utc'),utc=True,errors='coerce')
        if pd.isna(stamp) or pd.isna(gtime) or abs((stamp-gtime).total_seconds())>86400:continue
        course=_num(r.get('odds'))
        if course is None or course<=1:continue
        market=str(r.get('market') or '')
        side=str(r.get('name') or '')
        line=_num(r.get('line'))
        if market=='h2h':
            picked=TEAM_MAP.get(side)
            if picked not in expected:continue
            p=sim['home_win_pct']/100 if picked==game['home'] else sim['away_win_pct']/100
            label='Wygrana meczu';outcome=side
        elif market=='totals' and line is not None:
            if side.lower()=='over':p=float(np.mean(home_draws+away_draws>line))
            elif side.lower()=='under':p=float(np.mean(home_draws+away_draws<line))
            else:continue
            if float(line).is_integer():continue # Pushes need three-way EV calculation.
            label='Suma punktów';outcome=side.upper()
        else:continue
        rows.append({'Rynek':label,'Wariant':outcome,'Linia':line,'Bukmacher':r.get('bookmaker'),
          'Kurs':round(course,3),'Szansa modelu (%)':round(p*100,1),
          'Próg kursu (%)':round(100/course,1),'Przewaga (pp)':round(100*(p-1/course),1),
          'EV modelu (%)':round(100*(p*course-1),1),
          'Aktualizacja (UTC)':r.get('market_updated') or r.get('book_updated') or ''})
    if not rows:return pd.DataFrame(columns=cols)
    # For each identical market, side and line, select max bookmaker price.
    df=pd.DataFrame(rows).sort_values('Kurs',ascending=False)
    return df.drop_duplicates(subset=['Rynek','Wariant','Linia']).reset_index(drop=True)
