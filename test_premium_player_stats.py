"""Offline, deterministic tests for Premium player directory analytics."""
import unittest

import pandas as pd

from premium_player_stats import (
    build_player_averages, load_verified_player_history, verified_roster_targets,
)


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
        self.assertEqual(row["three_pa"], 5.)
        self.assertEqual(row["three_pct"], 40.)
        self.assertEqual(row["games"], 2)
        self.assertFalse(result["partial"])

    def test_no_attempts_means_no_three_point_percentage(self):
        raw = pd.DataFrame([{"PLAYER_NAME": "Test Player", "TEAM_ABBREVIATION": "BOS",
                             "GAME_DATE": "2026-11-12", "MIN": 20, "PTS": 12,
                             "REB": 3, "AST": 2, "FG3M": 1}])
        result = build_player_averages(raw, {"source": "ESPN", "partial": True})
        self.assertIsNone(result["rows"]["testplayer"]["three_pct"])
        self.assertIsNone(result["rows"]["testplayer"]["three_pa"])
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

    def test_browser_ids_must_match_server_verified_roster(self):
        catalog = {"players": [
            {"id": "111", "name": "Nikola Jokić", "team": "DEN"},
            {"id": "222", "name": "Stephen Curry", "team": "GSW"},
        ]}
        self.assertEqual(verified_roster_targets(
            ["999", "111", "111", "222", "invalid"], catalog), [
                {"id": "111", "name": "Nikola Jokić", "team": "DEN"},
                {"id": "222", "name": "Stephen Curry", "team": "GSW"},
            ])
        self.assertEqual(verified_roster_targets(["111"], None), [])
        self.assertEqual(verified_roster_targets("111", catalog), [])

    def test_same_name_different_ids_never_mix_athlete_stats(self):
        raw = pd.DataFrame([
            {"PLAYER_ID": "101", "PLAYER_NAME": "Alex Smith", "TEAM_ABBREVIATION": "BOS",
             "GAME_ID": "game1", "GAME_DATE": "2026-11-10", "MIN": 30,
             "PTS": 30, "REB": 8, "AST": 5, "FG3M": 4, "FG3A": 10},
            {"PLAYER_ID": "202", "PLAYER_NAME": "Alex Smith", "TEAM_ABBREVIATION": "MIA",
             "GAME_ID": "game1", "GAME_DATE": "2026-11-10", "MIN": 20,
             "PTS": 10, "REB": 1, "AST": 2, "FG3M": 1, "FG3A": 3},
        ])
        result = build_player_averages(raw, {"source": "ESPN"})
        self.assertEqual(result["id_rows"]["101"]["pts"], 30)
        self.assertEqual(result["id_rows"]["202"]["pts"], 10)
        self.assertNotIn("alexsmith", result["rows"])

    def test_partial_three_point_coverage_does_not_discard_points(self):
        raw = pd.DataFrame([
            {"PLAYER_ID": "123", "PLAYER_NAME": "Test Player", "TEAM_ABBREVIATION": "BOS",
             "GAME_ID": "1", "GAME_DATE": "2026-11-10", "MIN": 30,
             "PTS": 30, "REB": 7, "AST": 5, "FG3M": 3, "FG3A": 6},
            {"PLAYER_ID": "123", "PLAYER_NAME": "Test Player", "TEAM_ABBREVIATION": "BOS",
             "GAME_ID": "2", "GAME_DATE": "2026-11-12", "MIN": 28,
             "PTS": 20, "REB": 5, "AST": 3, "FG3M": None, "FG3A": None},
        ])
        stats = build_player_averages(raw, {"source": "ESPN"})["id_rows"]["123"]
        self.assertEqual((stats["pts"], stats["games"]), (25, 2))
        self.assertEqual((stats["three_pm_games"], stats["three_pct_games"]), (1, 1))
        self.assertEqual(stats["three_pct"], 50)
        self.assertEqual(stats["last_game"], "2026-11-12")

    def test_primary_feed_and_fallback_keep_only_verified_requested_id(self):
        rows = pd.DataFrame([
            {"PLAYER_ID": "111", "PLAYER_NAME": "John Doe", "TEAM_ABBREVIATION": "BOS",
             "GAME_ID": "1", "GAME_DATE": "2026-11-10", "MIN": 20,
             "PTS": 15, "REB": 4, "AST": 3, "FG3M": 2, "FG3A": 4},
            {"PLAYER_ID": "222", "PLAYER_NAME": "John Doe", "TEAM_ABBREVIATION": "BOS",
             "GAME_ID": "1", "GAME_DATE": "2026-11-10", "MIN": 20,
             "PTS": 41, "REB": 4, "AST": 3, "FG3M": 2, "FG3A": 4},
        ])
        calls = []
        def fail_primary(*args):
            raise RuntimeError("ESPN chwilowo nie odpowiada")
        def recent(team, season, games_per_team):
            calls.append((team, season, games_per_team))
            return rows, {"coverage": "1/8"}
        result = load_verified_player_history("111", "John Doe", "BOS", "2026-27",
                                              gamelog_fetch=fail_primary, recent_team_fetch=recent)
        self.assertEqual(calls, [("BOS", "2026-27", 8)])
        self.assertEqual(result["id_rows"]["111"]["pts"], 15)
        self.assertNotIn("222", result["id_rows"])
        self.assertTrue(result["partial"])
        self.assertIn("boxscore", result["source"])
        with self.assertRaises(ValueError):
            load_verified_player_history("333", "John Doe", "BOS", "2026-27",
                                         gamelog_fetch=fail_primary, recent_team_fetch=recent)

    def test_valid_primary_never_invokes_partial_fallback(self):
        row = pd.DataFrame([{"PLAYER_ID": "123", "PLAYER_NAME": "Person", "TEAM_ABBREVIATION": "SAS",
                             "GAME_DATE": "2026-11-10", "GAME_ID": "1", "MIN": 30,
                             "PTS": 20, "REB": 8, "AST": 4, "FG3M": 0, "FG3A": 0}])
        def never(*args, **kwargs):
            self.fail("Fallback must not replace an available current-season gamelog")
        got = load_verified_player_history("123", "Person", "SAS", "2026-27",
                                           gamelog_fetch=lambda *a: (row, {"source": "ESPN"}),
                                           recent_team_fetch=never)
        self.assertEqual(got["id_rows"]["123"]["games"], 1)
        self.assertIsNone(got["id_rows"]["123"]["three_pct"])


if __name__ == "__main__":
    unittest.main()
