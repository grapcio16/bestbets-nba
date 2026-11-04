"""Pure analytics functions. No HTTP calls and no Streamlit dependency.

All probability estimates are uncalibrated until evaluated against held-out games.
"""
from __future__ import annotations

from datetime import datetime
from math import erf, sqrt, log
import re
import unicodedata
import numpy as np
import pandas as pd

STAT_NAMES = {"PTS":"Punkty", "REB":"Zbiórki", "AST":"Asysty", "FG3M":"Celne trójki", "PRA":"Punkty + zbiórki + asysty"}


def norm_name(name):
    s = unicodedata.normalize("NFKD", str(name or ""))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]", "", s.lower())


def minute_value(value):
    if value is None: return np.nan
    if isinstance(value, str) and ":" in value:
        try:
            m, sec = value.split(":",1)
            return float(m) + float(sec) / 60
        except (ValueError, TypeError): return np.nan
    try: return float(value)
    except (ValueError, TypeError): return np.nan


def normalize_logs(raw):
    df = raw.copy()
    df.columns = [str(c).upper() for c in df.columns]
    required = {"PLAYER_NAME", "GAME_DATE", "TEAM_ABBREVIATION", "MIN", "PTS", "REB", "AST", "FG3M"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError("Brakuje kolumn z API NBA: " + ", ".join(sorted(missing)))
    df["GAME_DATE"] = pd.to_datetime(df["GAME_DATE"], errors="coerce", utc=True)
    df["MIN"] = df["MIN"].map(minute_value)
    for stat in ["PTS","REB","AST","FG3M", "FGA", "FG3A", "OREB", "DREB", "TOV"]:
        if stat not in df: df[stat] = np.nan
        df[stat] = pd.to_numeric(df[stat], errors="coerce")
    if "MATCHUP" not in df: df["MATCHUP"] = ""
    df["PRA"] = df[["PTS", "REB", "AST"]].sum(axis=1, min_count=3)
    df = df.dropna(subset=["GAME_DATE", "PLAYER_NAME", "MIN"])
    return df.sort_values(["PLAYER_NAME", "GAME_DATE"]).reset_index(drop=True)


def minutes_projection(g):
    """Conservative, calculated minutes estimate, based only on prior game logs."""
    g = g.sort_values("GAME_DATE")
    vals = pd.to_numeric(g["MIN"], errors="coerce").dropna()
    vals = vals[vals > 2]
    if vals.empty: return np.nan
    mean = float(vals.mean())
    l5 = float(vals.tail(5).mean())
    l10 = float(vals.tail(10).mean())
    est = .55 * l5 + .25 * l10 + .20 * mean
    if len(vals) < 5: est = .50 * mean + .50 * l5
    # Prevent implausible upside from tiny sample or one 40+ min game
    return round(float(np.clip(est, 0, 42)), 1)


def league_context(team_advanced):
    """Team advanced columns from NBA: TEAM_NAME/TEAM_ABBREVIATION, PACE, DEF_RATING.
    Maps team abbreviation; if API lacks abbreviation use a separate team ID merge in UI.
    """
    if team_advanced is None or team_advanced.empty:
        return {}, {}
    t = team_advanced.copy(); t.columns = [str(c).upper() for c in t.columns]
    abbr = "TEAM_ABBREVIATION"
    if abbr not in t: return {}, {}
    lookup = {str(r[abbr]):r.to_dict() for _,r in t.iterrows()}
    med = {}
    for k in ["PACE", "DEF_RATING", "OFF_RATING"]:
        if k in t:
            n = pd.to_numeric(t[k], errors="coerce").dropna()
            if not n.empty: med[k] = float(n.median())
    return lookup, med


def matchup_factor(opponent, team_context=None, averages=None):
    if not opponent or not team_context or not averages: return 1.0
    row = team_context.get(opponent, {})
    if not row: return 1.0
    try:
        pace = float(row.get("PACE", np.nan))
        defense = float(row.get("DEF_RATING", np.nan))
        pace_base = float(averages.get("PACE", np.nan))
        def_base = float(averages.get("DEF_RATING", np.nan))
        if not all(np.isfinite(x) and x > 0 for x in (pace,defense,pace_base,def_base)):
            return 1.0
        # Heuristic, intentionally capped. Validation required.
        return float(np.clip((pace/pace_base)**.5 * (defense/def_base)**.5, .90, 1.10))
    except (ValueError,TypeError): return 1.0


def calc_projection(g, stat, opponent=None, team_context=None, averages=None,
                    minutes_override=None):
    if stat not in STAT_NAMES: raise ValueError("Unsupported market: " + str(stat))
    g = g.sort_values("GAME_DATE").copy()
    g = g[(g["MIN"] > 2) & g[stat].notna()]
    if g.empty: raise ValueError("Brak występów z danymi")
    # Rates instead of raw stats; playing time is modeled explicitly.
    rate = (g[stat].clip(lower=0) / g["MIN"].clip(lower=2))
    rate_s = float(rate.mean()); rate5 = float(rate.tail(5).mean()); rate10 = float(rate.tail(10).mean())
    rate_pred = .5*rate5 + .3*rate10 + .2*rate_s
    if len(g) < 5: rate_pred = .6*rate_s + .4*rate5
    model_minutes = minutes_projection(g)
    projected_minutes = model_minutes if minutes_override is None else float(np.clip(minutes_override,0,48))
    factor = matchup_factor(opponent, team_context, averages)
    pred = max(0., projected_minutes * rate_pred * factor)
    # At low n, prefer conservative predictive variability, not a falsely certain number.
    sdev = float(g[stat].std(ddof=1)) if len(g)>1 else np.nan
    dispersion = max(1.25, sqrt(max(pred, .1)), sdev if np.isfinite(sdev) else 0.0)
    if len(g) < 10: dispersion *= 1.25
    return {"prediction":round(pred,2), "estimated_minutes":round(projected_minutes,1),
            "baseline_minutes":model_minutes, "sample_size":len(g), "stdev":round(dispersion,2),
            "season_avg":round(float(g[stat].mean()),2),
            "last5":round(float(g[stat].tail(5).mean()),2),
            "last10":round(float(g[stat].tail(10).mean()),2),
            "matchup_factor":round(factor,3),
            "reliability":"niska" if len(g)<10 else ("średnia" if len(g)<25 else "wyższa")}


def cdf(x): return 0.5*(1.0+erf(float(x)/sqrt(2)))


def prop_probability(projection, line, side):
    """Half-point or non-integer lines only; fractional probabilities are uncalibrated."""
    side = str(side).upper()
    if side not in ("OVER","UNDER"): raise ValueError("side should be OVER/UNDER")
    mu = float(projection["prediction"]); sd = max(1.0,float(projection["stdev"]))
    line = float(line)
    # continuity correction for counting stats with half-point lines
    prob_over = 1-cdf((line-mu)/sd)
    return float(np.clip(prob_over if side=="OVER" else 1-prob_over, .01, .99))


def implied_probability(odds):
    o = float(odds)
    if not np.isfinite(o) or o<=1: raise ValueError("Kurs musi być >1.00")
    return 1/o


def value_assessment(projection, line, side, odds, other_side_odds=None):
    """Both breakeven and fair (vig normalized when both outcomes available)."""
    prob = prop_probability(projection,line,side)
    implied = implied_probability(odds)
    fair_market = None
    if other_side_odds is not None:
        other = implied_probability(other_side_odds)
        fair_market = implied/(implied+other)
    ev = prob*float(odds)-1
    # No claim of profitable betting before calibration; show numerical indication only.
    return {"p_model":round(prob,4),"p_break_even":round(implied,4),
            "p_market_novig":round(fair_market,4) if fair_market is not None else None,
            "ev_model":round(ev,4),"edge_pp":round(100*(prob-implied),2)}


def project_team_total(home,away,team_context):
    a=team_context.get(home,{});b=team_context.get(away,{})
    try:
        p=(float(a['PACE'])+float(b['PACE']))/2
        home_eff=(float(a['OFF_RATING'])+float(b['DEF_RATING']))/2
        away_eff=(float(b['OFF_RATING'])+float(a['DEF_RATING']))/2
        if min(p,home_eff,away_eff)<1: return None
        return round(float((home_eff+away_eff)*p/100),1)
    except (KeyError,ValueError,TypeError):return None


def rolling_backtest(logs, stat, min_games=6, max_rows=12000):
    """Walk-forward, each forecast uses only games strictly before its target game.
    The threshold is a simulated rolling-average line, NOT a bookmaker line.
    """
    data=[]
    if logs.empty:return pd.DataFrame()
    for player,g in logs.groupby("PLAYER_NAME",sort=False):
        g=g.sort_values("GAME_DATE").reset_index(drop=True)
        for i in range(min_games,len(g)):
            prior=g.iloc[:i]
            target=g.iloc[i]
            try:
                p=calc_projection(prior,stat)
            except ValueError: continue
            if not pd.notna(target[stat]):continue
            line=round(float(prior[stat].tail(10).mean())*2)/2 + .5
            prob=prop_probability(p,line,"OVER")
            actual=float(target[stat])
            data.append({"date":target["GAME_DATE"],"player":player,"team":target["TEAM_ABBREVIATION"],
                         "market":stat,"line":line,"p_over":prob,"actual":actual,
                         "over_hit":int(actual>line),"projection":p["prediction"],"sample_size":i,
                         "line_type":"SYMULOWANA (średnia L10 + 0,5)"})
            if len(data)>=max_rows:break
        if len(data)>=max_rows:break
    return pd.DataFrame(data)


def backtest_external_lines(logs, lines):
    """Use supplied historical lines, with recorded pre-game odds and date.

    Required cols: date, player, market, line, odds_over, odds_under.
    Never fill missing prices or assume these are time-stamped pregame.
    """
    required={"date","player","market","line","odds_over","odds_under"}
    if not required.issubset(lines.columns):
        raise ValueError("CSV wymaga kolumn: " + ", ".join(sorted(required)))
    lg=logs.copy(); lg["_name"]=lg["PLAYER_NAME"].map(norm_name)
    lg["_date"]=pd.to_datetime(lg["GAME_DATE"],utc=True,errors="coerce").dt.date
    rows=[]
    for _,a in lines.iterrows():
        try:
            market=str(a["market"]).upper().strip()
            if market not in STAT_NAMES:continue
            d=pd.Timestamp(a["date"]).date(); n=norm_name(a["player"])
            hist=lg[(lg["_name"]==n)&(lg["_date"]<d)]
            outcome=lg[(lg["_name"]==n)&(lg["_date"]==d)]
            if len(hist)<5 or outcome.empty:continue
            # When the archival quote includes event teams, verify the player's
            # actual game belongs to THAT event. Never settle a different match.
            event_home=str(a.get('home_team','')).strip()
            event_away=str(a.get('away_team','')).strip()
            if event_home and event_away:
                from teams import TEAM_MAP
                team_codes={TEAM_MAP.get(event_home),TEAM_MAP.get(event_away)}
                if None in team_codes or str(outcome.iloc[-1]['TEAM_ABBREVIATION']) not in team_codes:
                    continue
                if 'MATCHUP' in outcome.columns:
                    played=str(outcome.iloc[-1]['MATCHUP'])
                    if played and not all(team in played for team in team_codes):
                        continue
            p=calc_projection(hist,market)
            line=float(a["line"]); actual=float(outcome.iloc[-1][market])
            if actual==line:continue # push, not an over/under win
            prob=prop_probability(p,line,"OVER")
            side="OVER" if prob>=.5 else "UNDER"
            odds=float(a["odds_over"] if side=="OVER" else a["odds_under"])
            if odds<=1:continue
            hit=(actual>line) if side=="OVER" else (actual<line)
            rows.append({"date":d,"player":a["player"],"market":market,"line":line,
                         "p_over":prob,"actual":actual,"over_hit":int(actual>line),"projection":p["prediction"],
                         "sample_size":len(hist),"side":side,"odds":odds,"p_selected":max(prob,1-prob),
                         "hit_selected":int(hit),"return_per_unit":odds-1 if hit else -1,
                         "line_type":"HISTORYCZNA (wgrana przez użytkownika)"})
        except (ValueError,TypeError,KeyError,OverflowError):continue
    return pd.DataFrame(rows)


def calibration_summary(test):
    if test.empty:return {"n":0}
    y=test["over_hit"].astype(float).to_numpy()
    p=test["p_over"].astype(float).to_numpy()
    p=np.clip(p,.001,.999)
    return {"n":len(test),"brier":round(float(np.mean((p-y)**2)),4),
            "logloss":round(float(-np.mean(y*np.log(p)+(1-y)*np.log(1-p))),4),
            "mae_projection":round(float(np.mean(abs(test["projection"]-test["actual"]))),2),
            "accuracy_50":round(float(np.mean((p>=.5)==(y==1))),4)}


def calibration_bins(test, bins=8):
    if test.empty:return pd.DataFrame()
    df=test.copy();df["p_bin"]=pd.cut(df["p_over"],bins=np.linspace(0,1,bins+1),include_lowest=True)
    return df.groupby("p_bin",observed=True).agg(prognoza=("p_over","mean"),trafienia=("over_hit","mean"),proba=("over_hit","size")).reset_index()


def smoothed_calibration_fit(train, bins=10, prior_weight=20):
    """Fit monotone approximate P(over) calibration on PAST records only.

    Uses smoothed empirical bins + pooled adjacent violators (PAVA), no sklearn.
    Call only on a chronologically earlier training subset and evaluate on holdout.
    """
    if train is None or len(train) < 100:
        raise ValueError('Kalibracja wymaga co najmniej 100 wcześniejszych prób')
    p=np.asarray(train['p_over'],dtype=float)
    y=np.asarray(train['over_hit'],dtype=float)
    if not all(np.isfinite(p)) or not all(np.isfinite(y)):
        raise ValueError('Dane kalibracyjne zawierają wartości nieprawidłowe')
    cuts=np.linspace(0,1,bins+1)
    groups=[]
    for i in range(bins):
        mask=(p>=cuts[i]) & ((p<=cuts[i+1]) if i==bins-1 else (p<cuts[i+1]))
        count=int(mask.sum())
        prior_center=(cuts[i]+cuts[i+1])/2
        calibrated=(float(y[mask].sum())+prior_center*prior_weight)/(count+prior_weight)
        groups.append({'a':i,'b':i,'weight':count+prior_weight,'value':calibrated})
    # PAVA enforces nondecreasing forecast probability.
    blocks=[]
    for group in groups:
        blocks.append(group)
        while len(blocks)>1 and blocks[-2]['value']>blocks[-1]['value']:
            b=blocks.pop();a=blocks.pop()
            w=a['weight']+b['weight']
            blocks.append({'a':a['a'],'b':b['b'],'weight':w,
                           'value':(a['value']*a['weight']+b['value']*b['weight'])/w})
    vals=[0.5]*bins
    for block in blocks:
        for i in range(block['a'],block['b']+1):
            vals[i]=float(np.clip(block['value'],.01,.99))
    return {'bins':bins,'values':vals,'count':len(train),'prior_weight':prior_weight}


def calibration_apply(probabilities,calibrator):
    p=np.atleast_1d(np.asarray(probabilities,dtype=float))
    idx=np.clip((p*calibrator['bins']).astype(int),0,calibrator['bins']-1)
    v=np.array(calibrator['values'])[idx]
    if np.isscalar(probabilities):return float(v[0])
    return v


def chronological_calibration_check(test,split=.70,min_total=160):
    """One chronological split: fit early games, evaluate later, never vice versa."""
    if test is None or len(test)<min_total:
        return None
    df=test.sort_values('date').reset_index(drop=True)
    n=int(len(df)*split)
    train,test_tail=df.iloc[:n],df.iloc[n:]
    calibrator=smoothed_calibration_fit(train)
    raw=np.asarray(test_tail['p_over'],dtype=float)
    calibrated=calibration_apply(raw,calibrator)
    outcomes=np.asarray(test_tail['over_hit'],dtype=float)
    return {
       'train':len(train),'holdout':len(test_tail),
       'brier_raw':round(float(np.mean((raw-outcomes)**2)),4),
       'brier_calibrated':round(float(np.mean((calibrated-outcomes)**2)),4),
       'calibrator':calibrator,
       'holdout_frame':test_tail.assign(p_calibrated=calibrated)
    }
