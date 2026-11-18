"""Admin report: historical-only scores and independent model separation."""
import unittest
import pandas as pd

from admin_model_performance import build_model_report


def forecast(model, game_id, *, settled=False, late=False):
    return {
        "model_id": model, "game_id": game_id, "season": "2026-27",
        "home": "SAS", "away": "POR",
        "forecast_time_utc": "2026-11-19T01:30:00Z" if late else "2026-11-17T12:00:00Z",
        "start_utc": "2026-11-18T01:30:00Z",
        "home_points": 115.0 if model == "first" else 110.0,
        "away_points": 107.0, "home_win_pct": 60.0, "away_win_pct": 40.0,
        "home_score": 119 if settled else None,
        "away_score": 110 if settled else None,
    }


class ModelReportTests(unittest.TestCase):
    def test_empty_report_does_not_fabricate_accuracy(self):
        report = build_model_report(pd.DataFrame(), season="2026-27")
        self.assertEqual(report["models"], [])

    def test_before_first_settlement_reports_no_metrics(self):
        report = build_model_report(pd.DataFrame([
            forecast("first", "401000001"), forecast("second", "401000001")
        ]), season="2026-27")
        self.assertEqual(len(report["models"]), 2)
        for model in report["models"]:
            self.assertEqual(model["snapshots"], 1)
            self.assertEqual(model["evaluated"], 0)
            self.assertIsNone(model["metrics"]["winner_accuracy"])
            self.assertIsNone(model["recent"][0]["home_actual"])

    def test_settlements_are_separated_by_model_and_exclude_late_forecasts(self):
        report = build_model_report(pd.DataFrame([
            forecast("first", "401000001", settled=True),
            forecast("second", "401000001", settled=True),
            forecast("first", "401000002", settled=True, late=True),
        ]), season="2026-27")
        first, second = report["models"]
        self.assertEqual(first["snapshots"], 2)
        self.assertEqual(first["settled"], 2)
        self.assertEqual(first["evaluated"], 1)
        self.assertEqual(second["evaluated"], 1)
        self.assertEqual(first["metrics"]["total_mae"], 7.0)
        self.assertEqual(second["metrics"]["total_mae"], 12.0)

    def test_missing_expected_columns_is_handled(self):
        report = build_model_report(pd.DataFrame([{"model_id": "first"}]), season="2026-27")
        self.assertTrue(report["error"])
        self.assertEqual(report["models"], [])


if __name__ == "__main__":
    unittest.main()
