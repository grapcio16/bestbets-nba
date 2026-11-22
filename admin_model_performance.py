"""Read-only, admin-only presentation data for independently frozen models.

This module does not access credentials or mutate the tracker. Callers must
check the verified server-side administrator role before loading or exposing it.
"""
from __future__ import annotations

from datetime import datetime, timezone
import pandas as pd

from performance_tracker import performance_metrics

MODEL_LABELS = {
    "auto_legacy_v72": "V7.2 · Model bazowy",
    "auto_research_form_v74": "V7.4 · Forma drużyn",
    "auto_context_full_v75": "V7.5 · Pełny kontekst",
    "auto_shadow_home_v76": "V7.6 · Test przewagi parkietu",
}

# These IDs represent successive versions of the SAME V7.5 hypothesis.
# Keep original database rows immutable, but display one audited forecast per
# game. In particular, the 9 injury snapshots cannot be added to 16 venue
# snapshots as though they represented 25 distinct matches.
V75_ARCHIVE_IDS = {
    "auto_context_venue_rest_v75",
    "auto_context_injury_minutes_v75",
    "auto_context_full_v75",
}
UNIFIED_V75_MODEL_ID = "auto_context_full_v75"


def _report_groups(frame: pd.DataFrame):
    rows = frame.copy()
    rows["report_model_id"] = rows["model_id"].replace(
        {name: UNIFIED_V75_MODEL_ID for name in V75_ARCHIVE_IDS})
    for name, group in rows.groupby("report_model_id", dropna=False):
        if name != UNIFIED_V75_MODEL_ID:
            yield name, group.sort_values("start_utc", ascending=False).drop_duplicates("game_id")
            continue

        # Prefer the most complete trustworthy pregame evidence. If the fresh
        # combined model had no injury feed, a saved injury-aware historical
        # snapshot takes precedence. Late snapshots never trump pregame ones.
        group = group.copy()
        captured = pd.to_datetime(group["forecast_time_utc"], utc=True, errors="coerce")
        tipoff = pd.to_datetime(group["start_utc"], utc=True, errors="coerce")
        group["_pregame"] = captured.notna() & tipoff.notna() & (captured < tipoff)
        ids = group["model_id"].astype(str)
        informed = group.get("warning", pd.Series("", index=group.index)).astype(str).str.contains(
            "ESPN OUT A/H", regex=False)
        group["_rank"] = 4
        group.loc[ids.eq("auto_context_venue_rest_v75"), "_rank"] = 3
        group.loc[ids.eq(UNIFIED_V75_MODEL_ID), "_rank"] = 2
        group.loc[ids.eq("auto_context_injury_minutes_v75"), "_rank"] = 1
        group.loc[ids.eq(UNIFIED_V75_MODEL_ID) & informed, "_rank"] = 0
        group = (group.sort_values(
            ["_pregame", "_rank", "forecast_time_utc"],
            ascending=[False, True, False], kind="stable")
            .drop_duplicates("game_id")
            .sort_values("start_utc", ascending=False))
        yield name, group.drop(columns=["_pregame", "_rank"])


def _paired_comparison(groups):
    """Compare only outcomes evaluated for EVERY included model.

    V7.5 is captured closer to tipoff than V7.2/V7.4; their raw coverage
    differs. Independent per-model accuracy percentages are not a fair
    head-to-head unless restricted to identical matchups.
    """
    candidates = {}
    for name, group in groups:
        verified, _ = performance_metrics(group)
        if not verified.empty:
            candidates[str(name)] = (group, set(verified["game_id"].astype(str)))
    if len(candidates) < 2:
        return {"games": 0, "models": []}
    common = set.intersection(*(value[1] for value in candidates.values()))
    if not common:
        return {"games": 0, "models": []}
    models = []
    for name, (group, _) in candidates.items():
        _, metrics = performance_metrics(group[group["game_id"].astype(str).isin(common)])
        models.append({"id": name, "label": MODEL_LABELS.get(name, name)[:80],
                       "metrics": metrics})
    return {"games": len(common), "models": sorted(models, key=lambda item: item["id"])}


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
    groups = list(_report_groups(frame))
    for name, group in groups:
        if pd.isna(name) or not str(name).strip():
            continue
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
                "origin_model_id": str(row["model_id"])[:65],
            })
        models.append({
            "id": str(name)[:65],
            "label": MODEL_LABELS.get(str(name), str(name))[:80],
            "snapshots": int(len(group)),
            "settled": int(settled.sum()),
            "evaluated": metrics["games"],
            "metrics": metrics,
            "recent": recent,
        })
    return {**base, "models": sorted(models, key=lambda item: item["id"]),
            "paired_comparison": _paired_comparison(groups)}


def build_quarter_report(frame: pd.DataFrame | None) -> dict:
    """Admin-only Q1-Q4 audit, with matched-game head-to-head comparison."""
    import numpy as np
    from simulation_quarter_shadow import MODEL_IDS, quarter_performance_metrics

    names = {
        MODEL_IDS["auto_legacy_v72"]: "V7.2 · Kwarty",
        MODEL_IDS["auto_research_form_v74"]: "V7.4 · Kwarty",
        MODEL_IDS["auto_context_full_v75"]: "V7.5 · Kwarty",
        MODEL_IDS["auto_shadow_home_v76"]: "V7.6 · Kwarty",
    }
    response = {"status": "research_only", "models": [], "paired": [],
                "paired_games": 0, "caveat": (
                    "Warunkowy rozklad punktow z 5000 wynikow koncowych; "
                    "nie jest play-by-play ani skalibrowanym prawdopodobienstwem kwart.")}
    if frame is None or frame.empty:
        return response
    required = {"game_id", "model_id", "quarter", "forecast_time_utc", "start_utc",
                "home_points", "away_points", "home_win_pct", "away_win_pct",
                "tie_pct", "home_actual", "away_actual"}
    if not required.issubset(frame.columns):
        return {**response, "error": "Niepelny schemat trackera kwart."}
    rows = frame[frame["model_id"].isin(names)].copy()
    if rows.empty:
        return response
    captured = pd.to_datetime(rows["forecast_time_utc"], utc=True, errors="coerce")
    start = pd.to_datetime(rows["start_utc"], utc=True, errors="coerce")
    rows = rows.loc[captured.notna() & start.notna() & (captured < start)].copy()
    for col in ("quarter", "home_points", "away_points",
                "home_win_pct", "away_win_pct", "tie_pct",
                "home_actual", "away_actual"):
        rows[col] = pd.to_numeric(rows[col], errors="coerce")
    rows = rows[rows["quarter"].between(1, 4)]
    rows = rows.drop_duplicates(["game_id", "model_id", "quarter"])
    if rows.empty:
        return response

    settled = rows.dropna(subset=["home_actual", "away_actual"])
    complete = settled.groupby(["model_id", "game_id"])["quarter"].nunique()
    complete = complete[complete.eq(4)]
    games_by_model = {
        model: set(complete.loc[model].index.astype(str)) if model in complete.index.get_level_values(0)
        else set()
        for model in names
    }

    def metrics_table(data):
        per_q = quarter_performance_metrics(data)
        if per_q.empty:
            return {"n_quarters": 0, "team_mae": None,
                    "team_bias": None, "winner_accuracy": None,
                    "brier_3way": None, "quarters": []}
        weights = per_q["n"].to_numpy(dtype=float)
        aggregate = {
            "n_quarters": int(weights.sum()),
            "team_mae": round(float(np.average(per_q["team_mae"], weights=weights)), 3),
            "team_bias": round(float(np.average(per_q["team_bias"], weights=weights)), 3),
            "winner_accuracy": round(float(np.average(per_q["winner_accuracy"], weights=weights)), 2),
            "brier_3way": round(float(np.average(per_q["brier_3way"], weights=weights)), 4),
        }
        return {**aggregate, "quarters": per_q[[
            "quarter", "n", "team_mae", "winner_accuracy", "brier_3way"
        ]].to_dict("records")}

    for model, label in names.items():
        model_rows = rows[rows["model_id"].eq(model)]
        graded = settled[settled["model_id"].eq(model)]
        response["models"].append({
            "id": model, "label": label,
            "snapshots": int(len(model_rows)),
            "games_saved": int(model_rows["game_id"].nunique()),
            "games_settled": int(len(games_by_model[model])),
            **metrics_table(graded),
        })

    if all(games_by_model.values()):
        common = set.intersection(*games_by_model.values())
    else:
        common = set()
    response["paired_games"] = len(common)
    if common:
        paired = settled[settled["game_id"].astype(str).isin(common)]
        for model, label in names.items():
            response["paired"].append({
                "id": model, "label": label,
                **metrics_table(paired[paired["model_id"].eq(model)])
            })
    return response
