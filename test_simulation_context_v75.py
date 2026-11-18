"""V7.5 experimental features must be deterministic, bounded and pregame-only."""
import unittest

import pandas as pd

from simulation_context_v2 import simulation_inputs
from simulation_context_v75 import simulation_inputs_v75, _rest_deltas
from simulation_engine import simulate_game
from simulation_backtest import walk_forward_comparison


def fixtures(count=28):
    base = pd.Timestamp("2026-10-05T00:00:00Z")
    return pd.DataFrame([{
        "game_id": str(70000+i), "start_utc": base + pd.Timedelta(days=i),
        "home": "BOS" if i % 2 == 0 else "NYK",
        "away": "NYK" if i % 2 == 0 else "BOS",
        "home_score": 105 + (i % 13),
        "away_score": 96 + ((i*3) % 16), "status_code": 3,
    } for i in range(count)])


class ResearchV75Tests(unittest.TestCase):
    def setUp(self):
        self.before = fixtures()
        self.game = {"game_id": "49999999", "home": "BOS", "away": "NYK",
                     "start_utc": pd.Timestamp("2026-11-10T00:00:00Z")}

    def test_new_model_uses_real_venue_history_with_bounded_changes(self):
        base = simulation_inputs(self.before, self.game)
        enriched = simulation_inputs_v75(self.before, self.game)
        self.assertEqual(enriched["score_noise"], base["score_noise"])
        factors = enriched["context"]["v75_factors"]
        # Latest 20 matchups are used for the current venue estimate.
        self.assertEqual(factors["home_venue_games"], 10)
        self.assertEqual(factors["away_venue_games"], 10)
        self.assertFalse(factors["injuries_confirmed"])
        self.assertFalse(factors["calibrated"])
        for side in ("home", "away"):
            self.assertLessEqual(abs(enriched["means"][side] - base["means"][side]), 3.8)
        first, _, h, a = simulate_game(
            self.game, enriched["means"], score_noise=enriched["score_noise"])
        second, _, h2, a2 = simulate_game(
            self.game, enriched["means"], score_noise=enriched["score_noise"])
        self.assertEqual(first, second)
        self.assertEqual(len(h), 5000)
        self.assertTrue((h == h2).all() and (a == a2).all())

    def test_future_results_do_not_change_projection(self):
        before = simulation_inputs_v75(self.before, self.game)
        fake_future = pd.DataFrame([{
            "game_id": "future", "start_utc": "2026-11-11T00:00:00Z",
            "home": "BOS", "away": "NYK", "home_score": 200,
            "away_score": 55, "status_code": 3,
        }])
        after = simulation_inputs_v75(
            pd.concat([self.before, fake_future], ignore_index=True), self.game)
        self.assertEqual(before, after)

    def test_scarce_samples_disable_venue_and_rest(self):
        scarce = self.before.head(10).copy()
        scarce["home"] = "NYK"
        scarce["away"] = "BOS"
        model = simulation_inputs_v75(scarce, self.game)
        self.assertIsNotNone(model["means"])
        factors = model["context"]["v75_factors"]
        self.assertEqual(factors["venue_home_pts"], 0.0)
        self.assertEqual(factors["venue_away_pts"], 0.0)

    def test_back_to_back_is_conservative_and_transparent(self):
        home = {"available": True, "back_to_back": True}
        away = {"available": True, "back_to_back": False}
        self.assertEqual(_rest_deltas({"home": home, "away": away}), (-0.8, 0.4))
        self.assertEqual(_rest_deltas({"home": away, "away": home}), (0.4, -0.8))
        self.assertEqual(_rest_deltas({"home": home, "away": home}), (0.0, 0.0))
        self.assertEqual(_rest_deltas({"home": home, "away": {}}), (0.0, 0.0))

    def test_walk_forward_reports_new_model_separately(self):
        frame, report = walk_forward_comparison(self.before, max_games=18)
        self.assertGreater(report.get("games", 0), 0)
        self.assertIn("v75_team_mae", report)
        self.assertIn("v75_brier", report)
        self.assertIn("enriched_team_mae", report)
        self.assertIn("v75_home", frame.columns)


if __name__ == "__main__":
    unittest.main()
