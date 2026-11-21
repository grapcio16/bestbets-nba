"""Pure factual team comparison from verified pre-tipoff NBA finals (synthetic fixtures)."""
import unittest

import pandas as pd

from simulation_context_v2 import simulation_inputs
from simulation_data_audit import verified_history
from test_simulation_context_v75 import fixtures


class TeamComparisonFactsTest(unittest.TestCase):
    def setUp(self):
        self.games = fixtures(28)
        self.fixture = {"game_id": "49999014", "home": "BOS", "away": "NYK",
                        "start_utc": pd.Timestamp("2026-11-10T00:00:00Z")}
        self.advanced = pd.DataFrame([
            {"TEAM_ABBREVIATION": "NYK", "PACE": 100.1,
             "OFF_RATING": 113.0, "DEF_RATING": 108.6},
            {"TEAM_ABBREVIATION": "BOS", "PACE": 97.8,
             "OFF_RATING": 116.0, "DEF_RATING": 111.2},
        ])

    def facts(self, history=None, advanced=None):
        model = simulation_inputs(
            self.games if history is None else history,
            self.fixture,
            self.advanced if advanced is None else advanced)
        self.assertIsNotNone(model["means"])
        return model["context"]["team_comparison"]

    def test_window_wins_and_scoring_are_from_real_previous_finals(self):
        value = self.facts()
        history = verified_history(self.games, self.fixture["start_utc"])
        for side, code in (("away", "NYK"), ("home", "BOS")):
            facts = value[side]
            records = history[(history["away"] == code) | (history["home"] == code)]
            self.assertEqual(facts["n5"], 5)
            self.assertEqual(facts["n10"], 10)
            self.assertEqual(facts["sample"], 20)
            for length in (5, 10):
                last = records.tail(length)
                points = [float(row["away_score"] if row["away"] == code
                                else row["home_score"]) for _, row in last.iterrows()]
                allowed = [float(row["home_score"] if row["away"] == code
                                 else row["away_score"]) for _, row in last.iterrows()]
                wins = sum(p > a for p, a in zip(points, allowed))
                self.assertAlmostEqual(facts["pts" + str(length)],
                                       round(sum(points)/length, 1))
                self.assertAlmostEqual(facts["allowed" + str(length)],
                                       round(sum(allowed)/length, 1))
                self.assertEqual(facts["wins" + str(length)], wins)
                self.assertEqual(facts["losses" + str(length)], length-wins)
                self.assertEqual(facts["win_pct" + str(length)],
                                 round(wins*100/length, 1))
        self.assertTrue(value["advanced_available"])
        self.assertEqual(value["away"]["pace"], 100.1)
        self.assertEqual(value["home"]["off_rating"], 116.0)
        self.assertEqual(value["home"]["def_rating"], 111.2)

    def test_future_or_nonfinal_games_never_change_the_stats(self):
        before = self.facts()
        future = pd.DataFrame([{
            "game_id": "fake-after-tipoff", "start_utc": "2026-11-12T00:00:00Z",
            "home": "BOS", "away": "NYK", "home_score": 200,
            "away_score": 55, "status_code": 3}])
        nonfinal = pd.DataFrame([{
            "game_id": "fake-live", "start_utc": "2026-11-03T00:00:00Z",
            "home": "NYK", "away": "BOS", "home_score": 190,
            "away_score": 55, "status_code": 2}])
        after = self.facts(
            pd.concat([self.games, future, nonfinal], ignore_index=True))
        self.assertEqual(before, after)

    def test_missing_advanced_is_not_filled_with_guesswork(self):
        only_away = self.advanced.iloc[:1].copy()
        item = self.facts(advanced=only_away)
        self.assertFalse(item["advanced_available"])
        for side in ("home", "away"):
            self.assertIsNone(item[side]["pace"])
            self.assertIsNone(item[side]["off_rating"])
            self.assertIsNone(item[side]["def_rating"])
            self.assertIsNotNone(item[side]["pts10"])


if __name__ == "__main__":
    unittest.main()
