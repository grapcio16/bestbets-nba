"""Admin report: historical-only scores and independent model separation."""
import unittest
import pandas as pd

from admin_model_performance import build_model_report
from tracker_postgres import _report_frame


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
    def test_postgres_rows_have_unique_model_id_column_and_render_report(self):
        raw = forecast("first", "401000001", settled=True)
        raw.update(total_points=222.0, source="test", warning="", settled_at_utc=None)
        frame = _report_frame([raw])
        self.assertFalse(frame.columns.duplicated().any())
        report = build_model_report(frame, season="2026-27")
        self.assertEqual(len(report["models"]), 1)
        self.assertEqual(report["models"][0]["snapshots"], 1)
        self.assertEqual(report["models"][0]["evaluated"], 1)

    def test_empty_postgres_archive_has_no_duplicate_columns(self):
        frame = _report_frame([])
        self.assertFalse(frame.columns.duplicated().any())
        self.assertEqual(build_model_report(frame, season="2026-27")["models"], [])

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

    def test_paired_comparison_uses_only_same_pregame_settled_games(self):
        frame = pd.DataFrame([
            forecast("first", "401000001", settled=True),
            forecast("second", "401000001", settled=True),
            forecast("first", "401000002", settled=True),
            forecast("second", "401000003", settled=True, late=True),
        ])
        report = build_model_report(frame, season="2026-27")
        paired = report["paired_comparison"]
        self.assertEqual(paired["games"], 1)
        by_name = {model["id"]: model["metrics"] for model in paired["models"]}
        self.assertEqual(by_name["first"]["games"], 1)
        self.assertEqual(by_name["second"]["games"], 1)
        self.assertEqual(by_name["first"]["total_mae"], 7.0)
        self.assertEqual(by_name["second"]["total_mae"], 12.0)

    def test_missing_expected_columns_is_handled(self):
        report = build_model_report(pd.DataFrame([{"model_id": "first"}]), season="2026-27")
        self.assertTrue(report["error"])
        self.assertEqual(report["models"], [])

    def test_previous_v75_ids_combine_without_double_counting_games(self):
        frame = pd.DataFrame([
            forecast("auto_context_venue_rest_v75", "401000001", settled=True),
            forecast("auto_context_injury_minutes_v75", "401000001", settled=True),
            forecast("auto_context_venue_rest_v75", "401000002", settled=True),
        ])
        report = build_model_report(frame, season="2026-27")
        self.assertEqual(len(report["models"]), 1)
        model = report["models"][0]
        self.assertEqual(model["id"], "auto_context_full_v75")
        self.assertEqual(model["label"], "V7.5 · Pełny kontekst")
        self.assertEqual(model["snapshots"], 2)
        self.assertEqual(model["evaluated"], 2)
        recent = {row["game_id"]: row for row in model["recent"]}
        self.assertEqual(recent["401000001"]["origin_model_id"],
                         "auto_context_injury_minutes_v75")

    def test_v75_combined_prefers_fresh_injury_and_ignores_late_duplicates(self):
        frame = pd.DataFrame([
            {**forecast("auto_context_venue_rest_v75", "401000001", settled=True),
             "warning": "only venue/rest"},
            {**forecast("auto_context_injury_minutes_v75", "401000001", settled=True),
             "warning": "ESPN OUT"},
            {**forecast("auto_context_full_v75", "401000001", settled=True, late=True),
             "warning": "ESPN OUT A/H"},
            {**forecast("auto_context_full_v75", "401000002", settled=True),
             "warning": "V7.5 pełny kontekst; ESPN OUT A/H"},
        ])
        report = build_model_report(frame, season="2026-27")
        self.assertEqual(len(report["models"]), 1)
        self.assertEqual(report["models"][0]["snapshots"], 2)
        self.assertEqual(report["models"][0]["evaluated"], 2)
        self.assertEqual(report["models"][0]["recent"][-1]["origin_model_id"],
                         "auto_context_injury_minutes_v75")


if __name__ == "__main__":
    unittest.main()
