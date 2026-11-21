"""Server-side what-if validation. All fixtures/results are synthetic test data."""
from datetime import timedelta
from unittest.mock import patch

import pandas as pd
from bestbets_simulations_canvas import scenario_for_entitled_user


def test_scenario_builder_permissions_and_assumptions():
    day = (pd.Timestamp.now(tz="UTC") + pd.Timedelta(days=2)).date().isoformat()
    start = (pd.Timestamp.now(tz="UTC") + pd.Timedelta(days=2)).isoformat()
    fixture = {"id": "401999333", "away": "NYK", "home": "BOS",
               "state": "scheduled", "start": start}
    calls = []

    def fake_model(day_in, id_in, model_id, pace_pct=0):
        calls.append(pace_pct)
        base = 113.0 + pace_pct
        return {"away_points": base, "home_points": 117.0 + pace_pct,
                "total_points": 230.0 + 2 * pace_pct,
                "away_win_pct": 49.0, "home_win_pct": 51.0}

    with patch("bestbets_simulations_canvas.premium_entitled", return_value=False):
        denied = scenario_for_entitled_user(day, fixture["id"], "research_form_v74", 3)
        assert "Premium" in denied["error"]
        assert not calls, "Free user must not run simulations"

    with (patch("bestbets_simulations_canvas.premium_entitled", return_value=True),
          patch("bestbets_simulations_canvas._day_for_simulations",
                return_value={"games": [fixture]}),
          patch("bestbets_simulations_canvas._game_simulation",
                side_effect=fake_model)):
        for invalid in (-6, 6, 3.5, True, "3", None):
            assert "error" in scenario_for_entitled_user(
                day, fixture["id"], "research_form_v74", invalid)
        assert not calls, "Invalid inputs must not reach the model"
        result = scenario_for_entitled_user(
            day, fixture["id"], "research_form_v74", 3)
        assert calls == [0, 3]
        assert result["hypothetical"] is True
        assert result["n_sims"] == 5000
        assert result["baseline"]["total_points"] == 230
        assert result["scenario"]["total_points"] == 236
        assert result["pace_pct"] == 3

    past_fixture = {**fixture, "state": "final"}
    with (patch("bestbets_simulations_canvas.premium_entitled", return_value=True),
          patch("bestbets_simulations_canvas._day_for_simulations",
                return_value={"games": [past_fixture]})):
        assert "error" in scenario_for_entitled_user(
            day, fixture["id"], "research_form_v74", 2)


if __name__ == "__main__":
    test_scenario_builder_permissions_and_assumptions()
    print("Scenario Builder: server permission, bounds and future-game isolation OK")
