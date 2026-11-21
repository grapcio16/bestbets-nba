"""Real-data history packing for screenshot-matched Player Simulations.

All fixtures synthetic; production must not invent history, photo identities,
future logs or bookmaker-like player hit probabilities.
"""
import unittest

import pandas as pd

from bestbets_simulations_canvas import _compact_pregame_player_history


class PlayerSimulationsEvidenceTest(unittest.TestCase):
    def test_verified_pregame_history_and_team_binding(self):
        cutoff = pd.Timestamp("2026-11-22T20:00:00Z")
        rows = [
            {
                "GAME_ID": str(401900000 + i), "GAME_DATE": f"2026-11-{i+1:02d}T12:00:00Z",
                "TEAM_ABBREVIATION": "PHI", "PLAYER_NAME": "Sample Player",
                "PLAYER_ID": "44332211", "POSITION": "PG",
                "PTS": 15 + i, "REB": 3 + i % 2, "AST": 5 + i % 3, "MIN": 30.0,
            } for i in range(6)
        ]
        rows.append({**rows[-1], "GAME_ID": "401900999",
                     "GAME_DATE": "2026-11-25T12:00:00Z", "PTS": 99})
        rows.append({**rows[-1], "TEAM_ABBREVIATION": "LAL",
                     "GAME_DATE": "2026-11-20T12:00:00Z"})
        rows.append({**rows[-1], "TEAM_ABBREVIATION": "BOS",
                     "GAME_DATE": "2026-11-20T12:00:00Z", "PTS": None})
        rows.append({**rows[0], "MIN": 0})
        result = _compact_pregame_player_history(
            pd.DataFrame(rows), cutoff, "PHI", "BOS")
        item = result[("PHI", "sampleplayer")]
        self.assertEqual(item["espn_id"], "44332211")
        self.assertEqual(item["position"], "PG")
        self.assertEqual(len(item["history"]), 6)
        self.assertEqual(item["history"][0]["pts"], 15)
        self.assertEqual(item["history"][-1]["pts"], 20)
        self.assertEqual(item["history"][-1]["pra"], 31.0)
        self.assertNotIn(("LAL", "sampleplayer"), result)
        self.assertNotIn(("BOS", "sampleplayer"), result)
        self.assertTrue(all(r["date"] < cutoff.date().isoformat()
                            for r in item["history"]))

    def test_missing_source_does_not_make_up_an_athlete(self):
        cutoff = pd.Timestamp("2026-11-22T20:00:00Z")
        self.assertEqual(_compact_pregame_player_history(
            pd.DataFrame(), cutoff, "PHI", "MIL"), {})
        self.assertEqual(_compact_pregame_player_history(
            pd.DataFrame({"PTS": [20]}), cutoff, "PHI", "MIL"), {})


if __name__ == "__main__":
    unittest.main()
