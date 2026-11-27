"""Independent, opt-in V8 research job.

Never changes existing V7 game/player/quarter models, their model IDs or
public Premium UI. Uses only the schedule + historical finals as transport;
all feature engineering, math, calibration and storage are V8-only.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone

import pandas as pd

from v8_shadow.data import collect_team_boxes
from v8_shadow.engine import VERSION, predict_v8
from v8_shadow.readiness import audit_evidence
from v8_shadow.storage import (
    initialize, ids, read_boxes, record_ingest_failures, record_worker_run,
    save_forecasts, settle_forecasts, store_boxes
)


def season_for(now):
    timestamp = pd.to_datetime(now, utc=True)
    year = timestamp.year if timestamp.month >= 10 else timestamp.year - 1
    return f"{year}-{(year + 1) % 100:02d}"


def eligible_upcoming(schedule, now):
    if schedule is None or schedule.empty:
        return []
    required = {"game_id","start_utc","home","away","status_code"}
    if not required.issubset(schedule.columns):
        return []
    valid = schedule.copy()
    valid["start_utc"] = pd.to_datetime(valid["start_utc"],utc=True,errors="coerce")
    valid["status_code"] = pd.to_numeric(valid["status_code"],errors="coerce")
    valid = valid[(valid["status_code"]==1) &
        (valid["start_utc"] > now + pd.Timedelta(minutes=20)) &
        (valid["start_utc"] <= now + pd.Timedelta(hours=36))]
    valid = valid.sort_values("start_utc").drop_duplicates("game_id")
    return valid.to_dict("records")


def collect_v803(evidence, selected, asof, *, enabled, ready, predict=None, now=None):
    """Same evidence snapshot for all games; never archive an expired candidate."""
    if not enabled or not ready:
        return [], {}
    if predict is None:
        from v8_shadow.engine_v803 import predict_v803
        predict = predict_v803
    if now is None:
        now = lambda: pd.Timestamp.now(tz="UTC")
    forecasts, skipped = [], {}
    lead = pd.Timedelta(minutes=15)
    def reject(reason):
        skipped[reason] = skipped.get(reason, 0) + 1
    for event in selected:
        game = {"game_id": str(event["game_id"]), "start_utc": event["start_utc"],
                "home": str(event["home"]), "away": str(event["away"])}
        tip = pd.to_datetime(game["start_utc"], utc=True)
        if tip <= now() + lead:
            reject("expired_before_compute")
            continue
        try:
            result = predict(evidence, game, asof, n=5000)
            if tip <= now() + lead:
                reject("expired_after_compute")
            elif result["status"] == "shadow_only":
                forecasts.append(result)
            else:
                reject(result["status"])
        except (ValueError, KeyError, TypeError) as exc:
            reject(type(exc).__name__)
    return forecasts, skipped


def run():
    url = os.environ.get("TRACKER_DATABASE_URL", "").strip()
    if not url:
        raise RuntimeError("V8 Shadow requires durable Neon URL: TRACKER_DATABASE_URL")
    # Existing external adapters only. Do not import or reuse V7 mathematics.
    from simulation_sources import historical_espn_results
    from sources import espn_schedule
    now = pd.Timestamp.now(tz="UTC")
    season = season_for(now)
    finals, warnings = historical_espn_results(
        season, refresh=True, lookback_months=3)
    if warnings or finals is None or finals.empty:
        raise RuntimeError("V8 cannot build a research dataset from stale ESPN finals")
    schedule, meta = espn_schedule(refresh=True)
    if schedule is None or schedule.empty or meta.get("stale"):
        raise RuntimeError("V8 cannot archive forecasts against a stale NBA schedule")
    initialize(url)
    done = finals.copy()
    done["season"] = season
    archived = ids(url, season)
    limit = int(os.environ.get("HOOPZARO_V8_BOX_FETCH_LIMIT", "18"))
    accepted, provenance = collect_team_boxes(done, archived, limit=limit)
    stored = store_boxes(url, accepted)
    record_ingest_failures(url, season, provenance.get("rejections") or [])
    evidence = read_boxes(url, season)
    # Get a current clock AFTER network activity; do not create now-outdated
    # forecasts just because the fetch originally began before kickoff.
    clock = pd.Timestamp.now(tz="UTC")
    selected = eligible_upcoming(schedule, clock)
    readiness = audit_evidence(evidence, clock)
    forecast = []
    skipped = {}
    if not readiness['ready_for_eligible_matchups']:
        skipped['chronological_history_incomplete'] = len(selected)
    for event in (selected if readiness['ready_for_eligible_matchups'] else []):
        game = {"game_id": str(event["game_id"]),
                "start_utc": event["start_utc"],
                "home": str(event["home"]), "away": str(event["away"])}
        try:
            result = predict_v8(evidence, game, clock, n=5000)
        except (ValueError, KeyError, TypeError) as exc:
            key = type(exc).__name__
            skipped[key] = skipped.get(key, 0) + 1
            continue
        if result["status"] == "shadow_only":
            forecast.append(result)
        else:
            key = result["status"]
            skipped[key] = skipped.get(key, 0) + 1
    # Persist baseline first; V8.03 must not delay V8.02 collection.
    new = save_forecasts(url, forecast, season)
    v803_enabled = os.environ.get("HOOPZARO_V803_ENABLED", "").strip() == "true"
    v803_forecasts, v803_skipped = [], {}
    v803_history_count = None
    if v803_enabled:
        from v8_shadow.season_gate import calendar_supported, filter_regular_window
        if not calendar_supported(season):
            v803_skipped["unsupported_season_calendar"] = len(selected)
        else:
            regular_history = filter_regular_window(evidence, season)
            regular_upcoming = filter_regular_window(selected, season)
            v803_history_count = len(regular_history)
            v803_forecasts, v803_skipped = collect_v803(
                regular_history, regular_upcoming, clock, enabled=True,
                ready=readiness["ready_for_eligible_matchups"])
            excluded = len(selected) - len(regular_upcoming)
            if excluded:
                v803_skipped["outside_regular_window"] = excluded
    v803_new = save_forecasts(url, v803_forecasts, season) if v803_forecasts else 0
    settled = settle_forecasts(url, finals.to_dict("records"))
    return {
        "model_id": VERSION,
        "status": "research_only_not_in_premium",
        "season": season, "boxscore_ingest": provenance,
        "new_boxscore_games": stored, "boxscore_history_games": len(evidence),
        "upcoming_games_checked": len(selected),
        "new_shadow_forecasts": new,
        "shadow_forecasts_calculated": len(forecast),
        "model_skips": skipped,
        "v803": {"enabled": v803_enabled, "calculated": len(v803_forecasts),
                 "archived": v803_new, "regular_history_games": v803_history_count,
                 "skipped": v803_skipped},
        "settlement": settled,
        "no_v7_changes": True,
        "source_licensing": "research only: commercial rights not yet confirmed",
    }


if __name__ == "__main__":
    print(json.dumps(run(),ensure_ascii=False,default=str))
