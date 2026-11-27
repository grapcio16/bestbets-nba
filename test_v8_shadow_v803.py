"""Offline regression tests for V8.03; no external calls or DB writes."""
import unittest
import numpy as np
import pandas as pd

from test_v8_shadow_engine import history
from v8_shadow.engine import FINAL_RESULT_DELAY, _prepare_history, _time
from v8_shadow.engine_v803 import VERSION, LEAD, _examples, _fit, _targets, _points, predict_v803


class V803Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.games = history()
        cls.asof = _time(cls.games[-1]["start_utc"]) + pd.Timedelta(hours=10)
        cls.match = {"game_id": "401999999", "home": "T07", "away": "T02",
                     "start_utc": (cls.asof + pd.Timedelta(hours=5)).isoformat()}

    def test_factorized_targets_reconstruct_scores(self):
        game = self.games[0]
        np.testing.assert_allclose(_points(_targets(game)), [game["home_score"], game["away_score"]])

    def test_forecast_contract(self):
        result = predict_v803(self.games, self.match, self.asof, n=1000)
        self.assertEqual(result["status"], "shadow_only")
        self.assertEqual(result["model_id"], VERSION)
        self.assertNotEqual(result["scenario_home"], result["scenario_away"])
        self.assertAlmostEqual(result["home_win_probability_pct"] + result["away_win_probability_pct"], 100, places=1)
        self.assertTrue(75 <= result["expected_possessions"] <= 125)
        self.assertGreaterEqual(result["holdout_n"], 16)
        self.assertGreaterEqual(result["holdout_fit_n"], 40)
        for side in ("home", "away", "total"):
            low, middle, high = result[side + "_p10_p50_p90"]
            self.assertLess(low, middle)
            self.assertLess(middle, high)

    def test_frozen_clock_and_no_future_or_ongoing_result_leakage(self):
        baseline = predict_v803(self.games, self.match, self.asof, n=1000)
        self.assertEqual(baseline, predict_v803(self.games, self.match, self.asof, n=1000))
        for hours in (-1, 1):
            injected = dict(self.games[-1], game_id="401999998",
                start_utc=(self.asof + pd.Timedelta(hours=hours)).isoformat(),
                home_score=180, away_score=65)
            self.assertEqual(baseline, predict_v803(self.games+[injected], self.match, self.asof, n=1000))

    def test_holdout_training_labels_are_purged(self):
        x, y, times = _examples(_prepare_history(self.games))
        _, _, report = _fit(x, y, times)
        holdout_start = times[-report["holdout_n"]] - LEAD
        self.assertLessEqual(times[report["holdout_fit_n"]-1] + FINAL_RESULT_DELAY, holdout_start)
        self.assertGreater(report["holdout_pace_mae"], 0)

    def test_missing_evidence_and_late_cutoff(self):
        self.assertEqual(predict_v803([], self.match, self.asof, n=1000)["status"], "insufficient_evidence")
        with self.assertRaisesRegex(ValueError, "before tipoff"):
            predict_v803(self.games, self.match, _time(self.match["start_utc"])-pd.Timedelta(minutes=5), n=1000)


if __name__ == "__main__":
    unittest.main()
