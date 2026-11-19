"""Offline regressions for prospective NBA player projections and settlement."""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

import pandas as pd

from player_simulation_tracker import (MODEL_ID, build_player_forecasts,
                                       player_model_report)
from tracker_automation import run_player_cycle
import tracker_postgres


NOW = pd.Timestamp("2026-11-19T01:00:00Z")
GAME = {"game_id": "401001234", "start_utc": NOW + pd.Timedelta(hours=2),
        "home": "BOS", "away": "NYK", "status_code": 1}


def raw_logs():
    return pd.DataFrame([
        {"TEAM_ABBREVIATION": team, "PLAYER_NAME": name, "PLAYER_ID": pid,
         "GAME_ID": f"{team}-{day}", "GAME_DATE": NOW-pd.Timedelta(days=day),
         "PTS": 15, "REB": 4, "AST": 3, "FG3M": 2, "MIN": 30}
        for team, name, pid in (("BOS", "Example Starter", "123"),
                                ("NYK", "Example Guard", "456"))
        for day in (1, 2, 3, 4)
    ])


def projections():
    return pd.DataFrame([
        {"Zawodnik": "Example Starter", "Drużyna": "BOS", "PTS": 21.5,
         "REB": 5.5, "AST": 4.5, "3PM": 2.0, "Minuty": 30.0,
         "Próba występów": 7},
        {"Zawodnik": "Example Guard", "Drużyna": "NYK", "PTS": 17.5,
         "REB": 3.5, "AST": 8.0, "3PM": 1.5, "Minuty": 32.0,
         "Próba występów": 7},
    ])


class PlayerSnapshotsTest(unittest.TestCase):
    def setUp(self):
        self.history = pd.DataFrame([{"game_id": "401000111", "status_code": 3,
                                      "start_utc": NOW-pd.Timedelta(days=2),
                                      "home": "BOS", "away": "NYK",
                                      "home_score": 105, "away_score": 103}])

    def _build(self, future=GAME, raw=None):
        logs = raw_logs() if raw is None else raw
        with patch("core.normalize_logs", side_effect=lambda frame: frame), \
             patch("simulation_engine.completed_team_scores", return_value={}), \
             patch("simulation_engine.matchup_means", return_value={
                 "home": 110.0, "away": 107.0, "source": "test"}), \
             patch("simulation_engine.eligible_roster", side_effect=lambda *args, **kwargs:
                   pd.DataFrame([{"player": "Test", "PTS": 10.0}])), \
             patch("simulation_engine.simulate_game", return_value=(
                 {}, projections(), [], [])) as simulate:
            rows, coverage = build_player_forecasts(
                pd.DataFrame([future]), self.history, NOW,
                fetch_logs=lambda *_a, **_kw: (logs, {}))
        return rows, coverage, simulate

    def test_freezes_two_real_id_linked_players_before_tipoff(self):
        rows, coverage, simulate = self._build()
        self.assertEqual(coverage, {"attempted_games": 1, "projected_games": 1})
        self.assertEqual(len(rows), 2)
        self.assertEqual({row["player_id"] for row in rows}, {"123", "456"})
        self.assertEqual({row["model_id"] for row in rows}, {MODEL_ID})
        self.assertEqual(rows[0]["pts_pred"], 21.5)
        self.assertEqual(rows[0]["sample_games"], 7)
        simulate.assert_called_once()

    def test_never_predicts_after_tipoff(self):
        rows, coverage, simulate = self._build({**GAME, "start_utc": NOW-pd.Timedelta(minutes=1)})
        self.assertEqual(rows, [])
        self.assertEqual(coverage["attempted_games"], 0)
        simulate.assert_not_called()

    def test_rejects_ambiguous_player_id_instead_of_name_guess(self):
        logs = raw_logs()
        logs.loc[0, "PLAYER_ID"] = "other-id"
        rows, _, _ = self._build(raw=logs)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["player_id"], "456")

    def test_missing_boxscore_history_does_not_create_fake_projections(self):
        logs = raw_logs().iloc[:2]
        rows, coverage, _ = self._build(raw=logs)
        self.assertEqual(rows, [])
        self.assertEqual(coverage["projected_games"], 0)

    def test_real_simulator_builds_frozen_player_rows_without_network(self):
        history = pd.DataFrame([
            {"game_id": str(401000100 + day), "status_code": 3,
             "start_utc": NOW-pd.Timedelta(days=day),
             "home": "BOS", "away": "NYK",
             "home_score": 105 + day, "away_score": 103 + day}
            for day in range(1, 7)
        ])
        results, coverage = build_player_forecasts(
            pd.DataFrame([GAME]), history, NOW,
            fetch_logs=lambda *_a, **_kw: (raw_logs(), {"coverage": "4/4"}))
        self.assertEqual(coverage["projected_games"], 1)
        self.assertEqual({r["player_id"] for r in results}, {"123", "456"})
        self.assertTrue(all(r["pts_pred"] >= 0 and r["minutes_pred"] > 0
                            for r in results))


class PerformanceMetricsTest(unittest.TestCase):
    def test_only_pregame_played_player_games_count_toward_accuracy(self):
        frame = pd.DataFrame([
            {"game_id": "1", "player_id": "10", "player_name": "A", "team": "BOS",
             "model_id": MODEL_ID, "forecast_time_utc": NOW-pd.Timedelta(hours=2),
             "start_utc": NOW, "pts_pred": 20, "pts_actual": 25,
             "reb_pred": 7, "reb_actual": 4, "ast_pred": 4, "ast_actual": 6,
             "fg3m_pred": 2, "fg3m_actual": None},
            {"game_id": "1", "player_id": "11", "player_name": "B", "team": "NYK",
             "model_id": MODEL_ID, "forecast_time_utc": NOW-pd.Timedelta(hours=2),
             "start_utc": NOW, "pts_pred": 12, "pts_actual": None,
             "reb_pred": 4, "reb_actual": None, "ast_pred": 5, "ast_actual": None,
             "fg3m_pred": 1, "fg3m_actual": None},
            {"game_id": "2", "player_id": "12", "player_name": "C", "team": "BOS",
             "model_id": MODEL_ID, "forecast_time_utc": NOW+pd.Timedelta(hours=1),
             "start_utc": NOW, "pts_pred": 10, "pts_actual": 70,
             "reb_pred": 3, "reb_actual": 30, "ast_pred": 2, "ast_actual": 10},
        ])
        report = player_model_report(frame, season="2026-27")["models"][0]
        self.assertEqual(report["saved"], 2)
        self.assertEqual(report["evaluated_players"], 1)
        self.assertEqual(report["games_with_results"], 1)
        self.assertEqual(report["metrics"]["pts"], {
            "n": 1, "mae": 5.0, "bias": 5.0,
            "within_pct": 1.0, "tolerance": 5.0})
        self.assertEqual(report["metrics"]["fg3m"]["n"], 0)


class PlayerDatabaseTest(unittest.TestCase):
    def test_database_is_append_only_and_refuses_late_or_invalid_forecasts(self):
        conn = MagicMock()
        conn.__enter__.return_value = conn
        conn.execute.return_value.rowcount = 1
        good = {"game_id": GAME["game_id"], "start_utc": GAME["start_utc"],
                "player_id": "123", "model_id": MODEL_ID, "team": "BOS",
                "player_name": "Example Starter", "sample_games": 7,
                "source": "ESPN", "pts_pred": 21.5, "reb_pred": 5.5,
                "ast_pred": 4.5, "fg3m_pred": 2.0, "minutes_pred": 30.0}
        with patch.object(tracker_postgres, "connect", return_value=conn), \
             patch.object(tracker_postgres, "init_remote"):
            result = tracker_postgres.remote_store_players(
                "ignored", "2026-27", [good,
                    {**good, "start_utc": NOW-pd.Timedelta(hours=1)},
                    {**good, "player_id": "fake"}], captured_at=NOW)
        self.assertEqual(result["saved"], 1)
        self.assertEqual(result["duplicates_or_rejected"], 2)
        self.assertIn("ON CONFLICT", conn.execute.call_args_list[0].args[0])

    def test_only_matching_final_boxscore_player_can_be_settled(self):
        conn = MagicMock()
        conn.__enter__.return_value = conn
        conn.execute.return_value.fetchall.return_value = [(GAME["game_id"],)]
        conn.execute.return_value.rowcount = 1
        finals = pd.DataFrame([{**GAME, "status_code": 3,
                                "start_utc": NOW-pd.Timedelta(hours=3),
                                "home_score": 110, "away_score": 99}])
        boxscore = [{"GAME_ID": GAME["game_id"], "PLAYER_ID": "123",
                     "TEAM_ABBREVIATION": "BOS", "PTS": 24,
                     "REB": 6, "AST": 4, "FG3M": float("nan"), "MIN": 33},
                    {"GAME_ID": GAME["game_id"], "PLAYER_ID": "456",
                     "TEAM_ABBREVIATION": "NYK", "PTS": 0,
                     "REB": 0, "AST": 0, "MIN": 0}]
        with patch.object(tracker_postgres, "connect", return_value=conn), \
             patch.object(tracker_postgres, "init_remote"):
            matched = tracker_postgres.remote_settle_players(
                "ignored", finals, fetch_boxscore=lambda g: boxscore, settled_at=NOW)
        self.assertEqual(matched, 1)
        updates = [c for c in conn.execute.call_args_list if "UPDATE bestbets_player_forecasts" in c.args[0]]
        self.assertEqual(len(updates), 1)
        self.assertEqual(updates[0].args[1][3], None)
        self.assertIn("forecast_time_utc < start_utc", updates[0].args[0])


class PipelineTest(unittest.TestCase):
    def test_player_cycle_is_independent_and_idempotent_friendly(self):
        source = pd.DataFrame([{**GAME}])
        with patch("player_simulation_tracker.build_player_forecasts",return_value=(
            [{"player_id": "123"}], {"attempted_games": 1, "projected_games": 1})):
            output = run_player_cycle(
                source, pd.DataFrame(), NOW,
                save_player_forecasts=lambda rows, season: {"saved": 1},
                settle_player_results=lambda completed: 2,
                season="2026-27")
        self.assertEqual(output["new_player_snapshots"], 1)
        self.assertEqual(output["player_rows_settled"], 2)
        self.assertEqual(output["model_id"], MODEL_ID)


if __name__ == "__main__":
    unittest.main()
