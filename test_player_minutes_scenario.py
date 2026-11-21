"""V7.5 player-minute sensitivity: all players/fixtures below are synthetic."""
from unittest.mock import patch

import pandas as pd
from bestbets_simulations_canvas import player_minutes_scenario_for_entitled_user


def test_minute_sensitivity_permissions_and_data():
    day = (pd.Timestamp.now(tz="UTC") + pd.Timedelta(days=2)).date().isoformat()
    start = (pd.Timestamp.now(tz="UTC") + pd.Timedelta(days=2)).isoformat()
    fixture = {
        "id": "401999345", "away": "NYK", "home": "BOS",
        "state": "scheduled", "start": start,
    }
    player = {
        "name": "Test Athlete", "team": "NYK",
        "minutes": 30.0, "minutes_sample": 4,
        "pts": 24.0, "reb": 6.0, "ast": 9.0,
        "availability": "Questionable",
    }
    calls = []

    def fake_roster(date, game_id, model_id):
        calls.append((date, game_id, model_id))
        return {"players": [player], "error": ""}

    def scenario(**changes):
        return player_minutes_scenario_for_entitled_user(
            day, fixture["id"], changes.pop("model_id", "research_context_v75"),
            changes.pop("player_name", "Test Athlete"),
            changes.pop("team", "NYK"),
            changes.pop("minute_delta", 5))

    with patch("bestbets_simulations_canvas.premium_entitled", return_value=False):
        assert "Premium" in scenario()["error"]
        assert not calls, "No source/roster fetch for a free account"

    with (patch("bestbets_simulations_canvas.premium_entitled", return_value=True),
          patch("bestbets_simulations_canvas._day_for_simulations",
                return_value={"games": [fixture]}),
          patch("bestbets_simulations_canvas._game_players", side_effect=fake_roster)):
        for delta in (-6, 6, 3.5, True, None, "3"):
            assert "error" in scenario(minute_delta=delta)
        assert "error" in scenario(model_id="research_form_v74")
        assert "error" in scenario(team="BOS")
        assert "error" in scenario(player_name="Someone Else")
        assert calls == [(day, fixture["id"], "research_context_v75"),
                         (day, fixture["id"], "research_context_v75")], calls
        # Above two calls correspond only to team/player mismatch after
        # fixture validation. All invalid deltas/model/team are rejected first.
        calls.clear()
        result = scenario()
        assert result["baseline_minutes"] == 30.0
        assert result["scenario_minutes"] == 35.0
        assert result["baseline"]["pts"] == 24.0
        assert result["scenario"]["pts"] == 28.0
        assert result["scenario"]["reb"] == 7.0
        assert result["scenario"]["ast"] == 10.5
        assert result["scenario"]["pra"] == 45.5
        assert result["baseline"]["pra"] == 39
        assert result["minutes_sample"] == 4
        assert result["availability"] == "Questionable"
        assert result["hypothetical"] is True
        assert "win_pct" not in result and "n_sims" not in result
        assert calls == [(day, fixture["id"], "research_context_v75")]

        # An official-looking OUT is never silently treated as an active player.
        player["availability"] = "Out"
        assert "OUT" in scenario()["error"]
        player["availability"] = "Niezweryfikowany"
        player["minutes_sample"] = 2
        assert "próbki" in scenario()["error"]
        player["minutes_sample"] = 4
        player["minutes"] = 43
        assert "5–44" in scenario()["error"]
        player["minutes"] = 30
        player["ast"] = None
        assert "Niepełne" in scenario()["error"]
        player["ast"] = 9.0

    past = {**fixture, "state": "final"}
    with (patch("bestbets_simulations_canvas.premium_entitled", return_value=True),
          patch("bestbets_simulations_canvas._day_for_simulations",
                return_value={"games": [past]}),
          patch("bestbets_simulations_canvas._game_players", side_effect=fake_roster)):
        calls.clear()
        assert "error" in scenario()
        assert not calls


if __name__ == "__main__":
    test_minute_sensitivity_permissions_and_data()
    print("V7.5 minute sensitivity: Premium, fixture, real samples, OUT and bounds OK")
