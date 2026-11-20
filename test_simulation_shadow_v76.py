"""Pregame-only tests for the separate V7.6 shadow experiment."""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

import pandas as pd

from simulation_shadow_v76 import (
    SHADOW_PLAYER_MODEL_ID, SHADOW_TEAM_MODEL_ID, shadow_home_means,
    shadow_minutes_projection, shadow_roster_minutes,
)
from test_tracker_v720 import fixture
from tracker_automation import build_automatic_forecasts, upcoming_events
from player_simulation_tracker import MODEL_ID, build_player_forecasts
import tracker_postgres


NOW = pd.Timestamp("2026-11-20T01:00:00Z")
START = NOW + pd.Timedelta(hours=2)


def player_logs():
    samples = []
    for team, name, athlete in (("BOS", "Test Starter", "123"),
                                ("NYK", "Test Guard", "456")):
        for day in range(8, 0, -1):
            samples.append({
                "GAME_DATE": NOW - pd.Timedelta(days=day),
                "GAME_ID": f"{team}-{day}",
                "PLAYER_NAME": name, "PLAYER_ID": athlete,
                "TEAM_ABBREVIATION": team,
                "MIN": 18 if day > 3 else 34,
                "PTS": 10 if day > 3 else 20,
                "REB": 4, "AST": 3, "FG3M": 1,
            })
    return pd.DataFrame(samples)


class ShadowHypothesisTest(unittest.TestCase):
    def test_home_variant_does_not_change_total_or_modify_v75(self):
        old = {"home": 117.5, "away": 110.25, "source": "ESPN"}
        new = shadow_home_means(old)
        self.assertEqual(old["home"], 117.5)
        self.assertEqual(old["away"], 110.25)
        self.assertAlmostEqual(new["home"] + new["away"], 227.75)
        self.assertAlmostEqual(new["home"], 116.75)
        self.assertAlmostEqual(new["away"], 111.0)
        self.assertIn("shadow", new["source"])

    def test_minute_trend_is_bounded_and_small_samples_stay_unchanged(self):
        logs = player_logs()
        one = logs[logs["PLAYER_NAME"].eq("Test Starter")]
        shadow = shadow_minutes_projection(one)
        self.assertGreater(shadow, 25)
        self.assertLessEqual(shadow, 42)
        short = one.tail(4)
        from core import minutes_projection
        self.assertEqual(shadow_minutes_projection(short), minutes_projection(short))

    def test_roster_adjustment_preserves_source_and_excludes_future_rows(self):
        logs = player_logs()
        roster = pd.DataFrame([{
            "player": "Test Starter", "team": "BOS", "minutes": 25,
            "PTS": 14, "REB": 5, "AST": 4, "FG3M": 2,
        }])
        before = shadow_roster_minutes(roster, logs, captured_at=NOW, tipoff=START)
        self.assertEqual(roster.loc[0, "minutes"], 25)
        self.assertGreater(before.loc[0, "minutes"], 25)
        self.assertAlmostEqual(before.loc[0, "PTS"] / roster.loc[0, "PTS"],
                               before.loc[0, "minutes"] / 25, places=2)
        future = pd.concat([logs, pd.DataFrame([{
            "GAME_DATE": NOW + pd.Timedelta(minutes=10),
            "PLAYER_NAME": "Test Starter", "TEAM_ABBREVIATION": "BOS",
            "MIN": 48,
        }])], ignore_index=True)
        after = shadow_roster_minutes(roster, future, captured_at=NOW, tipoff=START)
        pd.testing.assert_frame_equal(before, after)

    def test_shadow_refuses_after_tipoff_input(self):
        with self.assertRaises(ValueError):
            shadow_roster_minutes(pd.DataFrame([{"player": "A"}]), player_logs(),
                                  captured_at=START, tipoff=START)


class SnapshotIsolationTest(unittest.TestCase):
    def test_team_shadow_is_extra_snapshot_from_same_pregame_evidence(self):
        clock = pd.Timestamp("2026-11-10T08:00:00Z")
        history, schedule = fixture(clock)
        schedule = schedule.iloc[[0]].copy()
        schedule.loc[:, "start_utc"] = clock + pd.Timedelta(hours=3)
        events = upcoming_events(schedule, clock)
        original, _ = build_automatic_forecasts(events, history, clock)
        extended, _ = build_automatic_forecasts(
            events, history, clock, include_shadow_v76=True)
        self.assertEqual(len(original), 3)
        self.assertEqual(len(extended), 4)
        self.assertEqual(original, extended[:3])
        shadow = extended[3]
        baseline = extended[2]
        self.assertEqual(shadow["model_id"], SHADOW_TEAM_MODEL_ID)
        self.assertEqual(shadow["game_id"], baseline["game_id"])
        self.assertAlmostEqual(
            shadow["home_points"] + shadow["away_points"],
            baseline["home_points"] + baseline["away_points"], delta=0.9)
        schedule.loc[:, "start_utc"] = clock + pd.Timedelta(hours=9)
        far, _ = build_automatic_forecasts(
            upcoming_events(schedule, clock), history, clock,
            include_shadow_v76=True)
        self.assertEqual(len(far), 2)

    def test_player_shadow_keeps_existing_athletes_and_model(self):
        history = pd.DataFrame([{
            "game_id": str(401000100 + day), "status_code": 3,
            "start_utc": NOW - pd.Timedelta(days=day),
            "home": "BOS", "away": "NYK",
            "home_score": 104 + day, "away_score": 101 + day,
        } for day in range(1, 9)])
        upcoming = pd.DataFrame([{
            "game_id": "401001234", "status_code": 1,
            "start_utc": START, "home": "BOS", "away": "NYK",
        }])
        baseline, coverage = build_player_forecasts(
            upcoming, history, NOW, fetch_logs=lambda *_a, **_k: (player_logs(), {}))
        combined, expanded_coverage = build_player_forecasts(
            upcoming, history, NOW,
            fetch_logs=lambda *_a, **_k: (player_logs(), {}), shadow_v76=True)
        self.assertEqual(coverage, expanded_coverage)
        self.assertEqual(baseline, combined[:len(baseline)])
        self.assertEqual(len(baseline), 2)
        self.assertEqual(len(combined), 4)
        self.assertEqual({x["model_id"] for x in baseline}, {MODEL_ID})
        shadow = [x for x in combined if x["model_id"] == SHADOW_PLAYER_MODEL_ID]
        self.assertEqual({x["player_id"] for x in shadow}, {"123", "456"})
        self.assertTrue(any(a["minutes_pred"] != b["minutes_pred"]
                            for a, b in zip(baseline, shadow)))
        self.assertTrue(all(x["start_utc"] > NOW for x in combined))


class ShadowPersistenceTest(unittest.TestCase):
    def test_postgres_accepts_only_whitelisted_player_models(self):
        conn = MagicMock()
        conn.__enter__.return_value = conn
        conn.execute.return_value.rowcount = 1
        base = {
            "game_id": "401001234", "start_utc": START, "player_id": "123",
            "team": "BOS", "player_name": "Test Starter", "sample_games": 8,
            "pts_pred": 20, "reb_pred": 5, "ast_pred": 4,
            "fg3m_pred": 2, "minutes_pred": 32, "source": "ESPN",
        }
        rows = [
            {**base, "model_id": MODEL_ID},
            {**base, "model_id": SHADOW_PLAYER_MODEL_ID},
            {**base, "model_id": "unapproved_model"},
        ]
        with patch.object(tracker_postgres, "connect", return_value=conn), \
             patch.object(tracker_postgres, "init_remote"):
            result = tracker_postgres.remote_store_players(
                "unused", "2026-27", rows, captured_at=NOW)
        self.assertEqual(result, {"saved": 2, "duplicates_or_rejected": 1})
        inserted = [args.args[1][1] for args in conn.execute.call_args_list]
        self.assertEqual(inserted, [MODEL_ID, SHADOW_PLAYER_MODEL_ID])


if __name__ == "__main__":
    unittest.main()
