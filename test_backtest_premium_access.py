"""Walk-forward report is strictly on-demand and server Premium gated."""
from unittest.mock import patch

from bestbets_simulations_canvas import backtest_for_entitled_user


def test_permission_controls_historical_model_report():
    with (patch("bestbets_simulations_canvas.premium_entitled", return_value=False),
          patch("bestbets_simulations_canvas._cached_walkforward_report")
          as cached):
        result = backtest_for_entitled_user()
        assert "Premium" in result["error"]
        cached.assert_not_called()

    research = {
        "season": "2026-27", "games": 40,
        "max_games": 40, "models": [
            {"key": "old", "total_mae": 14.0, "team_mae": 10.0,
             "winner_accuracy_pct": 55.0, "brier": .24},
            {"key": "new", "total_mae": 13.0, "team_mae": 9.0,
             "winner_accuracy_pct": 57.5, "brier": .23},
            {"key": "enriched", "total_mae": 12.0, "team_mae": 8.0,
             "winner_accuracy_pct": 60.0, "brier": .22},
            {"key": "v75", "total_mae": 12.0, "team_mae": 8.0,
             "winner_accuracy_pct": 60.0, "brier": .22},
        ],
        "roi_available": False, "odds_available": False,
        "limitation": "Historical offline research core only",
    }
    with (patch("bestbets_simulations_canvas.premium_entitled", return_value=True),
          patch("bestbets_simulations_canvas._season_at",
                return_value="2026-27") as season,
          patch("bestbets_simulations_canvas._cached_walkforward_report",
                return_value=research) as cached):
        result = backtest_for_entitled_user()
        assert result == research
        season.assert_called_once()
        cached.assert_called_once_with("2026-27")
        assert not result["roi_available"] and not result["odds_available"]


if __name__ == "__main__":
    test_permission_controls_historical_model_report()
    print("Walk-forward Premium access and server-selected season OK")
