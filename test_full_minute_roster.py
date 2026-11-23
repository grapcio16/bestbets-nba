"""Premium selected-game Player Minutes roster; synthetic offline provider data."""
import sys
import types
import unittest
from unittest.mock import patch

import pandas as pd

import bestbets_simulations_canvas as canvas


class FullMinuteRosterTests(unittest.TestCase):
    def test_both_espn_teams_loaded_and_stale_source_not_claimed_full(self):
        from roster_data import team_roster
        del team_roster
        canvas._minute_roster_for_fixture.clear()
        def source(team):
            if team == "DET":
                return pd.DataFrame([
                    {"PLAYER_NAME": "Starter", "POSITION": "PG", "ROSTER_STATUS": "active"},
                    {"PLAYER_NAME": "Reserve", "POSITION": "C", "ROSTER_STATUS": "active"},
                ]), {"stale": False}
            return pd.DataFrame([{"PLAYER_NAME": "Hawk", "POSITION": "SG",
                                  "ROSTER_STATUS": "active"}]), {"stale": False}
        with patch("roster_data.team_roster", side_effect=source) as fetch:
            rows, verified, warning = canvas._minute_roster_for_fixture("DET", "ATL")
        self.assertEqual(fetch.call_count, 2)
        self.assertEqual(set(verified), {"DET", "ATL"})
        self.assertFalse(warning)
        self.assertEqual({r["name"] for r in rows}, {"Starter", "Reserve", "Hawk"})
        self.assertEqual({r["team"] for r in rows}, {"DET", "ATL"})
        self.assertEqual({r["position"] for r in rows}, {"PG", "SG", "C"})

    def test_partial_roster_does_not_claim_complete(self):
        canvas._minute_roster_for_fixture.clear()
        def source(team):
            if team == "DET":
                return pd.DataFrame([{"PLAYER_NAME": "Starter", "POSITION": "PG"}]), {"stale": False}
            raise TimeoutError("ESPN unavailable")
        with patch("roster_data.team_roster", side_effect=source):
            rows, verified, warning = canvas._minute_roster_for_fixture("DET", "ATL")
        self.assertEqual(verified, ["DET"])
        self.assertEqual(len(rows), 1)
        self.assertIn("nie udostępnił", warning)

    def test_matchup_roster_does_not_fabricate_projections_for_bench(self):
        day = "2026-11-23"
        upcoming = (pd.Timestamp.now(tz="UTC") + pd.Timedelta(days=2)).isoformat()
        fixture = {"id": "401999555", "state": "scheduled",
                   "start": upcoming, "away": "DET", "home": "ATL"}
        table = pd.DataFrame([
            {"Zawodnik": "Starter", "Drużyna": "DET", "PTS": 19.,
             "REB": 5., "AST": 4.},
        ])
        roster = [
            {"name": "Starter", "team": "DET", "position": "PG"},
            {"name": "Reserve", "team": "DET", "position": "C"},
            {"name": "Hawk", "team": "ATL", "position": "SG"},
        ]
        dummy = types.ModuleType("simulation_view")
        dummy.matchup_players_cached = lambda *_a, **_kw: (table, {})
        now = pd.Timestamp.now(tz="UTC")
        report = {"fresh": True, "checked_at": now.isoformat(),
                  "valid_until": (now + pd.Timedelta(minutes=90)).isoformat(),
                  "rows": []}
        with patch.dict(sys.modules, {"simulation_view": dummy}), \
             patch.object(canvas, "_day_for_simulations",
                          return_value={"games": [fixture]}), \
             patch.object(canvas, "_history_for_simulations",
                          return_value=(pd.DataFrame(), "")), \
             patch.object(canvas, "_advanced_from_verified_cache",
                          return_value=pd.DataFrame()), \
             patch("espn_player_data.matchup_espn_logs",
                   return_value=(pd.DataFrame(), {})), \
             patch.object(canvas, "_minute_roster_for_fixture",
                          return_value=(roster, ["DET", "ATL"], "")), \
             patch.object(canvas, "_selected_injury_watch",
                          return_value=report):
            canvas._game_players.clear()
            result = canvas._game_players(day, fixture["id"], "research_form_v74")
        self.assertEqual(len(result["players"]), 1)
        self.assertEqual(len(result["minute_roster"]), 3)
        by_name = {r["name"]: r for r in result["minute_roster"]}
        self.assertEqual(by_name["Starter"]["projection_index"], 0)
        self.assertIsNone(by_name["Reserve"]["projection_index"])
        self.assertIsNone(by_name["Hawk"]["projection_index"])
        self.assertIsNone(result["players"][0]["minutes"])
        self.assertEqual(result["players"][0]["minutes_sample"], 0)

    def test_free_user_never_triggers_roster_fetch(self):
        with patch.object(canvas, "premium_entitled", return_value=False), \
             patch.object(canvas, "_minute_roster_for_fixture") as roster:
            response = canvas.simulation_for_entitled_user(
                "2026-11-23", "401999555", players=True)
        self.assertIn("Premium", response["error"])
        roster.assert_not_called()


if __name__ == "__main__":
    unittest.main()
