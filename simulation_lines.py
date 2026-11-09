"""BestBets v7.19 — exact market-line research on the 5,000 game draws.

No new sportsbook data, no fabricated odds, no changed production forecast.
Every probability is a Monte Carlo frequency CONDITIONED ON THE PRESENT MODEL,
not a calibrated chance. Retains pushes on whole-number lines. Alternative
model sensitivity uses only completed games before tipoff.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

from simulation_engine import (
    advanced_ratings, completed_team_scores, legacy_matchup_means,
    matchup_means, simulate_game,
)
from simulation_data_audit import verified_history, venue_research_candidate
from opponent_ratings import regularized_matchup_means


def _line(v, lower, upper):
    try:
        f=float(v)
    except (TypeError,ValueError) as exc:
        raise ValueError("Linia musi być liczbą") from exc
    if not math.isfinite(f) or f<lower or f>upper:
        raise ValueError(f"Linia musi być w zakresie {lower:g}–{upper:g}.")
    return f


def _draws(home_draws, away_draws):
    h=np.asarray(home_draws, dtype=float)
    a=np.asarray(away_draws, dtype=float)
    if h.ndim!=1 or a.ndim!=1 or len(h)!=5000 or len(a)!=5000:
        raise ValueError("Do porównania wymagane są dokładnie 5000 wyników obu drużyn.")
    if not (np.isfinite(h).all() and np.isfinite(a).all()):
        raise ValueError("Zestaw wyników zawiera nieprawidłowe wartości.")
    return h,a


def score_line_probabilities(home_draws, away_draws, total_line, home_handicap):
    """P(total O/U) and P(home/away cover), exact pushes and quantile ranges.

    Negative home_handicap (e.g. -6.5) means the home team must win by 7+
    to cover. Both sides total 100% including PUSH, never double-count draws.
    """
    home,away=_draws(home_draws,away_draws)
    total_line=_line(total_line,100,400)
    home_handicap=_line(home_handicap,-75,75)
    total=home+away
    margin=home-away
    tol=1e-7
    over=np.count_nonzero(total>total_line+tol)
    under=np.count_nonzero(total<total_line-tol)
    total_push=len(total)-over-under
    spread=margin+home_handicap
    home_cover=np.count_nonzero(spread>tol)
    away_cover=np.count_nonzero(spread<-tol)
    spread_push=len(spread)-home_cover-away_cover
    return {
        "n":5000,
        "total_line":total_line,"home_handicap":home_handicap,
        "total_over":over/5000,"total_under":under/5000,
        "total_push":total_push/5000,
        "home_cover":home_cover/5000,"away_cover":away_cover/5000,
        "spread_push":spread_push/5000,
        "total_mean":float(total.mean()),"margin_mean":float(margin.mean()),
        "total_p10":float(np.percentile(total,10)),
        "total_p90":float(np.percentile(total,90)),
        "margin_p10":float(np.percentile(margin,10)),
        "margin_p90":float(np.percentile(margin,90)),
    }


def quoted_price_diagnostics(probability, push_probability, decimal_odds):
    """Optional *conditional-model* quote math with exact push accounting."""
    s=str(decimal_odds or "").replace(",",".").strip()
    if not s:
        return None
    try:
        odds=float(s)
    except (ValueError,TypeError) as exc:
        raise ValueError("Kurs musi być liczbą dziesiętną, np. 1,85.") from exc
    if not math.isfinite(odds) or not 1.01<=odds<=100:
        raise ValueError("Kurs musi być w zakresie 1,01–100.")
    p=_line(probability,0,1)
    push=_line(push_probability,0,1)
    if p+push>1.00000001:
        raise ValueError("Błędne prawdopodobieństwo wygranej i zwrotu.")
    # With a push: no win/loss; expected net per 1 unit = odds*p + push - 1
    return {
        "odds":odds,"conditional_break_even":(1-push)/odds,
        "model_ev_pct":100*(odds*p+push-1),
        "note":"Niezweryfikowane EV WEDŁUG MODELU, NIE prognoza rzeczywistego zwrotu.",
    }


def alternate_scenarios(history, game, advanced=None):
    """Optional pregame-only scoring means; no fallback values are invented."""
    tipoff=game.get("start_utc")
    prior=verified_history(history,tipoff)
    teams=completed_team_scores(prior)
    ratings=advanced_ratings(
        advanced if isinstance(advanced,pd.DataFrame) else pd.DataFrame())
    home=str(game.get("home") or "")
    away=str(game.get("away") or "")
    variants={
        "Podstawowy v7.2": legacy_matchup_means(home,away,ratings,teams),
        "Ważona forma":matchup_means(home,away,ratings,teams),
        "Siła przeciwników":regularized_matchup_means(home,away,prior,tipoff),
        "Dom/wyjazd":venue_research_candidate(prior,game),
    }
    return {label:mean for label,mean in variants.items() if mean is not None}


def scenario_line_table(game, history, advanced, total_line, home_handicap,
                        original_summary, home_draws, away_draws):
    """Compare CURRENT 5000 result with independent, uncalibrated candidates.

    Original model is inserted from its existing 5,000 draws so its percentage
    exactly matches the visible card, regardless of availability of other models.
    """
    base=score_line_probabilities(home_draws,away_draws,total_line,home_handicap)
    rows=[{
        "Wariant":"Na karcie meczu",
        "Średnia suma":round(base["total_mean"],1),
        "Średni handicap":round(base["margin_mean"],1),
        "Suma OVER (%)":round(100*base["total_over"],1),
        "Gospodarze pokryją (%)":round(100*base["home_cover"],1),
        "P(gospodarze wygrają) (%)":original_summary.get("home_win_pct"),
        "Źródło":"Na podstawie prognozy wyświetlonej na karcie",
    }]
    for label,mean in alternate_scenarios(history,game,advanced).items():
        try:
            summary,_,h,a=simulate_game(game,mean)
            values=score_line_probabilities(h,a,total_line,home_handicap)
            rows.append({
                "Wariant":label,
                "Średnia suma":round(values["total_mean"],1),
                "Średni handicap":round(values["margin_mean"],1),
                "Suma OVER (%)":round(100*values["total_over"],1),
                "Gospodarze pokryją (%)":round(100*values["home_cover"],1),
                "P(gospodarze wygrają) (%)":summary["home_win_pct"],
                "Źródło":str(mean.get("source","Źródło nieznane")),
            })
        except (ValueError,KeyError,TypeError,np.linalg.LinAlgError):
            continue
    frame=pd.DataFrame(rows)
    if len(frame)<=1:
        return frame,{
            "available":False,
            "warning":"Brak niezależnego wariantu z wystarczającymi danymi. "
                      "Nie należy uznawać tego za zgodność modeli.",
        }
    # These ranges are diagnostics, NOT calibrated confidence intervals.
    p_over=frame["Suma OVER (%)"].astype(float)
    p_handicap=frame["Gospodarze pokryją (%)"].astype(float)
    total_range=float(p_over.max()-p_over.min())
    cover_range=float(p_handicap.max()-p_handicap.min())
    warn=(total_range>=12 or cover_range>=12)
    return frame,{
        "available":True,
        "total_spread_pp":round(total_range,1),
        "cover_spread_pp":round(cover_range,1),
        "models":len(frame),
        "sensitive":warn,
        "warning":("Duża rozbieżność między niekalibrowanymi modelami; "
                   "sama prognoza jest wrażliwa na założenia."
                   if warn else
                   "Warianty mają zbliżone wyniki, lecz nie dowodzi to "
                   "poprawnej kalibracji ani przewagi nad bukmacherem."),
    }
