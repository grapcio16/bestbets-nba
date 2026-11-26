"""Prospective V8 Shadow scorecard — archived before tipoff, read-only.

Compares V8.1, V8.2 and V7 on overlapping verified NBA finals.
It NEVER calculates retrospective forecasts and NEVER writes to the database.
Results have no statistical significance claim while samples are small.
"""
from __future__ import annotations

import json
import os
from collections import Counter, defaultdict

import numpy as np
import pandas as pd


def _timestamp(value):
    try:
        t = pd.to_datetime(value, utc=True, errors="coerce")
        return t if not pd.isna(t) else None
    except (TypeError, ValueError):
        return None


def _number(value):
    try:
        x = float(value)
        return x if np.isfinite(x) else None
    except (ValueError, TypeError, OverflowError):
        return None


def _validated(row, source):
    """Reject retrospective, incomplete, contradictory and tied NBA finals."""
    start = _timestamp(row.get("start_utc"))
    issued = _timestamp(row.get(
        "issued_at" if source == "v8" else "forecast_time_utc"))
    settlement = _timestamp(row.get(
        "settled_at" if source == "v8" else "settled_at_utc"))
    if (start is None or issued is None or settlement is None
            or issued >= start - pd.Timedelta(minutes=15)
            or settlement < start):
        return None
    if source == "v8":
        actual_h, actual_a = _number(row.get("actual_home")), _number(row.get("actual_away"))
        expected_h, expected_a = _number(row.get("mean_home")), _number(row.get("mean_away"))
        home_p = _number(row.get("home_win_pct"))
    else:
        actual_h, actual_a = _number(row.get("home_score")), _number(row.get("away_score"))
        expected_h, expected_a = _number(row.get("home_points")), _number(row.get("away_points"))
        home_p = _number(row.get("home_win_pct"))
    fields = (actual_h, actual_a, expected_h, expected_a, home_p)
    if any(x is None for x in fields):
        return None
    if (not 50 <= actual_h <= 200 or not 50 <= actual_a <= 200
            or actual_h == actual_a or not 50 <= expected_h <= 200
            or not 50 <= expected_a <= 200 or not 0 <= home_p <= 100):
        return None
    model = str(row.get("model_id") or "")
    game_id = str(row.get("game_id") or "")
    home, away = str(row.get("home") or ""), str(row.get("away") or "")
    if not model or not game_id.isdecimal() or not home or not away or home == away:
        return None
    scenario_h, scenario_a = None, None
    if source == "v8":
        scenario_h, scenario_a = _number(row.get("scenario_home")), _number(row.get("scenario_away"))
    report = row.get("report") if source == "v8" else None
    return {
        "source": source, "model_id": model, "game_id": game_id,
        "home": home, "away": away, "actual_home": actual_h,
        "actual_away": actual_a, "mean_home": expected_h,
        "mean_away": expected_a, "home_win_pct": home_p,
        "scenario_home": scenario_h, "scenario_away": scenario_a,
        "report": report if isinstance(report, dict) else {},
        "training_examples": row.get("training_examples") if source == "v8" else None,
        "issued_at": issued.isoformat(),
    }


def _metrics(records):
    if not records:
        return None
    actual = np.array([[r["actual_home"], r["actual_away"]] for r in records], dtype=float)
    means = np.array([[r["mean_home"], r["mean_away"]] for r in records], dtype=float)
    home_outcome = (actual[:, 0] > actual[:, 1]).astype(float)
    probs = np.array([r["home_win_pct"] / 100.0 for r in records])
    points_error = means - actual
    hit = np.where(probs == 0.5, 0.5, ((probs > 0.5) == (home_outcome == 1)).astype(float))
    result = {
        "n": len(records),
        "winner_hit_pct": round(float(100 * np.mean(hit)), 2),
        "brier": round(float(np.mean((probs - home_outcome) ** 2)), 4),
        "team_points_mae": round(float(np.mean(np.abs(points_error))), 2),
        "total_points_mae": round(float(np.mean(np.abs(points_error.sum(axis=1)))), 2),
        "total_points_bias": round(float(np.mean(points_error.sum(axis=1))), 2),
    }
    if all(r["scenario_home"] is not None and r["scenario_away"] is not None for r in records):
        scenarios = np.array([[r["scenario_home"], r["scenario_away"]]
                              for r in records], dtype=float)
        error = scenarios - actual
        result["scenario_team_points_mae"] = round(float(np.mean(np.abs(error))), 2)
        result["scenario_total_points_mae"] = round(
            float(np.mean(np.abs(error.sum(axis=1)))), 2)
        result["scenario_tied_final_count"] = int(np.sum(scenarios[:, 0] == scenarios[:, 1]))
        for name, target in (("home", actual[:, 0]),
                             ("away", actual[:, 1]),
                             ("total", actual.sum(axis=1))):
            coverage = []
            for r, true_score in zip(records, target):
                interval = r["report"].get(f"{name}_p10_p50_p90")
                if (isinstance(interval, list) and len(interval) == 3
                        and all(_number(x) is not None for x in interval)
                        and float(interval[0]) <= float(interval[2])):
                    coverage.append(float(interval[0]) <= true_score <= float(interval[2]))
            result[f"{name}_80pct_interval_coverage"] = (
                round(float(100 * np.mean(coverage)), 1) if coverage else None)
            result[f"{name}_intervals_checked"] = len(coverage)
    return result


def _dedupe(rows, kind):
    records = {}
    invalid = 0
    for row in rows:
        valid = _validated(row, kind)
        if valid is None:
            invalid += 1
            continue
        key = (valid["model_id"], valid["game_id"])
        if key in records:
            raise ValueError("duplicate archived forecast in scorecard")
        records[key] = valid
    return records, invalid


def _compatible(a, b):
    return (a["game_id"] == b["game_id"] and
            a["home"] == b["home"] and a["away"] == b["away"] and
            a["actual_home"] == b["actual_home"] and
            a["actual_away"] == b["actual_away"])


def evaluate_records(v8_rows, v7_rows):
    """Fair model comparisons use exactly matching, settled, pregame IDs."""
    v8_all = list(v8_rows)
    v7_all = list(v7_rows)
    v8, bad_v8 = _dedupe(v8_all, "v8")
    v7, bad_v7 = _dedupe(v7_all, "v7")
    v8_models = sorted({r["model_id"] for r in v8.values()})
    v7_models = sorted({r["model_id"] for r in v7.values()})
    recorded = Counter(str(r.get("model_id")) for r in v8_all)
    groups = defaultdict(list)
    for r in v8.values():
        groups[r["model_id"]].append(r)
    for r in v7.values():
        groups[r["model_id"]].append(r)
    scorecard = {
        "status": "prospective_settlement_available" if v8 else "waiting_for_settled_games",
        "v8_archived_by_version": dict(sorted(recorded.items())),
        "v8_valid_settled_by_version": {
            model: len(groups[model]) for model in v8_models},
        "v8_pregame_rows_without_valid_settlement": bad_v8,
        "v7_rows_without_valid_settlement": bad_v7,
        "model_metrics": {
            model: _metrics(groups[model]) for model in v8_models + v7_models},
        "common_game_comparisons": [],
        "sample_disclaimer": ("A small shared sample is observational only; "
            "models need more prospective fixtures for calibration claims."),
    }
    def compare(left, right, a, b, label):
        ids = sorted(set(a).intersection(b))
        good = [i for i in ids if _compatible(a[i], b[i])]
        if not good:
            return
        arr_a = [a[i] for i in good]
        arr_b = [b[i] for i in good]
        sample_a = sorted({int(r["training_examples"]) for r in arr_a
                           if r["training_examples"] is not None})
        sample_b = sorted({int(r["training_examples"]) for r in arr_b
                           if r["training_examples"] is not None})
        scorecard["common_game_comparisons"].append({
            "comparison": label, "left": left, "right": right,
            "same_game_n": len(good),
            "left_training_sample_sizes": sample_a,
            "right_training_sample_sizes": sample_b,
            "historical_training_sample_differs": bool(
                sample_a and sample_b and sample_a != sample_b),
            "left_metrics": _metrics(arr_a), "right_metrics": _metrics(arr_b),
        })
    for i, left in enumerate(v8_models):
        a = {k[1]: r for k, r in v8.items() if k[0] == left}
        for right in v8_models[i+1:]:
            b = {k[1]: r for k, r in v8.items() if k[0] == right}
            compare(left, right, a, b, "V8 version matched-game comparison")
        for right in v7_models:
            b = {k[1]: r for k, r in v7.items() if k[0] == right}
            compare(left, right, a, b, "V8 versus V7 matched-game comparison")
    return scorecard


def read_report(database_url, season):
    """Read-only source tables; never infer/overwrite actual NBA results."""
    if not database_url:
        raise RuntimeError("TRACKER_DATABASE_URL required")
    import psycopg
    with psycopg.connect(database_url, connect_timeout=5) as conn:
        with conn.cursor() as cur:
            cur.execute("SET TRANSACTION READ ONLY")
            cur.execute("SET LOCAL statement_timeout = '5000ms'")
            cur.execute(
                """SELECT game_id,model_id,issued_at,start_utc,home,away,
                          actual_home,actual_away,settled_at,scenario_home,
                          scenario_away,mean_home,mean_away,home_win_pct,
                          training_examples,report
                     FROM hoopzaro_v8_shadow_forecasts WHERE season=%s
                     ORDER BY model_id,game_id""", (season,))
            v8_cols = [c.name for c in cur.description]
            v8_rows = [dict(zip(v8_cols, r)) for r in cur.fetchall()]
            cur.execute(
                """SELECT game_id,model_id,forecast_time_utc,start_utc,home,away,
                          home_score,away_score,settled_at_utc,
                          home_points,away_points,home_win_pct
                     FROM bestbets_forecasts_by_model WHERE season=%s
                       AND model_id IN ('auto_legacy_v72',
                                        'auto_research_form_v74',
                                        'auto_context_full_v75',
                                        'auto_shadow_home_v76')
                     ORDER BY model_id,game_id""", (season,))
            v7_cols = [c.name for c in cur.description]
            v7_rows = [dict(zip(v7_cols, r)) for r in cur.fetchall()]
    result = evaluate_records(v8_rows, v7_rows)
    result["season"] = season
    result["data_source"] = "append-only pregame V8 + pregame V7 Neon archives"
    return result


def main():
    now = pd.Timestamp.now(tz="UTC")
    year = now.year if now.month >= 10 else now.year - 1
    season = f"{year}-{(year+1) % 100:02d}"
    result = read_report(os.environ.get("TRACKER_DATABASE_URL", ""), season)
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
