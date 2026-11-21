"""Observed-variance and no-lookahead checks for enriched simulations."""
import unittest

import pandas as pd

from simulation_context_v2 import simulation_inputs, score_volatility
from simulation_data_audit import verified_history
from simulation_engine import simulate_game


def history(n=28):
    start = pd.Timestamp("2026-10-10T00:00:00Z")
    return pd.DataFrame([{
        "game_id": str(1000 + i),
        "start_utc": start + pd.Timedelta(days=i),
        "home": "BOS" if i % 2 == 0 else "NYK",
        "away": "NYK" if i % 2 == 0 else "BOS",
        "home_score": 107 + i % 14,
        "away_score": 103 + i % 19,
        "status_code": 3,
    } for i in range(n)])


class EnrichedModelTests(unittest.TestCase):
    def setUp(self):
        self.game = {"game_id": "4019999", "home": "BOS", "away": "NYK",
                     "start_utc": pd.Timestamp("2026-11-14T00:00:00Z")}
        self.data = history()

    def test_more_historical_inputs_without_lookahead(self):
        first = simulation_inputs(self.data, self.game)
        future = pd.DataFrame([{
            "game_id": "late", "start_utc": "2026-11-15T00:00:00Z",
            "home": "BOS", "away": "NYK", "home_score": 200,
            "away_score": 55, "status_code": 3,
        }])
        again = simulation_inputs(pd.concat([self.data, future], ignore_index=True), self.game)
        self.assertEqual(first, again)
        self.assertEqual(first["context"]["completed_games"], len(self.data))
        # Venue evidence deliberately uses the most recent 20 fixtures.
        self.assertEqual(first["context"]["venue_samples"], [10, 10])
        self.assertFalse(first["context"]["advanced_available"])
        self.assertIsNotNone(first["score_noise"]["home_sd"])
        self.assertEqual(first["context"]["score_sd_points"], [
            score_volatility(verified_history(self.data, self.game["start_utc"]), "NYK")["sd"],
            score_volatility(verified_history(self.data, self.game["start_utc"]), "BOS")["sd"],
        ])
        self.assertEqual(len(first["context"]["score_sd_samples"]), 2)
        self.assertNotEqual(first["context"]["score_sd_points"],
                            first["context"]["score_sd_samples"])

    def test_noise_is_finite_shrunk_and_deterministic(self):
        actual = verified_history(self.data, self.game["start_utc"])
        home = score_volatility(actual, "BOS")
        self.assertEqual(home["sample"], 20)
        self.assertGreater(home["sd"], 7)
        self.assertLess(home["sd"], 20)
        model = simulation_inputs(self.data, self.game)
        one, _, hs, as_ = simulate_game(self.game, model["means"], score_noise=model["score_noise"])
        two, _, hs2, as2 = simulate_game(self.game, model["means"], score_noise=model["score_noise"])
        self.assertEqual(one, two)
        self.assertEqual(one["n_sims"], 5000)
        self.assertEqual(len(hs), 5000)
        self.assertTrue((hs == hs2).all() and (as_ == as2).all())
        self.assertTrue((hs != as_).all())

    def test_sparse_history_does_not_invent_sd(self):
        short = verified_history(self.data.head(3), self.game["start_utc"])
        self.assertIsNone(score_volatility(short, "BOS")["sd"])
        self.assertIsNone(simulation_inputs(short, self.game)["means"])


if __name__ == "__main__":
    unittest.main()
