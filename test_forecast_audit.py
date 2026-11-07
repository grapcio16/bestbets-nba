"""Offline regression tests for frozen NBA forecast evaluation."""
import unittest
import pandas as pd
from forecast_audit import evaluate_frozen_predictions


class ForecastAuditTests(unittest.TestCase):
    def test_known_forecast_scores_and_winner(self):
        a=pd.DataFrame([{
            "game_id":"x","forecast_time_utc":"2026-11-06T20:00:00Z",
            "start_utc":"2026-11-07T02:00:00Z","away_points":111,
            "home_points":114,"away_win_pct":40,"home_win_pct":60
        }])
        b=pd.DataFrame([{"game_id":"x","away_score":105,"home_score":120}])
        _,metrics=evaluate_frozen_predictions(a,b)
        self.assertEqual(metrics["games"],1)
        self.assertEqual(metrics["winner_accuracy"],1.)
        self.assertEqual(metrics["total_mae"],0.)
        self.assertEqual(metrics["team_mae"],6.)
        self.assertAlmostEqual(metrics["brier"],0.16)

    def test_reject_post_tipoff_prediction(self):
        a=pd.DataFrame([{
            "game_id":"x","forecast_time_utc":"2026-11-07T03:00:00Z",
            "start_utc":"2026-11-07T02:00:00Z","away_points":111,
            "home_points":114,"away_win_pct":40,"home_win_pct":60
        }])
        b=pd.DataFrame([{"game_id":"x","away_score":105,"home_score":120}])
        _,metrics=evaluate_frozen_predictions(a,b)
        self.assertEqual(metrics["games"],0)

    def test_reject_duplicate_ids(self):
        a=pd.DataFrame([{
            "game_id":"x","forecast_time_utc":"2026-11-06T20:00:00Z",
            "start_utc":"2026-11-07T02:00:00Z","away_points":111,
            "home_points":114,"away_win_pct":40,"home_win_pct":60
        }])
        b=pd.DataFrame([{"game_id":"x","away_score":105,"home_score":120}])
        with self.assertRaises(ValueError):
            evaluate_frozen_predictions(pd.concat([a,a],ignore_index=True),b)

if __name__=="__main__":
    unittest.main()
