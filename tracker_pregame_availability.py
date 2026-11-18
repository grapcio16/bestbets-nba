"""On-demand, bounded pregame evidence for the unified V7.5 forecast.

ESPN injuries are an unofficial source. This module creates a research
snapshot only when both teams have enough actual pregame boxscores and the
injury feed was recently fetched. It never infers who is healthy from an
absent injury entry. Missing evidence leaves the venue/rest baseline intact.
"""
from __future__ import annotations

import pandas as pd

from availability_context import matchup_injuries
from core import normalize_logs
from simulation_availability_v75 import availability_evidence
from simulation_context_v2 import simulation_inputs
from simulation_engine import eligible_roster, simulate_game

INJURY_AWARE_MODEL_ID = "auto_context_injury_minutes_v75"
MAX_LEAD_HOURS = 6
MIN_MINUTE_COVERAGE = 5  # per team, with >=3 real games each


def near_tipoff(game, now, *, max_lead_hours=MAX_LEAD_HOURS):
    """Take snapshots 15 min–6 h pregame, not a day before injury decisions."""
    start = pd.to_datetime(game.get("start_utc"), utc=True, errors="coerce")
    at = pd.to_datetime(now, utc=True, errors="coerce")
    if pd.isna(start) or pd.isna(at):
        return False
    lead = (start - at).total_seconds()
    return 15 * 60 < lead <= max_lead_hours * 3600


class PregameAvailabilityFeed:
    """Fetch ESPN injury records once per cycle, and boxscores per matchup.

    No Streamlit session, credentials, or browser is required in GitHub Actions.
    Source failures are confined to the injury adjustment; the combined V7.5
    venue/rest fallback and other automatic models remain available.
    """

    def __init__(self, *, clock=None):
        self._injury_snapshot = None
        self._injury_checked = False
        self._clock = clock or (lambda: pd.Timestamp.now(tz="UTC"))

    def _injuries(self):
        if not self._injury_checked:
            self._injury_checked = True
            from sources import injuries
            self._injury_snapshot = injuries(refresh=True)
        return self._injury_snapshot

    def __call__(self, game, history, now):
        if not near_tipoff(game, now):
            return None
        try:
            raw_injuries, raw_meta = self._injuries()
            if raw_meta.get("stale") or not raw_meta.get("timestamp"):
                return None
            injury_rows, injury_meta = matchup_injuries(
                raw_injuries, game["home"], game["away"], raw_meta)
            if not injury_meta.get("available"):
                return None

            from espn_player_data import matchup_espn_logs
            selected, source = matchup_espn_logs(history, game, games_per_team=7)
            if selected.empty:
                return None
            logs = normalize_logs(selected)
            # ESPN can miss one of fourteen final boxscores. Keep only the
            # observed rows and require a real four-game minimum per team;
            # never treat a partially loaded feed as a full seven-game sample.
            if any(logs[logs["TEAM_ABBREVIATION"] == code]["GAME_ID"].nunique() < 4
                   for code in (game["home"], game["away"])):
                return None
            home = eligible_roster(
                logs, game["home"], game["away"], asof=game["start_utc"])
            away = eligible_roster(
                logs, game["away"], game["home"], asof=game["start_utc"])
            if min(len(home), len(away)) < MIN_MINUTE_COVERAGE:
                return None

            baseline = simulation_inputs(history, game)
            if baseline["means"] is None:
                return None
            _, projected_players, _, _ = simulate_game(
                game, baseline["means"], home, away,
                score_noise=baseline["score_noise"])
            if projected_players is None or projected_players.empty:
                return None

            # Use actual retrieval time: the feed may have been fetched after
            # the schedule runner's original clock was recorded. The database
            # captures the resulting forecast only AFTER all evidence exists.
            verified_at = self._clock()
            if not near_tipoff(game, verified_at):
                return None
            evidence = availability_evidence(
                projected_players, injury_rows,
                {**raw_meta, "available": injury_meta["available"]}, game,
                logs=logs, now=verified_at)
            coverage = evidence["minute_coverage"]
            if (not evidence["report_fresh"] or
                    min(coverage["home"], coverage["away"]) < MIN_MINUTE_COVERAGE):
                return None
            evidence["snapshot_utc"] = str(raw_meta["timestamp"])
            evidence["boxscore_coverage"] = str(source.get("coverage") or "")[:100]
            evidence["boxscores_partial"] = bool(source.get("stale"))
            return evidence
        except (OSError, RuntimeError, ValueError, TypeError, KeyError,
                ConnectionError, TimeoutError):
            return None
