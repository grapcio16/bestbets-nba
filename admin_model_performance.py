"""Read-only, admin-only presentation data for independently frozen models.

This module does not access credentials or mutate the tracker. Callers must
check the verified server-side administrator role before loading or exposing it.
"""
from __future__ import annotations

from datetime import datetime, timezone
import pandas as pd

from performance_tracker import performance_metrics


def build_model_report(frame: pd.DataFrame | None, *, season: str) -> dict:
    """Compare forecasts by model, never treating unsettled games as outcomes."""
    base = {"season": season, "as_of_utc": datetime.now(timezone.utc).isoformat(timespec="minutes"),
            "models": [], "error": ""}
    if frame is None or frame.empty:
        return base
    required = {"game_id", "model_id", "home", "away", "forecast_time_utc",
                "start_utc", "home_points", "away_points", "home_win_pct",
                "away_win_pct", "home_score", "away_score"}
    if not required.issubset(frame.columns):
        return {**base, "error": "Archiwum prognoz ma niepełny schemat."}
    models = []
    for name, group in frame.groupby("model_id", dropna=False):
        if pd.isna(name) or not str(name).strip():
            continue
        group = group.sort_values("start_utc", ascending=False).drop_duplicates("game_id")
        settled = group["home_score"].notna() & group["away_score"].notna()
        _, metrics = performance_metrics(group)
        recent = []
        for row in group.head(30).to_dict("records"):
            actual = row.get("home_score") is not None and row.get("away_score") is not None
            actual = actual and pd.notna(row["home_score"]) and pd.notna(row["away_score"])
            recent.append({
                "game_id": str(row["game_id"])[:40],
                "date": str(row["start_utc"])[:16].replace("T", " "),
                "home": str(row["home"])[:12], "away": str(row["away"])[:12],
                "home_pred": round(float(row["home_points"]), 1),
                "away_pred": round(float(row["away_points"]), 1),
                "home_actual": int(row["home_score"]) if actual else None,
                "away_actual": int(row["away_score"]) if actual else None,
            })
        models.append({
            "id": str(name)[:65],
            "snapshots": int(len(group)),
            "settled": int(settled.sum()),
            "evaluated": metrics["games"],
            "metrics": metrics,
            "recent": recent,
        })
    return {**base, "models": sorted(models, key=lambda item: item["id"])}
