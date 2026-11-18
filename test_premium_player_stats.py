"""Offline, deterministic tests for Premium player directory analytics."""
import unittest

import pandas as pd

from premium_player_stats import build_player_averages


class PlayerAveragesTests(unittest.TestCase):
    def test_weighted_three_point_percentage_and_per_game_means(self):
        raw = pd.DataFrame([
            {"PLAYER_NAME": "Jayson Tatum", "TEAM_ABBREVIATION": "BOS",
             "GAME_ID": "1", "GAME_DATE": "2026-11-10", "MIN": 31,
             "PTS": 30, "REB": 8, "AST": 5, "FG3M": 3, "FG3A": 5},
            {"PLAYER_NAME": "Jayson Tatum", "TEAM_ABBREVIATION": "BOS",
             "GAME_ID": "2", "GAME_DATE": "2026-11-13", "MIN": 32,
             "PTS": 20, "REB": 6, "AST": 7, "FG3M": 1, "FG3A": 5},
        ])
        result = build_player_averages(raw, {"source": "NBA Stats"})
        row = result["rows"]["jaysontatum"]
        self.assertEqual((row["pts"], row["reb"], row["ast"]), (25., 7., 6.))
        self.assertEqual(row["three_pm"], 2.)
        self.assertEqual(row["three_pct"], 40.)
        self.assertEqual(row["games"], 2)
        self.assertFalse(result["partial"])

    def test_no_attempts_means_no_three_point_percentage(self):
        raw = pd.DataFrame([{"PLAYER_NAME": "Test Player", "TEAM_ABBREVIATION": "BOS",
                             "GAME_DATE": "2026-11-12", "MIN": 20, "PTS": 12,
                             "REB": 3, "AST": 2, "FG3M": 1}])
        result = build_player_averages(raw, {"source": "ESPN", "partial": True})
        self.assertIsNone(result["rows"]["testplayer"]["three_pct"])
        self.assertTrue(result["partial"])

    def test_empty_source_is_honestly_reported(self):
        result = build_player_averages(pd.DataFrame(), {})
        self.assertEqual(result["rows"], {})
        self.assertIn("error", result)

    def test_duplicate_game_and_dnp_are_excluded(self):
        row = {"PLAYER_NAME": "Nikola Jokić", "TEAM_ABBREVIATION": "DEN",
               "GAME_ID": "1", "GAME_DATE": "2026-11-10", "MIN": 33,
               "PTS": 25, "REB": 12, "AST": 9, "FG3M": 1, "FG3A": 3}
        raw = pd.DataFrame([row, row, {**row, "GAME_ID": "2", "MIN": 0, "PTS": 0}])
        result = build_player_averages(raw, {"source": "NBA Stats"})
        self.assertEqual(result["rows"]["nikolajokic"]["games"], 1)


if __name__ == "__main__":
    unittest.main()
