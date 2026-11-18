"""Security and mode isolation checks for the live Premium canvas."""
import sys
import types
import unittest
from unittest.mock import patch

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


if __name__ == "__main__":
    unittest.main()
