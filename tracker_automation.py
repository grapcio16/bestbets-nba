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
from simulation_context_v75 import simulation_inputs_v75
from simulation_engine import (
    completed_team_scores, legacy_matchup_means, matchup_means, simulate_game,
)
from tracker_pregame_availability import (
    MIN_MINUTE_COVERAGE, PregameAvailabilityFeed, near_tipoff,
)

# Exactly one new V7.5 snapshot per game. Historical v75 IDs remain in the
# database and are combined only in the read-only administrator report.
UNIFIED_V75_MODEL_ID = "auto_context_full_v75"

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


def build_automatic_forecasts(upcoming, completed, now, *, availability_provider=None):
    """Forecast only on verified pregame evidence, one V7.5 per match.

    V7.2 and V7.4 retain their independent snapshots. V7.5 is frozen near
    tipoff so a fresh injury/minutes snapshot can be used when verified; if
    unavailable, its venue/rest baseline is still valid and explicitly marked.
    Neither variant is written twice under different V7.5 IDs.
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
            try:
                mean = model(g["home"], g["away"], {}, grouped)
                if mean is None:
                    skipped += 1
                    continue
                outcome, _, _, _ = simulate_game(g, mean)
            except (KeyError, TypeError, ValueError):
                skipped += 1
                continue
            outcome["model_id"] = model_id
            stored.append(outcome)
        # The new combined V7.5 is saved only once, inside the same pregame
        # window used to fetch fresh injuries. Otherwise the first (up to 36h
        # early) venue-only snapshot would permanently block an injury-aware
        # version through the database's append-only unique constraint.
        if not near_tipoff(g, now):
            continue
        try:
            evidence = (availability_provider(g, history, now)
                        if availability_provider is not None else None)
        except (KeyError, TypeError, ValueError, RuntimeError, OSError,
                ConnectionError, TimeoutError):
            # ESPN failures must not erase the venue/rest projection.
            evidence = None
        try:
            covered = (evidence or {}).get("minute_coverage") or {}
            enhanced = bool(
                evidence and evidence.get("report_fresh") and
                min(float(covered.get("home") or 0),
                    float(covered.get("away") or 0)) >= MIN_MINUTE_COVERAGE)
            enriched = simulation_inputs_v75(
                history, g, availability=evidence if enhanced else None)
            if enriched["means"] is None:
                skipped += 1
                continue
            outcome, _, _, _ = simulate_game(
                g, enriched["means"], score_noise=enriched["score_noise"])
            impact = enriched["context"]["v75_factors"]
            provenance = ("V7.5 pełny kontekst: dom/wyjazd + odpoczynek; "
                          + (f"ESPN OUT A/H: {impact['injury_out_away']}/{impact['injury_out_home']}; "
                             f"korekta A/H: {impact['injury_away_pts']}/{impact['injury_home_pts']} pkt; "
                             f"minuty A/H: {covered['away']}/{covered['home']}; "
                             f"raport: {str(evidence.get('snapshot_utc') or '')[:25]}; "
                             + ("boxscore częściowe; " if evidence.get("boxscores_partial") else "")
                             + "nieoficjalne, niekalibrowane"
                             if enhanced else "brak zweryfikowanego raportu ESPN / minut; "
                                             "bez korekty kontuzji"))
            outcome["model_id"] = UNIFIED_V75_MODEL_ID
            outcome["warning"] = provenance
            stored.append(outcome)
        except (KeyError, TypeError, ValueError, RuntimeError, OSError):
            skipped += 1
    return stored, skipped


def run_cycle(schedule, history, now, save_forecasts, settle_results,
              season=None, horizon_hours=36, availability_provider=None):
    """One idempotent worker cycle; persistence is dependency-injected."""
    stamp = pd.to_datetime(now, utc=True, errors="coerce")
    if pd.isna(stamp):
        raise ValueError("Nieprawidłowa data UTC")
    season = season or active_nba_season(stamp)
    completed = verified_history(history, stamp)
    # Settle first: a partial ESPN schedule failure must not block settlement.
    settled = int(settle_results(completed))
    upcoming = upcoming_events(schedule, stamp, horizon_hours=horizon_hours)
    candidates, skipped = build_automatic_forecasts(
        upcoming, completed, stamp,
        availability_provider=availability_provider)
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


def run_player_cycle(schedule, history, now, save_player_forecasts,
                     settle_player_results, season=None, fetch_logs=None):
    """Independent prospective evaluation of the existing player projections.

    Player tracking cannot overwrite or alter team-score forecasts. Missing
    ESPN boxscores remain ungraded instead of being treated as zero points.
    """
    from player_simulation_tracker import build_player_forecasts

    stamp = pd.to_datetime(now, utc=True, errors="coerce")
    if pd.isna(stamp):
        raise ValueError("Nieprawidłowa data UTC")
    season = season or active_nba_season(stamp)
    completed = verified_history(history, stamp)
    matched = int(settle_player_results(completed))
    upcoming = upcoming_events(schedule, stamp)
    kwargs = {"fetch_logs": fetch_logs} if fetch_logs is not None else {}
    forecasts, coverage = build_player_forecasts(upcoming, completed, stamp, **kwargs)
    stored = (save_player_forecasts(forecasts, season) if forecasts
              else {"saved": 0, "duplicates_or_rejected": 0})
    return {
        "model_id": "auto_player_form_v74",
        "pregame_games_checked": coverage["attempted_games"],
        "games_with_player_projections": coverage["projected_games"],
        "candidate_player_rows": len(forecasts),
        "new_player_snapshots": int(stored["saved"]),
        "player_rows_settled": matched,
        "duplicates_or_rejected": int(stored.get("duplicates_or_rejected", 0)),
    }


def run_scheduled_job():
    """No silent SQLite fallback for unattended jobs: disk is ephemeral."""
    from tracker_storage import (tracker_backend, save, settle,
                                 save_players, settle_players, record_tracker_run)
    cfg = tracker_backend()
    if not cfg["remote"]:
        raise RuntimeError(
            "Automatyczny Tracker wymaga TRACKER_DATABASE_URL (GitHub Actions Secret): "
            "bez trwałej bazy prognozy nie przetrwają restartu serwera."
        )
    from simulation_sources import historical_espn_results
    from sources import espn_schedule
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
    # Refresh the decision clock after the external fetches: a slow schedule
    # must not turn an already started game into a new pregame prediction.
    now = pd.Timestamp.now(tz="UTC")
    # No DB URL/credentials in printed summaries, logs, or thrown errors.
    result = run_cycle(
        upcoming, finals, now,
        save_forecasts=lambda snapshots, target_season: save(
            snapshots, target_season, config=cfg),
        settle_results=lambda completed: settle(completed, config=cfg),
        season=season,
        availability_provider=PregameAvailabilityFeed(),
    )
    try:
        result["player_tracking"] = run_player_cycle(
            upcoming, finals, pd.Timestamp.now(tz="UTC"),
            save_player_forecasts=lambda records, target_season: save_players(
                records, target_season, config=cfg),
            settle_player_results=lambda completed: settle_players(
                completed, config=cfg),
            season=season,
        )
    except (ValueError, TypeError, KeyError, RuntimeError, OSError,
            ConnectionError, TimeoutError) as exc:
        # Preserve the finished team-tracker cycle, but make a player-side
        # outage visible in logs without printing credentials or user data.
        result["player_tracking"] = {
            "status": "temporarily_unavailable", "error_type": type(exc).__name__}
    try:
        result["monitoring"] = record_tracker_run(result, config=cfg)
    except (ValueError, TypeError, KeyError, RuntimeError, OSError,
            ConnectionError, TimeoutError) as exc:
        # A heartbeat failure is visible in the worker summary, but must not
        # roll back correctly frozen game/player predictions.
        result["monitoring"] = {
            "recorded": False, "error_type": type(exc).__name__}
    return result


if __name__ == "__main__":
    import json
    print(json.dumps(run_scheduled_job(), ensure_ascii=False))
