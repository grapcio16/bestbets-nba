"""One combined V7.5 model with optional verified injury/minute evidence."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from performance_tracker import read_forecasts, settle_forecasts, store_forecasts
from test_tracker_v720 import fixture
from tracker_automation import (
    UNIFIED_V75_MODEL_ID, build_automatic_forecasts, run_cycle, upcoming_events,
)
from tracker_pregame_availability import (
    PregameAvailabilityFeed, near_tipoff,
)


class EnhancedTrackerTests(unittest.TestCase):
    def setUp(self):
        self.now = pd.Timestamp("2026-11-10T08:00:00Z")
        self.history, schedule = fixture(self.now)
        self.schedule = schedule.iloc[[0]].copy()
        self.schedule.loc[:, "start_utc"] = self.now + pd.Timedelta(hours=3)

    def provider(self, *_):
        return {
            "report_fresh": True,
            "score_delta": {"home": -2.5, "away": 0.0},
            "out_count": {"home": 1, "away": 0},
            "uncertain_count": {"home": 0, "away": 1},
            "minute_coverage": {"home": 7, "away": 8},
            "snapshot_utc": "2026-11-10T07:55:00Z",
            "warning": "ESPN: badawcze i nieoficjalne",
        }

    def test_single_v75_merges_context_and_verified_injury_effect(self):
        chosen = upcoming_events(self.schedule, self.now)
        before, _ = build_automatic_forecasts(chosen, self.history, self.now)
        after, _ = build_automatic_forecasts(
            chosen, self.history, self.now, availability_provider=self.provider)
        self.assertEqual(len(before), 3)
        self.assertEqual(len(after), 3)
        self.assertEqual(after[:2], before[:2])
        injury = next(row for row in after if row["model_id"] == UNIFIED_V75_MODEL_ID)
        team_only = next(row for row in before if row["model_id"] == UNIFIED_V75_MODEL_ID)
        # The seeded 5,000-draw Monte Carlo changes its draw sequence when
        # the mean changes, so allow small, genuine sampling noise.
        self.assertAlmostEqual(injury["home_points"], team_only["home_points"] - 2.5, delta=0.7)
        self.assertIn("korekta A/H", injury["warning"])
        self.assertEqual(injury["game_id"], team_only["game_id"])
        self.assertEqual(sum(row["model_id"] == UNIFIED_V75_MODEL_ID for row in after), 1)

    def test_stale_or_missing_evidence_keeps_venue_rest_fallback(self):
        chosen = upcoming_events(self.schedule, self.now)
        for fake in (None, {**self.provider(), "report_fresh": False},
                     {**self.provider(), "minute_coverage": {"home": 3, "away": 8}}):
            with self.subTest(evidence=fake):
                rows, _ = build_automatic_forecasts(
                    chosen, self.history, self.now,
                    availability_provider=lambda *_: fake)
                self.assertEqual(len(rows), 3)
                self.assertEqual(rows[-1]["model_id"], UNIFIED_V75_MODEL_ID)
                self.assertIn("bez korekty kontuzji", rows[-1]["warning"])
        too_far = self.schedule.copy()
        too_far.loc[:, "start_utc"] = self.now + pd.Timedelta(hours=9)
        called = []
        rows, _ = build_automatic_forecasts(
            upcoming_events(too_far, self.now), self.history, self.now,
            availability_provider=lambda *_: called.append(1))
        self.assertEqual(len(rows), 2)
        self.assertEqual(called, [])

    def test_espn_exception_still_falls_back_to_single_v75(self):
        chosen = upcoming_events(self.schedule, self.now)
        def broken_provider(*_):
            raise TimeoutError("ESPN timeout")
        rows, _ = build_automatic_forecasts(
            chosen, self.history, self.now, availability_provider=broken_provider)
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[-1]["model_id"], UNIFIED_V75_MODEL_ID)
        self.assertIn("bez korekty kontuzji", rows[-1]["warning"])

    def test_enhanced_forecast_is_immutable_and_settles_once(self):
        with tempfile.TemporaryDirectory() as path:
            db = Path(path) / "tracker.sqlite3"
            def save(rows, season):
                return store_forecasts(db, season, rows, captured_at=self.now)
            def settle(rows):
                return settle_forecasts(db, rows, settled_at=self.now)
            run_cycle(self.schedule, self.history, self.now, save, settle,
                      availability_provider=self.provider)
            run_cycle(self.schedule, self.history, self.now, save, settle,
                      availability_provider=lambda *_: None)
            snapshot = read_forecasts(db)
            self.assertEqual(len(snapshot), 3)
            injury = snapshot[snapshot.model_id == UNIFIED_V75_MODEL_ID].iloc[0]
            self.assertTrue(pd.isna(injury["home_score"]))
            future_result = pd.DataFrame([{
                "game_id": self.schedule.iloc[0]["game_id"],
                "start_utc": self.schedule.iloc[0]["start_utc"],
                "home": "BOS", "away": "NYK", "home_score": 101,
                "away_score": 99, "status_code": 3,
            }])
            after = self.now + pd.Timedelta(hours=6)
            settled = settle_forecasts(db, future_result, settled_at=after)
            self.assertEqual(settled, 3)
            self.assertEqual(settle_forecasts(db, future_result, settled_at=after), 0)

    def test_no_future_game_data_alters_existing_enhanced_forecast(self):
        chosen = upcoming_events(self.schedule, self.now)
        before, _ = build_automatic_forecasts(chosen, self.history, self.now,
                                              availability_provider=self.provider)
        future = pd.DataFrame([{
            "game_id": "later", "start_utc": self.now + pd.Timedelta(days=3),
            "home": "BOS", "away": "NYK", "home_score": 200,
            "away_score": 61, "status_code": 3,
        }])
        after, _ = build_automatic_forecasts(
            chosen, pd.concat([self.history, future], ignore_index=True), self.now,
            availability_provider=self.provider)
        self.assertEqual(before, after)

    def test_feed_uses_real_samples_and_fresh_report(self):
        game = self.schedule.iloc[0].to_dict()
        game["start_utc"] = pd.Timestamp(game["start_utc"])
        self.assertTrue(near_tipoff(game, self.now))
        observed = []
        for index, day in enumerate((2, 4, 6, 8)):
            for team in ("BOS", "NYK"):
                for athlete in range(6):
                    observed.append({
                        "GAME_ID": f"{team}{index}",
                        "GAME_DATE": pd.Timestamp(f"2026-11-{day:02d}T01:00:00Z"),
                        "TEAM_ABBREVIATION": team,
                        "PLAYER_NAME": f"{team} Player {athlete}",
                        "MIN": 24 + athlete, "PTS": 8 + athlete * 2,
                        "REB": 4 + athlete, "AST": 2 + athlete,
                        "FG3M": athlete % 3,
                    })
        boxscores = pd.DataFrame(observed)
        injury = pd.DataFrame([{
            "team": "BOS", "player": "BOS Player 5",
            "status": "Out", "note": "Reported by ESPN",
        }])
        feed = PregameAvailabilityFeed(
            clock=lambda: pd.Timestamp("2026-11-10T08:01:00Z"))
        source_meta = {"timestamp": "2026-11-10T07:59:00Z",
                       "stale": False, "source": "live"}
        with patch.object(feed, "_injuries", return_value=(injury, source_meta)), \
             patch("espn_player_data.matchup_espn_logs",
                   return_value=(boxscores, {"stale": False})):
            evidence = feed(game, self.history, self.now)
        self.assertIsNotNone(evidence)
        self.assertTrue(evidence["report_fresh"])
        self.assertEqual(evidence["out_count"]["home"], 1)
        self.assertLess(evidence["score_delta"]["home"], 0)
        self.assertGreaterEqual(evidence["minute_coverage"]["away"], 5)
        with patch.object(feed, "_injuries", return_value=(injury, source_meta)), \
             patch("espn_player_data.matchup_espn_logs",
                   return_value=(boxscores, {"stale": True, "coverage": "4/7 drużyna"})):
            partial = feed(game, self.history, self.now)
        self.assertTrue(partial["boxscores_partial"])
        with patch.object(feed, "_injuries", return_value=(injury, {**source_meta, "stale": True})):
            self.assertIsNone(feed(game, self.history, self.now))


if __name__ == "__main__":
    unittest.main()
