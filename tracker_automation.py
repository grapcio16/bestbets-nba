"""Automatic BestBets pregame archive and final-result settlement.

Designed for a scheduled GitHub Actions job with a durable PostgreSQL
TRACKER_DATABASE_URL. Also testable offline without credentials/network.

IMPORTANT: scheduled forecasts use a separate model_id (auto_*) because the
Streamlit page may have NBA Advanced cached while the runner has only ESPN.
They NEVER overwrite forecasts captured in the interactive simulations page.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd

from simulation_data_audit import verified_history
from simulation_engine import (
    completed_team_scores, legacy_matchup_means, matchup_means, simulate_game,
)

AUTO_MODELS = (
    ("auto_legacy_v72", legacy_matchup_means),
    ("auto_research_form_v74", matchup_means),
)


def active_nba_season(now):
    stamp = pd.to_datetime(now, utc=True, errors="coerce")
    if pd.isna(stamp):
        raise ValueError("Nieprawidłowa data UTC")
    year = stamp.year if stamp.month >= 10 else stamp.year - 1
    return f"{year}-{(year + 1) % 100:02d}"


def upcoming_events(schedule, now, horizon_hours=36, min_lead_minutes=15):
    """ESPN scheduled games with enough time to capture a true pregame forecast."""
    required = {"game_id", "home", "away", "start_utc", "status_code"}
    if not isinstance(schedule, pd.DataFrame) or not required.issubset(schedule.columns):
        return pd.DataFrame(columns=sorted(required))
    clock = pd.to_datetime(now, utc=True, errors="coerce")
    if pd.isna(clock):
        raise ValueError("Nieprawidłowa data UTC")
    df = schedule.copy()
    df["start_utc"] = pd.to_datetime(df["start_utc"], utc=True, errors="coerce")
    df["status_code"] = pd.to_numeric(df["status_code"], errors="coerce")
    df = df[(df["status_code"] == 1)
            & (df["start_utc"] > clock + pd.Timedelta(minutes=min_lead_minutes))
            & (df["start_utc"] <= clock + pd.Timedelta(hours=horizon_hours))]
    df = df[df["game_id"].astype(str).str.fullmatch(r"\d{1,20}")]
    df = df.drop_duplicates(subset=["game_id"], keep="first")
    return df.sort_values(["start_utc", "game_id"]).reset_index(drop=True)


def build_automatic_forecasts(upcoming, completed, now):
    """Forecast only on verified results known strictly before job timestamp.

    Models share the exact same clean historical dataset, but have distinct
    identifiers and results. Neither injuries nor missing advanced metrics
    are replaced with guessed modifiers.
    """
    history = verified_history(completed, now)
    grouped = completed_team_scores(history)
    stored = []
    skipped = 0
    for event in upcoming.to_dict("records"):
        g = {
            "game_id": str(event["game_id"]),
            "home": str(event["home"]),
            "away": str(event["away"]),
            "start_utc": event["start_utc"],
        }
        # ESPN states and valid final scores before the scheduled execution;
        # no hindsight and no guessed preseason ratings.
        for model_id, model in AUTO_MODELS:
            mean = model(g["home"], g["away"], {}, grouped)
            if mean is None:
                skipped += 1
                continue
            try:
                outcome, _, _, _ = simulate_game(g, mean)
            except (KeyError, TypeError, ValueError):
                skipped += 1
                continue
            outcome["model_id"] = model_id
            stored.append(outcome)
    return stored, skipped


def run_cycle(schedule, history, now, save_forecasts, settle_results,
              season=None, horizon_hours=36):
    """One idempotent worker cycle; persistence is dependency-injected."""
    stamp = pd.to_datetime(now, utc=True, errors="coerce")
    if pd.isna(stamp):
        raise ValueError("Nieprawidłowa data UTC")
    season = season or active_nba_season(stamp)
    completed = verified_history(history, stamp)
    # Settle first: a partial ESPN schedule failure must not block settlement.
    settled = int(settle_results(completed))
    upcoming = upcoming_events(schedule, stamp, horizon_hours=horizon_hours)
    candidates, skipped = build_automatic_forecasts(upcoming, completed, stamp)
    saved_result = (save_forecasts(candidates, season)
                    if candidates else {"saved": 0, "duplicates_or_rejected": 0})
    return {
        "season": season,
        "checked_at_utc": stamp.isoformat(),
        "final_results_checked": len(completed),
        "matched_forecast_rows_settled": settled,
        "upcoming_games_checked": len(upcoming),
        "candidate_forecast_rows": len(candidates),
        "new_pregame_snapshots": int(saved_result["saved"]),
        "duplicate_or_rejected": int(saved_result.get("duplicates_or_rejected", 0)),
        "insufficient_model_data": skipped,
        "storage": "PostgreSQL",
    }


def run_scheduled_job():
    """No silent SQLite fallback for unattended jobs: disk is ephemeral."""
    from tracker_storage import tracker_backend, save, settle
    from simulation_sources import historical_espn_results
    from sources import espn_schedule

    cfg = tracker_backend()
    if not cfg["remote"]:
        raise RuntimeError(
            "Automatyczny Tracker wymaga TRACKER_DATABASE_URL (GitHub Actions Secret): "
            "bez trwałej bazy prognozy nie przetrwają restartu serwera."
        )
    now = pd.Timestamp.now(tz="UTC")
    season = active_nba_season(now)
    # ESPN data is intentionally refreshed: do not settle against stale cached
    # finals or archive future predictions from unavailable schedules.
    finals, notes = historical_espn_results(
        season, refresh=True, lookback_months=3)
    if notes or finals is None or finals.empty:
        raise RuntimeError(
            "ESPN nie dostarczył aktualnej, kompletnej historii zakończonych meczów. "
            "Nie archiwizujemy ani nie rozliczamy prognoz na niepewnych danych."
        )
    upcoming, meta = espn_schedule(refresh=True)
    if meta.get("stale") or upcoming.empty:
        raise RuntimeError(
            "Niepełny lub nieaktualny terminarz ESPN. "
            "Ponowne wykonanie nastąpi przy następnym harmonogramie."
        )
    # No DB URL/credentials in printed summaries, logs, or thrown errors.
    return run_cycle(
        upcoming, finals, now,
        save_forecasts=lambda snapshots, target_season: save(
            snapshots, target_season, config=cfg),
        settle_results=lambda completed: settle(completed, config=cfg),
        season=season,
    )


if __name__ == "__main__":
    import json
    print(json.dumps(run_scheduled_job(), ensure_ascii=False))
