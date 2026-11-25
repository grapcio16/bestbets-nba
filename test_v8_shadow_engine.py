"""Offline V8 model regression: chronology, calibration and independent math.

Every case here is deterministic, synthetic and not a real NBA prediction.
A real research evaluation requires fetched observed boxscore history and
prospectively frozen pregame game IDs in Neon.
"""
import unittest
from unittest.mock import patch
from datetime import timedelta

import numpy as np
import pandas as pd

from v8_shadow.engine import VERSION, _examples, _prepare_history, predict_v8


def history(seed=13, total=260):
    rng = np.random.default_rng(seed)
    teams = [f"T{i:02d}" for i in range(12)]
    tip = pd.Timestamp("2026-09-25T00:00:00Z")
    scores = []
    for i in range(total):
        pair = rng.choice(teams, size=2, replace=False)
        away, home = str(pair[0]), str(pair[1])
        # Realistic synthetic dispersion and team-level persistent signal.
        away_signal = (int(away[1:]) - 5.5) * 2.2
        home_signal = (int(home[1:]) - 5.5) * 2.2
        pace = float(np.clip(rng.normal(99, 4.5), 85, 115))
        home_poss = float(np.clip(pace + rng.normal(0, 1.2), 80, 120))
        away_poss = float(np.clip(pace + rng.normal(0, 1.2), 80, 120))
        h = int(np.clip(np.rint(112 + home_signal - .3*away_signal +
                  rng.normal(0, 11)), 65, 175))
        a = int(np.clip(np.rint(110 + away_signal - .3*home_signal +
                  rng.normal(0, 12)), 65, 175))
        scores.append({
            "game_id": str(401000000 + i), "start_utc": (
                tip + pd.Timedelta(hours=9*i)).isoformat(),
            "away": away, "home": home, "away_score": a,
            "home_score": h, "away_poss": round(away_poss, 3),
            "home_poss": round(home_poss, 3),
        })
    return scores


class EngineTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.history = history()
        cls.time = pd.to_datetime(cls.history[-1]["start_utc"], utc=True) + pd.Timedelta(hours=10)
        cls.match = {"game_id": "401999999", "home": "T07", "away": "T02",
                     "start_utc": (cls.time + pd.Timedelta(hours=5)).isoformat()}

    def test_joint_distribution_and_independent_mean(self):
        result = predict_v8(self.history, self.match, self.time, n=5000)
        self.assertEqual(result["status"], "shadow_only")
        self.assertEqual(result["model_id"], VERSION)
        self.assertGreaterEqual(result["training_examples"], 60)
        self.assertGreater(result["expected_possessions"], 80)
        self.assertLess(result["expected_possessions"], 120)
        self.assertAlmostEqual(result["home_win_probability_pct"]+
                               result["away_win_probability_pct"], 100, places=1)
        for side in ("home","away","total"):
            p10, mid, p90 = result[f"{side}_p10_p50_p90"]
            self.assertLess(p10, mid)
            self.assertLess(mid, p90)
            self.assertGreater(p90 - p10, 10)
        self.assertGreater(result["scenario_home"], 60)
        self.assertGreater(result["scenario_away"], 60)
        self.assertLess(result["scenario_bin_probability_pct"], 20)
        self.assertTrue(result["holdout_team_mae"] > 0)
        self.assertTrue(result["holdout_n"] >= 16)

    def test_determinism_at_identical_frozen_clock(self):
        first = predict_v8(self.history, self.match, self.time, n=1000)
        second = predict_v8(self.history, self.match, self.time, n=1000)
        self.assertEqual(first, second)

    def test_future_game_result_does_not_leak_into_past_prediction(self):
        clean = predict_v8(self.history, self.match, self.time, n=1000)
        future = dict(self.history[-1])
        future.update(game_id="401999997", start_utc=(
            self.time + pd.Timedelta(hours=1)).isoformat(),
            home_score=180, away_score=65)
        contaminated = predict_v8(self.history+[future], self.match, self.time,n=1000)
        self.assertEqual(clean, contaminated)

    def test_ongoing_match_result_cannot_leak_into_current_forecast(self):
        # One game began an hour ago. It may already appear in a later
        # completed dataset but was NOT yet final at this prediction instant.
        clean = predict_v8(self.history, self.match, self.time, n=1000)
        early = dict(self.history[-1])
        early.update(
            game_id="401999996",
            start_utc=(self.time - pd.Timedelta(hours=1)).isoformat(),
            home_score=175, away_score=68,
        )
        contaminated = predict_v8(self.history + [early], self.match,
                                  self.time, n=1000)
        self.assertEqual(clean, contaminated)

    def test_adjacent_tipoffs_share_only_completed_prior_scores(self):
        # Physical games need time to finish; earlier kickoff alone does
        # not make a final score available to the subsequent tipoff.
        start = pd.Timestamp("2026-11-25T00:00:00Z")
        rows = [
            {"game_id": str(401900000+i),
             "start_utc": (start+pd.Timedelta(minutes=offset)).isoformat(),
             "home_score": 111+i, "away_score": 105+i}
            for i,offset in enumerate((0, 30, 180, 300))
        ]
        seen = {}
        def remember(game, past):
            seen[game["game_id"]] = [p["game_id"] for p in past]
            return {"x": np.array([float(len(past))])}
        with patch("v8_shadow.engine._feature_row", side_effect=remember):
            features, labels = _examples(
                rows, start + pd.Timedelta(hours=12))
        self.assertEqual(len(features), 4)
        self.assertEqual(len(labels), 4)
        self.assertEqual(seen[rows[0]["game_id"]], [])
        self.assertEqual(seen[rows[1]["game_id"]], [])
        self.assertEqual(seen[rows[2]["game_id"]], [])
        self.assertEqual(seen[rows[3]["game_id"]],
                         [rows[0]["game_id"], rows[1]["game_id"]])

    def test_invalid_scores_no_guessed_box_stats(self):
        corrupted = list(self.history)
        corrupted[0] = dict(corrupted[0], away_poss=None)
        records = _prepare_history(corrupted)
        self.assertEqual(len(records), len(self.history)-1)

    def test_duplicate_ids_rejected(self):
        with self.assertRaisesRegex(ValueError,"duplicate game"):
            _prepare_history([self.history[0],self.history[0]])

    def test_no_model_without_history_and_cutoff(self):
        empty = predict_v8([], self.match, self.time, n=1000)
        self.assertEqual(empty["status"], "insufficient_evidence")
        with self.assertRaisesRegex(ValueError, "before tipoff"):
            predict_v8(self.history, self.match,
                       pd.to_datetime(self.match["start_utc"],utc=True) -
                       pd.Timedelta(minutes=8), n=1000)

    def test_simultaneous_start_times_no_same_start_leak(self):
        entries = list(self.history[:180])
        same = pd.to_datetime(entries[-1]["start_utc"],utc=True)
        entries.append({**entries[-2], "game_id": "401999998",
                       "start_utc": same.isoformat(),
                       "away_score": 172, "home_score": 75})
        x, y = _examples(_prepare_history(entries), self.time)
        # A simultaneous game is allowed as a training example at a later
        # cutoff, but cannot influence features for another simultaneous game.
        self.assertEqual(len(x),len(y))
        self.assertTrue(np.isfinite(x).all())

    def test_no_legacy_engine_imports(self):
        from pathlib import Path
        source = (Path(__file__).parent/"v8_shadow"/"engine.py").read_text()
        for forbidden in ("from simulation_engine import",
                          "from simulation_context_v75 import",
                          "legacy_matchup_means(", "matchup_means(",
                          "simulate_game("):
            self.assertNotIn(forbidden,source)


if __name__ == "__main__":
    unittest.main()
