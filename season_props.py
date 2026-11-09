"""BestBets v7.21: verified season-long Over/Under rates and opponent context.

Pure research helpers. Never equate observed hit rates to calibrated future
probabilities. Defensive adjustment is a capped, unvalidated proxy for PTS;
it must not be automatically applied to REB/AST/3PM, nor to a matchup whose
identity or date is uncertain.
"""
from __future__ import annotations
import math
import pandas as pd
import numpy as np
from core import norm_name, calc_projection, prop_probability, STAT_NAMES


def season_window(season):
    try:
        year=int(str(season).split("-")[0])
        if not 2000<=year<=2100:raise ValueError()
        return pd.Timestamp(f"{year}-10-01T00:00:00Z")
    except (TypeError,ValueError,IndexError) as e:
        raise ValueError("Nieprawidłowy sezon NBA") from e


def clean_player_season(logs, player, season, cutoff_utc, player_id=None):
    """All observed appearances by athlete from Oct 1 to STRICT pregame cutoff."""
    columns=["PLAYER_NAME","TEAM_ABBREVIATION","GAME_DATE","MIN",
             "PTS","REB","AST","FG3M","PRA","GAME_ID"]
    if not isinstance(logs,pd.DataFrame) or logs.empty:
        return pd.DataFrame(columns=columns)
    df=logs.copy()
    df.columns=[str(col).upper() for col in df.columns]
    if not {"PLAYER_NAME","GAME_DATE","PTS","REB","AST","FG3M"}.issubset(df.columns):
        return pd.DataFrame(columns=columns)
    cutoff=pd.to_datetime(cutoff_utc,utc=True,errors="coerce")
    if pd.isna(cutoff):return pd.DataFrame(columns=columns)
    if player_id and "PLAYER_ID" in df:
        ids=df["PLAYER_ID"].fillna("").astype(str)
        same=df[ids==str(player_id)]
        if not same.empty:df=same
        else:df=df[df["PLAYER_NAME"].map(norm_name)==norm_name(player)]
    else:
        df=df[df["PLAYER_NAME"].map(norm_name)==norm_name(player)]
    df["GAME_DATE"]=pd.to_datetime(df["GAME_DATE"],utc=True,errors="coerce")
    df=df[(df["GAME_DATE"]>=season_window(season))&
          (df["GAME_DATE"]<cutoff)].copy()
    if df.empty:return df
    for col in ("PTS","REB","AST","FG3M","MIN"):
        if col in df:df[col]=pd.to_numeric(df[col],errors="coerce")
    if "MIN" in df:df=df[df["MIN"]>0]
    if "GAME_ID" in df:
        df=df.drop_duplicates(["GAME_ID","PLAYER_NAME"],keep="last")
    if "PRA" not in df:
        df["PRA"]=df[["PTS","REB","AST"]].sum(axis=1,min_count=3)
    return df.sort_values("GAME_DATE").reset_index(drop=True)


def observed_hit_rates(logs, market, line, recent=10):
    """Over + Under + Push = 100% across all *recorded appearances*."""
    if market not in STAT_NAMES:
        raise ValueError("Nieobsługiwany rynek")
    if logs is None or logs.empty or market not in logs:
        return None
    try:
        threshold=float(line)
        if not math.isfinite(threshold) or threshold<0:raise ValueError()
    except (TypeError,ValueError):
        raise ValueError("Niepoprawna linia")
    vals=pd.to_numeric(logs[market],errors="coerce").dropna()
    vals=vals[vals>=0]
    if vals.empty:return None
    def subset(x):
        return {"n":len(x),
                "over":int((x>threshold).sum()),
                "under":int((x<threshold).sum()),
                "push":int((x==threshold).sum()),
                "over_pct":round(100*float((x>threshold).mean()),1),
                "under_pct":round(100*float((x<threshold).mean()),1),
                "push_pct":round(100*float((x==threshold).mean()),1),
                "mean":round(float(x.mean()),1),
                "median":round(float(x.median()),1)}
    return {"season":subset(vals),"last10":subset(vals.tail(recent))}


def opponent_defensive_profile(results, opponent, cutoff_utc, min_games=5):
    """Observed opponent TEAM points allowed (not position-specific player defense)."""
    req={"start_utc","home","away","home_score","away_score","status_code"}
    if results is None or not isinstance(results,pd.DataFrame) or not req.issubset(results):
        return None
    cutoff=pd.to_datetime(cutoff_utc,utc=True,errors="coerce")
    if pd.isna(cutoff):return None
    r=results.copy()
    r["start_utc"]=pd.to_datetime(r["start_utc"],utc=True,errors="coerce")
    for k in ("home_score","away_score","status_code"):
        r[k]=pd.to_numeric(r[k],errors="coerce")
    r=r[(r["status_code"]==3)&(r["start_utc"]<cutoff)&
        r["home_score"].between(55,200)&r["away_score"].between(55,200)]
    if "game_id" in r:
        r=r.drop_duplicates("game_id")
    if r.empty:return None
    lg=float(pd.concat([r["home_score"],r["away_score"]]).mean())
    team=r[(r["home"]==opponent)|(r["away"]==opponent)].sort_values("start_utc")
    if len(team)<min_games:return None
    against=np.where(team["home"]==opponent,team["away_score"],team["home_score"])
    a=np.asarray(against,dtype=float)
    mean=float(a.mean())
    recent=float(a[-min(10,len(a)):].mean())
    # Both overall and recent defense; small samples shrink toward league mean.
    observed=.65*recent+.35*mean
    sample_weight=len(a)/(len(a)+12)
    ratio=1+sample_weight*(observed/lg-1)
    # This is a transparent HEURISTIC to be backtested, not a calibration.
    factor=float(np.clip(ratio**.45,.92,1.08))
    return {
        "opponent":opponent,"games":len(a),
        "allowed_season":round(mean,1),"allowed_last10":round(recent,1),
        "league_team_points":round(lg,1),
        "scoring_multiplier":round(factor,4),
        "label":"Przybliżenie na podstawie punktów oddawanych przez CAŁĄ drużynę",
        "warning":"Nie jest to obrona przeciw pozycji ani potwierdzona korekta modelu.",
    }


def upcoming_team_games(schedule, selected_date, timezone, now):
    """Current scheduled game for team, on explicitly selected local calendar day.

    If two games match the same team/day, mark AMBIGUOUS instead of guessing.
    """
    req={"game_id","start_utc","home","away","status_code"}
    if not isinstance(schedule,pd.DataFrame) or not req.issubset(schedule):
        return {}
    games=schedule.copy()
    games["start_utc"]=pd.to_datetime(games["start_utc"],utc=True,errors="coerce")
    games["status_code"]=pd.to_numeric(games["status_code"],errors="coerce")
    clock=pd.to_datetime(now,utc=True,errors="coerce")
    if pd.isna(clock):return {}
    local=pd.to_datetime(games["start_utc"]).dt.tz_convert(timezone)
    try:
        day=pd.Timestamp(selected_date).date()
    except (ValueError,TypeError):
        return {}
    games=games[(local.dt.date==day)&(games["status_code"]==1)&
                (games["start_utc"]>clock)].dropna(subset=["start_utc"])
    out={}
    for rec in games.to_dict("records"):
        h=str(rec["home"]);a=str(rec["away"])
        for team,opponent in ((h,a),(a,h)):
            entry={"opponent":opponent,"game_id":str(rec["game_id"]),
                   "start_utc":rec["start_utc"],
                   "game":a+" @ "+h,
                   "ambiguous":False}
            if team in out:out[team]={"ambiguous":True}
            else:out[team]=entry
    return out


def research_matchup_estimate(logs,market,line,defense=None):
    """V1 estimated Over/Under after optional PTS-only team defense modifier.

    Explicitly non-calibrated. Requires >=10 observed performances in season.
    """
    if len(logs)<10:return None
    pred=calc_projection(logs,market)
    factor=1.
    if market=="PTS" and defense is not None:
        factor=float(defense["scoring_multiplier"])
    adjusted=dict(pred)
    adjusted["prediction"]=float(pred["prediction"])*factor
    over=prop_probability(adjusted,line,"OVER")
    return {
        "p_over":round(100*over,1),"p_under":round(100*(1-over),1),
        "mean":round(adjusted["prediction"],1),
        "factor":factor,
        "matchup_used":bool(market=="PTS" and defense is not None),
        "sample":int(pred["sample_size"]),
        "model":"V1 / NIEKALIBROWANY",
    }


SEASON_RESULT_COLUMNS=[
    "Zawodnik","Drużyna","Rynek","Linia",
    "Występy sezon","OVER sezon %","UNDER sezon %","ZWROT sezon %",
    "OVER L10 %","UNDER L10 %","Śr. sezon","Ostatnie 10: OVER",
    "Przeciwnik","Obrona: stracone pkt/mecz","Obrona: L10 stracone",
    "Korekta PTS (%)","P(OVER) v2 %","P(UNDER) v2 %",
    "P(OVER) bez defensywy %","Status","Źródło statystyk","Uwagi",
    "Kurs OVER","Kurs UNDER",
]


def analyze_season_offers(offers, histories, identities, events, results,
                          season, now, min_games=10):
    """Calculate every known athlete's seasonal frequency; apply cautious
    PTS-only matchup adjustment to v2 when next game and defense are verified.

    Histories and identities must come from a real NBA/ESPN data source, and
    schedules are never guessed from the uploaded market screenshot.
    """
    from prediction_engine_v2 import forecast_v2
    from screenshot_import import parse_line, _valid_decimal
    table=[]
    for raw in offers.to_dict("records") if isinstance(offers,pd.DataFrame) else []:
        name=str(raw.get("Zawodnik") or "").strip()
        market=str(raw.get("Rynek") or "PTS").upper().strip()
        line=parse_line(raw.get("Linia"))
        key=norm_name(name)
        identity=(identities or {}).get(key)
        event=None
        notes=[]
        out={col:None for col in SEASON_RESULT_COLUMNS}
        out.update({
            "Zawodnik":name,"Rynek":market,"Linia":line,
            "Kurs OVER":_valid_decimal(raw.get("Kurs OVER")),
            "Kurs UNDER":_valid_decimal(raw.get("Kurs UNDER")),
            "Status":"BRAK DANYCH",
            "Uwagi":"","Źródło statystyk":"—",
        })
        if market not in STAT_NAMES or line is None or not key:
            out["Uwagi"]="Nieprawidłowe nazwisko, rynek lub linia."
            table.append(out);continue
        if not identity or identity.get("ambiguous"):
            out["Uwagi"]="Nie znaleziono jednoznacznej tożsamości zawodnika w aktualnych danych NBA."
            table.append(out);continue
        team=str(identity.get("team") or "")
        out["Drużyna"]=team
        out["Źródło statystyk"]=str(identity.get("source") or "Nieokreślone")
        raw_logs=(histories or {}).get(key)
        event=(events or {}).get(team)
        if not event or event.get("ambiguous"):
            notes.append("Nie potwierdzono jednego meczu tej drużyny we wskazanym dniu — brak korekty przeciwnika.")
        elif event.get("opponent"):
            out["Przeciwnik"]=str(event["opponent"])
        asof=event.get("start_utc") if event and not event.get("ambiguous") else now
        df=clean_player_season(raw_logs,name,season,asof,identity.get("id"))
        historical=observed_hit_rates(df,market,line)
        if historical is None:
            out["Uwagi"]="Brak poprawnych rzeczywistych występów zawodnika od początku sezonu."
            table.append(out);continue
        all_=historical["season"];recent=historical["last10"]
        out.update({
            "Występy sezon":all_["n"],
            "OVER sezon %":all_["over_pct"],
            "UNDER sezon %":all_["under_pct"],
            "ZWROT sezon %":all_["push_pct"],
            "OVER L10 %":recent["over_pct"],
            "UNDER L10 %":recent["under_pct"],
            "Śr. sezon":all_["mean"],
            "Ostatnie 10: OVER":f'{recent["over"]}/{recent["n"]}',
            "Status":"TYLKO HISTORIA",
        })
        if identity.get("stale") or identity.get("partial"):
            notes.append("Źródło nie gwarantuje pełnej historii sezonowej — częstości dotyczą tylko pobranych występów.")
        if df["TEAM_ABBREVIATION"].nunique()>1:
            notes.append("Zmiana drużyny: dane sezonowe obejmują różne role zawodnika.")
        if all_["n"]<min_games:
            notes.append(f"Tylko {all_['n']} występów (do modelu minimum {min_games}).")
        elif abs(line-round(line))<1e-9:
            notes.append("Linia całkowita: możliwy zwrot. Pokazujemy 3 stany, bez dwustanowego modelu v2.")
        else:
            defense=None
            if out["Przeciwnik"] and event:
                defense=opponent_defensive_profile(results,out["Przeciwnik"],event["start_utc"])
                if defense:
                    out["Obrona: stracone pkt/mecz"]=defense["allowed_season"]
                    out["Obrona: L10 stracone"]=defense["allowed_last10"]
                else:
                    notes.append("Za mało potwierdzonych finałów rywala do korekty defensywy.")
            factor=(defense["scoring_multiplier"]
                    if defense and market in ("PTS","PRA") else 1.)
            if market not in ("PTS","PRA") and defense:
                notes.append("Obrona w punktach drużyny nie koryguje automatycznie zbiórek, asyst ani trójek.")
            if factor!=1.:
                out["Korekta PTS (%)"]=round((factor-1)*100,1)
            try:
                model=forecast_v2(df,market,line,asof,min_games=min_games,
                                  draws=2048,scoring_multiplier=factor)
                out["P(OVER) v2 %"]=round(100*model["p_over"],1)
                out["P(UNDER) v2 %"]=round(100*model["p_under"],1)
                out["Status"]="MODEL TESTOWY"
                if factor!=1:
                    base=forecast_v2(df,market,line,asof,min_games=min_games,draws=2048)
                    out["P(OVER) bez defensywy %"]=round(100*base["p_over"],1)
                    notes.append("Korekta defensywy to niezweryfikowana hipoteza; nie są to skalibrowane szanse.")
                elif not defense:
                    notes.append("Prognoza v2 BEZ zweryfikowanej korekty defensywy przeciwnika.")
            except (ValueError,KeyError,TypeError) as exc:
                notes.append("Nie można policzyć eksperymentalnego modelu: "+str(exc)[:90])
        notes.append("Historyczny % nie jest prognozą kolejnego meczu.")
        out["Uwagi"]=" ".join(notes)
        table.append(out)
    return pd.DataFrame(table,columns=SEASON_RESULT_COLUMNS)
