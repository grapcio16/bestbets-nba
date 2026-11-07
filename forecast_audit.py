"""Pure and reproducible evaluation of frozen, pre-game NBA score forecasts.

No odds, no bet results, no model retraining. Only evaluate a snapshot created
BEFORE its event started, preventing accidental lookahead. Measurements are
descriptive, not proof of calibration or forecasting advantage.
"""
from __future__ import annotations
import pandas as pd
import numpy as np

PREDICTED_COLUMNS = {
    "game_id","forecast_time_utc","start_utc",
    "away_points","home_points","away_win_pct","home_win_pct"
}
RESULT_COLUMNS = {"game_id","away_score","home_score"}


def evaluate_frozen_predictions(predictions: pd.DataFrame,
                                final_scores: pd.DataFrame):
    """Return per-game verification rows and descriptive aggregate metrics.

    Game IDs must be unique. Forecasts at or after tip-off are excluded.
    Winners are evaluated on actual scores; draws in forecasts break toward
    the home team only if both modeled probabilities are equal.
    """
    if not PREDICTED_COLUMNS.issubset(predictions.columns):
        raise ValueError("Brakuje kolumn archiwum prognoz NBA.")
    if not RESULT_COLUMNS.issubset(final_scores.columns):
        raise ValueError("Brakuje kolumn wyników zakończonych spotkań.")
    if predictions["game_id"].duplicated().any() or final_scores["game_id"].duplicated().any():
        raise ValueError("Jedno spotkanie musi mieć jeden zamrożony wpis.")
    rows=predictions.copy()
    rows["forecast_time_utc"]=pd.to_datetime(rows["forecast_time_utc"],utc=True,errors="coerce")
    rows["start_utc"]=pd.to_datetime(rows["start_utc"],utc=True,errors="coerce")
    rows=rows[(rows["forecast_time_utc"]<rows["start_utc"]) &
              rows["forecast_time_utc"].notna() & rows["start_utc"].notna()]
    rows=rows.merge(final_scores[list(RESULT_COLUMNS)],on="game_id",how="inner",validate="one_to_one")
    numbers=["away_points","home_points","away_win_pct","home_win_pct","away_score","home_score"]
    for key in numbers:
        rows[key]=pd.to_numeric(rows[key],errors="coerce")
    rows=rows.dropna(subset=numbers).copy()
    rows=rows[(rows["away_score"]!=rows["home_score"]) &
              (rows["away_win_pct"].between(0,100)) &
              (rows["home_win_pct"].between(0,100)) &
              ((rows["away_win_pct"]+rows["home_win_pct"]-100).abs()<0.25)]
    if rows.empty:
        return rows,{"games":0,"winner_accuracy":None,"total_mae":None,
                     "team_mae":None,"total_bias":None,"brier":None}
    rows["forecast_total"]=rows["away_points"]+rows["home_points"]
    rows["actual_total"]=rows["away_score"]+rows["home_score"]
    rows["total_error"]=rows["actual_total"]-rows["forecast_total"]
    rows["actual_home_win"]=(rows["home_score"]>rows["away_score"]).astype(int)
    rows["pred_home_win"]=(rows["home_win_pct"]>=rows["away_win_pct"]).astype(int)
    rows["winner_hit"]=(rows["actual_home_win"]==rows["pred_home_win"])
    rows["brier"]=((rows["home_win_pct"]/100)-rows["actual_home_win"])**2
    metrics={
        "games":int(len(rows)),
        "winner_accuracy":round(float(rows["winner_hit"].mean()),4),
        "total_mae":round(float(rows["total_error"].abs().mean()),2),
        "team_mae":round(float(
            (rows["home_score"]-rows["home_points"]).abs().add(
             (rows["away_score"]-rows["away_points"]).abs()).mean()/2),2),
        "total_bias":round(float(rows["total_error"].mean()),2),
        "brier":round(float(rows["brier"].mean()),4),
    }
    return rows,metrics
