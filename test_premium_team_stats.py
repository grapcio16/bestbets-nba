"""Team analytics never fabricate missing results or mix future games."""
import unittest
from unittest.mock import Mock

import pandas as pd

from premium_team_stats import (build_team_analytics, load_verified_advanced,
                                estimate_team_ratings_from_boxscores,
                                parse_espn_possessions_boxscore)


class PremiumTeamStatsTests(unittest.TestCase):
    @staticmethod
    def fake_summary(game_id, *, complete=True, period=4):
        def totals(code, fga, fta, oreb, tov):
            values = [
                {"name": "fieldGoalsMade-fieldGoalsAttempted", "label": "FG",
                 "displayValue": f"41-{fga}"},
                {"name": "freeThrowsMade-freeThrowsAttempted", "label": "FT",
                 "displayValue": f"16-{fta}"},
                {"name": "offensiveRebounds", "label": "OR", "displayValue": str(oreb)},
                {"name": "totalTurnovers", "label": "TO", "displayValue": str(tov)},
            ]
            if not complete:
                values.pop()
            return {"team": {"abbreviation": code}, "statistics": values}
        return {"header": {"competitions": [{"id": str(game_id),
            "status": {"period": period}}]}, "boxscore": {"teams": [
                totals("BOS", 90, 20, 10, 14), totals("GS", 87, 24, 11, 12)]}}

    @staticmethod
    def sample_game():
        return pd.DataFrame([{
            "game_id": "season-test-one", "start_utc": "2026-11-08T01:00:00Z",
            "status_code": 3, "home": "BOS", "away": "GSW",
            "home_score": 111, "away_score": 104,
        }])

    def test_premium_loader_fetches_real_advanced_on_demand(self):
        official = pd.DataFrame([{"TEAM_ABBREVIATION": "BOS",
            "OFF_RATING": 119.7, "DEF_RATING": 108.3, "PACE": 99.5}])
        fetch = Mock(return_value=(official, {"stale": False}))
        verified = load_verified_advanced("2026-27", lambda _: pd.DataFrame(), fetch)
        report = build_team_analytics(self.sample_game(), verified)
        fetch.assert_called_once_with("Drużyny • advanced (pace/def)", "2026-27")
        self.assertEqual(report["teams"]["BOS"]["off"], 119.7)
        self.assertEqual(report["teams"]["BOS"]["def"], 108.3)
        self.assertEqual(report["teams"]["BOS"]["pace"], 99.5)

    def test_premium_loader_survives_blocked_advanced_source(self):
        fetch = Mock(side_effect=RuntimeError("NBA Stats blocked"))
        verified = load_verified_advanced("2026-27", lambda _: pd.DataFrame(), fetch)
        report = build_team_analytics(self.sample_game(), verified)
        self.assertEqual(report["teams"]["BOS"]["points"], 111.0)
        self.assertIsNone(report["teams"]["BOS"]["off"])
        self.assertEqual(report["teams"]["BOS"]["last5"], "W")

    def test_premium_loader_rejects_stale_advanced_metrics(self):
        official = pd.DataFrame([{"TEAM_ABBREVIATION": "BOS",
            "OFF_RATING": 119.7, "DEF_RATING": 108.3, "PACE": 99.5}])
        verified = load_verified_advanced("2026-27", lambda _: pd.DataFrame(),
                                          Mock(return_value=(official, {"stale": True})))
        self.assertEqual(verified, {})

    def test_completed_games_and_validated_advanced_only(self):
        rows = pd.DataFrame([
            {"game_id": "one", "start_utc": "2026-11-08T01:00:00Z", "status_code": 3,
             "home": "BOS", "away": "GSW", "home_score": 111, "away_score": 104},
            {"game_id": "one", "start_utc": "2026-11-08T01:00:00Z", "status_code": 3,
             "home": "BOS", "away": "GSW", "home_score": 111, "away_score": 104},
            {"game_id": "two", "start_utc": "2026-11-11T01:00:00Z", "status_code": 3,
             "home": "GSW", "away": "BOS", "home_score": 108, "away_score": 115},
            {"game_id": "pending", "start_utc": "2026-11-12T01:00:00Z", "status_code": 2,
             "home": "BOS", "away": "GSW", "home_score": 150, "away_score": 120},
            {"game_id": "impossible", "start_utc": "2026-11-13T01:00:00Z", "status_code": 3,
             "home": "BOS", "away": "GSW", "home_score": 999, "away_score": 10},
        ])
        result = build_team_analytics(rows, advanced={
            "BOS": {"pace": 99.2, "off": 114.2, "def": 109.1,
                    "source": "NBA Stats — advanced"},
            "GSW": {"pace": 101.0, "off": 113.0, "def": 112.0,
                    "source": "unverified"},
        })
        bos = result["teams"]["BOS"]
        self.assertEqual(bos["sample"], 2)
        self.assertEqual(bos["points"], 113.0)
        self.assertEqual(bos["allowed"], 106.0)
        self.assertEqual(bos["home"], 111)
        self.assertEqual(bos["away"], 115)
        self.assertEqual(bos["last5"], "WW")
        self.assertEqual(bos["pace"], 99.2)
        self.assertIsNone(result["teams"]["GSW"]["pace"])
        self.assertNotIn("ATL", result["teams"])

    def test_real_boxscores_generate_only_the_requested_three_ratings(self):
        completed = pd.DataFrame([{
            "game_id": str(401800001 + i), "start_utc": f"2026-11-{i + 2:02d}T01:00:00Z",
            "status_code": 3, "home": "BOS", "away": "GSW",
            "home_score": 112, "away_score": 110} for i in range(5)])
        fetch = Mock(side_effect=lambda game: self.fake_summary(game["game_id"]))
        rating = estimate_team_ratings_from_boxscores("BOS", completed, fetch)
        self.assertEqual(rating["rating_source"], "ESPN — szacunek z boxscore")
        self.assertTrue(rating["rating_estimated"])
        self.assertEqual(rating["rating_sample"], 5)
        self.assertEqual((rating["off"], rating["def"], rating["pace"]),
                         (111.2, 109.3, 100.7))
        self.assertEqual(fetch.call_count, 5)

    def test_bad_game_identity_or_missing_possession_input_is_not_fabricated(self):
        game = {"game_id": "401800001", "home": "BOS", "away": "GSW",
                "home_score": 112, "away_score": 110}
        self.assertIsNone(parse_espn_possessions_boxscore(
            self.fake_summary("401800002"), game))
        self.assertIsNone(parse_espn_possessions_boxscore(
            self.fake_summary("401800001", complete=False), game))
        completed = pd.DataFrame([{**game, "start_utc": "2026-11-03T01:00:00Z",
                                   "status_code": 3}])
        self.assertIsNone(estimate_team_ratings_from_boxscores(
            "BOS", completed, Mock(side_effect=RuntimeError("ESPN offline"))))

    def test_overtime_reduces_48_minute_pace(self):
        game = {"game_id": "401800001", "home": "BOS", "away": "GSW",
                "home_score": 112, "away_score": 110}
        normal = parse_espn_possessions_boxscore(self.fake_summary(game["game_id"]), game)
        overtime = parse_espn_possessions_boxscore(
            self.fake_summary(game["game_id"], period=5), game)
        self.assertEqual(normal["duration"], 48)
        self.assertEqual(overtime["duration"], 53)
        self.assertEqual(normal["possessions"], overtime["possessions"])

    def test_no_scores_means_no_stats(self):
        empty = build_team_analytics(pd.DataFrame())
        self.assertEqual(empty["teams"], {})
        self.assertTrue(empty["partial"])

    def test_missing_dates_explicitly_reported(self):
        report = build_team_analytics(pd.DataFrame([{"status_code": 3}]))
        self.assertEqual(report["teams"], {})
        self.assertIn("dat", report["error"])


if __name__ == "__main__":
    unittest.main()
