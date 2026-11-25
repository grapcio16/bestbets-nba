"""Strict research scorecard QA: shared pregame sample and zero-hindsight."""
import unittest

from v8_shadow.evaluation import evaluate_records


def v8(model="v8_possessions_shadow_v01", **overrides):
    record = {
        "game_id": "401909317", "model_id": model,
        "issued_at": "2026-11-25T17:00:50Z",
        "start_utc": "2026-11-25T22:00:00Z",
        "settled_at": "2026-11-26T04:00:00Z",
        "home": "PHI", "away": "MIA", "actual_home": 125,
        "actual_away": 118, "scenario_home": 127,
        "scenario_away": 117, "mean_home": 120,
        "mean_away": 120, "home_win_pct": 65,
        "training_examples": 79,
        "report": {
            "home_p10_p50_p90": [95, 120, 140],
            "away_p10_p50_p90": [90, 120, 135],
            "total_p10_p50_p90": [200, 235, 260],
        },
    }
    return {**record, **overrides}


def v7(model="auto_legacy_v72", **overrides):
    record = {
        "game_id": "401909317", "model_id": model,
        "forecast_time_utc": "2026-11-25T16:00:00Z",
        "start_utc": "2026-11-25T22:00:00Z",
        "settled_at_utc": "2026-11-26T04:00:00Z",
        "home": "PHI", "away": "MIA", "home_score": 125,
        "away_score": 118, "home_points": 117,
        "away_points": 112, "home_win_pct": 60,
    }
    return {**record, **overrides}


class ScorecardTest(unittest.TestCase):
    def test_unsettled_rows_are_only_waiting_not_success(self):
        forecast = v8(actual_home=None, actual_away=None, settled_at=None)
        result = evaluate_records([forecast], [])
        self.assertEqual(result["status"], "waiting_for_settled_games")
        self.assertEqual(result["v8_archived_by_version"]["v8_possessions_shadow_v01"], 1)
        self.assertEqual(result["common_game_comparisons"], [])
        self.assertEqual(result["v8_pregame_rows_without_valid_settlement"], 1)

    def test_common_games_compare_same_actual_for_v8_and_v7(self):
        a = v8()
        b = v8(model="v8_possessions_shadow_v02", training_examples=144,
               scenario_home=129, scenario_away=119,
               mean_home=123, mean_away=119)
        c = v7()
        result = evaluate_records([a, b], [c])
        self.assertEqual(result["status"], "prospective_settlement_available")
        self.assertEqual(len(result["common_game_comparisons"]), 3)
        self.assertTrue(all(x["same_game_n"] == 1
                            for x in result["common_game_comparisons"]))
        inter = [x for x in result["common_game_comparisons"]
                 if x["comparison"].startswith("V8 version")][0]
        self.assertTrue(inter["historical_training_sample_differs"])
        self.assertEqual(inter["left_training_sample_sizes"], [79])
        self.assertEqual(inter["right_training_sample_sizes"], [144])
        self.assertEqual(inter["left_metrics"]["scenario_tied_final_count"], 0)
        self.assertEqual(inter["right_metrics"]["home_80pct_interval_coverage"], 100.0)

    def test_v8_v01_tie_scenario_is_logged_not_rewritten(self):
        result = evaluate_records([v8(scenario_home=117, scenario_away=117)], [])
        self.assertEqual(
            result["model_metrics"]["v8_possessions_shadow_v01"]
            ["scenario_tied_final_count"], 1)

    def test_mismatched_home_away_scores_excluded_from_common_sample(self):
        result = evaluate_records([v8()], [v7(away_score=116)])
        self.assertEqual(result["common_game_comparisons"], [])

    def test_no_retroactive_or_close_to_tipoff_predictions(self):
        late = v8(issued_at="2026-11-25T21:55:00Z")
        hindsight = v8(issued_at="2026-11-26T00:05:00Z")
        settled_early = v8(settled_at="2026-11-25T20:05:00Z")
        for r in (late, hindsight, settled_early):
            result = evaluate_records([r], [v7()])
            self.assertEqual(result["status"], "waiting_for_settled_games")
            self.assertEqual(result["common_game_comparisons"], [])
        baseline_late = v7(forecast_time_utc="2026-11-25T21:59:00Z")
        result = evaluate_records([v8()], [baseline_late])
        self.assertEqual(result["common_game_comparisons"], [])

    def test_wrong_basketball_final_or_probability_rejected(self):
        for bad in (v8(actual_home=118, actual_away=118),
                    v8(home_win_pct=130), v8(mean_home=None),
                    v8(game_id="wrong")):
            result = evaluate_records([bad], [])
            self.assertEqual(result["status"], "waiting_for_settled_games")

    def test_duplicate_archived_model_and_game_rejected(self):
        with self.assertRaisesRegex(ValueError, "duplicate"):
            evaluate_records([v8(), v8()], [])

    def test_missing_interval_data_returns_null_not_invented_coverage(self):
        r = evaluate_records([v8(report={})], [])
        m = r["model_metrics"]["v8_possessions_shadow_v01"]
        self.assertIsNone(m["home_80pct_interval_coverage"])
        self.assertEqual(m["home_intervals_checked"], 0)

    def test_no_bets_roi_claim(self):
        result = evaluate_records([v8()], [v7()])
        self.assertNotIn("roi", str(result).lower())
        self.assertNotIn("profit", str(result).lower())


if __name__ == "__main__":
    unittest.main()
