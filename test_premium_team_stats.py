"""Team analytics never fabricate missing results or mix future games."""
import unittest

import pandas as pd

from premium_team_stats import build_team_analytics


class PremiumTeamStatsTests(unittest.TestCase):
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
