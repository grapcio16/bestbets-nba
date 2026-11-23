"""Security and mode isolation checks for the live Premium canvas."""
import sys
import types
import unittest
from unittest.mock import patch
import pandas as pd

try:
    import streamlit
except ModuleNotFoundError:
    fake = types.ModuleType("streamlit")
    fake.cache_data = lambda **_kwargs: lambda func: func
    sys.modules["streamlit"] = fake

import bestbets_simulations_canvas as canvas


class ModelChoiceTests(unittest.TestCase):
    def test_three_modes_are_accepted_and_passed_to_model(self):
        with patch.object(canvas, "premium_entitled", return_value=True), \
             patch.object(canvas, "_game_simulation", return_value={"home_points": 111}) as calculate:
            for model_id in ("legacy_v72", "research_form_v74", "research_context_v75"):
                result = canvas.simulation_for_entitled_user(
                    "2026-11-19", "401123456", model_id=model_id)
                self.assertEqual(result["home_points"], 111)
                calculate.assert_called_with("2026-11-19", "401123456", model_id)

    def test_unknown_model_never_reaches_simulation(self):
        with patch.object(canvas, "premium_entitled", return_value=True), \
             patch.object(canvas, "_game_simulation") as calculate:
            result = canvas.simulation_for_entitled_user(
                "2026-11-19", "401123456", model_id="hidden_model")
            self.assertIn("error", result)
            calculate.assert_not_called()

    def test_nonpremium_cannot_calculate_either_model(self):
        with patch.object(canvas, "premium_entitled", return_value=False), \
             patch.object(canvas, "_game_simulation") as calculate, \
             patch.object(canvas, "_game_players") as player_calculation:
            for model_id in ("legacy_v72", "research_form_v74", "research_context_v75"):
                for players in (True, False):
                    result = canvas.simulation_for_entitled_user(
                        "2026-11-19", "401123456", players=players, model_id=model_id)
                    self.assertIn("error", result)
            calculate.assert_not_called()
            player_calculation.assert_not_called()

    def test_v75_out_player_has_zero_minutes_without_fake_points(self):
        table = pd.DataFrame([
            {"Zawodnik": "Sample Starter", "Drużyna": "BOS", "PTS": 22.2,
             "REB": 5.5, "AST": 4.6, "Minuty": 30, "Próba występów": 7},
            {"Zawodnik": "Sample Guard", "Drużyna": "NYK", "PTS": 15.0,
             "REB": 3.0, "AST": 8.0, "Minuty": 28, "Próba występów": 7},
            # A stale/unmatched roster entry must NEVER appear in BOS–NYK.
            {"Zawodnik": "Unrelated Player", "Drużyna": "LAL", "PTS": 50.0,
             "REB": 10.0, "AST": 10.0, "Minuty": 38, "Próba występów": 12},
        ])
        evidence = {"players": {
            ("BOS", "samplestarter"): {"status": "Out", "minutes": 0, "sample": 7},
            ("NYK", "sampleguard"): {"status": "Niezweryfikowany", "minutes": 28, "sample": 7},
        }, "warning": "Raport ESPN"}
        # Keep the fixture genuinely upcoming. A fixed November date made
        # this test fail every day after tipoff, despite correct OUT logic.
        game = {"id": "401123456", "home": "BOS", "away": "NYK",
                "start": (pd.Timestamp.now(tz="UTC") + pd.Timedelta(days=2)).isoformat(),
                "state": "scheduled"}
        dummy = types.ModuleType("simulation_view")
        dummy.matchup_players_cached = lambda *_a, **_kw: (table, {})
        checked = pd.Timestamp.now(tz="UTC")
        report = {"fresh": True, "checked_at": checked.isoformat(),
                  "valid_until": (checked + pd.Timedelta(minutes=90)).isoformat(),
                  "rows": [{"name": "Sample Starter", "team": "BOS", "status": "Out"}]}
        with patch.dict(sys.modules, {"simulation_view": dummy}), \
             patch.object(canvas, "_day_for_simulations", return_value={"games": [game]}), \
             patch.object(canvas, "_history_for_simulations", return_value=(pd.DataFrame(), "")), \
             patch.object(canvas, "_advanced_from_verified_cache", return_value=pd.DataFrame()), \
             patch.object(canvas, "_v75_player_evidence", return_value=(table, evidence)), \
             patch.object(canvas, "_selected_injury_watch", return_value=report), \
             patch.object(canvas, "_minute_roster_for_fixture", return_value=([], [], "")), \
             patch("espn_player_data.matchup_espn_logs",
                   return_value=(pd.DataFrame(), {})):
            canvas._game_players.clear()
            result = canvas._game_players("2026-11-19", "401123456", "research_context_v75")
        self.assertEqual(len(result["players"]), 1)
        self.assertEqual(result["excluded_players"][0]["name"], "Sample Starter")
        self.assertEqual(result["excluded_players"][0]["status"], "Out")
        by_name = {entry["name"]: entry for entry in result["players"]}
        self.assertNotIn("Sample Starter", by_name)
        self.assertEqual(by_name["Sample Guard"]["minutes"], 28)
        self.assertEqual(by_name["Sample Guard"]["pts"], 15.0)


if __name__ == "__main__":
    unittest.main()
