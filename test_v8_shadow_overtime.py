"""Regression QA for V8.2: NBA final outcomes cannot end tied.

Synthetic draws, not empirical verification of overtime scoring efficiency.
The original v8_possessions_shadow_v01 archived pregame rows remain untouched.
"""
import unittest

import numpy as np
import pandas as pd

from test_v8_shadow_engine import history
from v8_shadow.engine import (
    VERSION, _resolve_overtime_draws, predict_v8,
)


class V8OvertimeTests(unittest.TestCase):
    def test_versioned_separately_from_archived_v01(self):
        self.assertEqual(VERSION, "v8_possessions_shadow_v02")

    def test_regulation_ties_get_scored_overtime_not_fake_winner(self):
        reg = np.array([
            [115, 115], [121, 98], [85, 85], [99, 114], [132, 132],
        ], dtype=int)
        rng = np.random.default_rng(19)
        final, tied, periods = _resolve_overtime_draws(
            reg, np.array([111.0, 114.0]), rng)
        self.assertEqual(tied, 3)
        self.assertTrue(np.all(final[:, 0] != final[:, 1]))
        self.assertTrue(np.all(final >= reg))
        self.assertTrue(np.array_equal(final[[1, 3]], reg[[1, 3]]))
        self.assertEqual(periods[1], 0)
        self.assertEqual(periods[3], 0)
        self.assertTrue(np.all(periods[[0, 2, 4]] >= 1))

    def test_overtime_is_reproducible_for_frozen_random_seed(self):
        scores = np.full((100, 2), 112, dtype=int)
        a = _resolve_overtime_draws(scores, np.array([115.0, 112.0]),
                                    np.random.default_rng(42))
        b = _resolve_overtime_draws(scores, np.array([115.0, 112.0]),
                                    np.random.default_rng(42))
        self.assertTrue(np.array_equal(a[0], b[0]))
        self.assertEqual(a[1], 100)
        self.assertTrue(np.all(a[0][:, 0] != a[0][:, 1]))

    def test_unresolvable_ties_fail_closed(self):
        class ImpossibleOT:
            @staticmethod
            def lognormal(*, mean, sigma, size):
                return np.ones(size)
            @staticmethod
            def poisson(rate):
                return np.zeros_like(rate, dtype=int)
        with self.assertRaisesRegex(ValueError, "unable to resolve"):
            _resolve_overtime_draws(
                np.array([[115, 115]], dtype=int),
                np.array([115.0, 115.0]), ImpossibleOT())

    def test_complete_5000_draws_return_untied_final_scenario_and_averages(self):
        games = history()
        asof = pd.to_datetime(games[-1]["start_utc"], utc=True) + pd.Timedelta(hours=10)
        fixture = {
            "game_id": "401988888", "home": "T02", "away": "T09",
            "start_utc": (asof + pd.Timedelta(hours=7)).isoformat(),
        }
        result = predict_v8(games, fixture, asof, n=5000)
        self.assertEqual(result["status"], "shadow_only")
        self.assertEqual(result["model_id"], VERSION)
        self.assertNotEqual(result["scenario_home"], result["scenario_away"])
        self.assertTrue(result["final_scores_include_simulated_overtime"])
        self.assertGreaterEqual(result["overtime_trajectory_count"], 0)
        self.assertLessEqual(result["overtime_trajectory_count"], 5000)
        self.assertGreaterEqual(result["overtime_probability_pct"], 0)
        self.assertLessEqual(result["overtime_probability_pct"], 100)
        self.assertGreater(result["overtime_max_periods_simulated"], 0)
        self.assertAlmostEqual(
            result["home_win_probability_pct"] +
            result["away_win_probability_pct"], 100, places=1)
        self.assertAlmostEqual(
            result["mean_home"] + result["mean_away"],
            result["mean_total"], delta=0.03)
        for side in ("home", "away", "total"):
            lo, med, hi = result[f"{side}_p10_p50_p90"]
            self.assertLess(lo, med)
            self.assertLess(med, hi)

    def test_frozen_prediction_is_deterministic_including_overtime(self):
        games = history()
        asof = pd.to_datetime(games[-1]["start_utc"], utc=True) + pd.Timedelta(hours=10)
        fixture = {
            "game_id": "401988881", "home": "T01", "away": "T05",
            "start_utc": (asof + pd.Timedelta(hours=6)).isoformat(),
        }
        a = predict_v8(games, fixture, asof, n=1000)
        b = predict_v8(games, fixture, asof, n=1000)
        self.assertEqual(a, b)


if __name__ == "__main__":
    unittest.main()
