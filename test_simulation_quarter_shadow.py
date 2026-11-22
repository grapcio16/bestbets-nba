"""HOOPZARO quarter shadow regression: no invented totals and no future games."""
import unittest
import numpy as np
import pandas as pd

from simulation_quarter_shadow import (
    MODEL_IDS, build_quarter_forecasts, forecast_game_quarters,
    generate_quarter_draws, quarter_performance_metrics)
from tracker_automation import run_quarter_cycle


GAME = {
    "game_id": "402888888", "away": "DET", "home": "ATL",
    "start_utc": pd.Timestamp("2026-11-22T22:00:00Z")
}


def history():
    rows = []
    for idx in range(9):
        for team in ("ATL", "DET"):
            if team == "ATL":
                home, away = "ATL", "BKN"
                home_q, away_q = [36, 29, 24, 25], [24, 25, 26, 27]
            else:
                home, away = "ORL", "DET"
                home_q, away_q = [27, 26, 28, 28], [21, 29, 39, 22]
            row = {
                "game_id": str(402700000 + idx * 2 + (team == "DET")),
                "start_utc": pd.Timestamp("2026-11-01T00:00:00Z") + pd.Timedelta(days=idx),
                "home": home, "away": away, "home_score": sum(home_q),
                "away_score": sum(away_q), "status_code": 3,
            }
            row.update({f"home_q{q}": home_q[q-1] for q in range(1, 5)})
            row.update({f"away_q{q}": away_q[q-1] for q in range(1, 5)})
            rows.append(row)
    return pd.DataFrame(rows)


class QuarterShadowTest(unittest.TestCase):
    def setUp(self):
        self.past = history()
        rng = np.random.default_rng(44)
        self.home = rng.integers(100, 131, size=5000)
        self.away = rng.integers(97, 126, size=5000)

    def test_all_game_models_keep_every_draw_exact(self):
        for base, quarter_id in MODEL_IDS.items():
            with self.subTest(model=base):
                result = generate_quarter_draws(
                    self.past, GAME, self.home, self.away, base)
                self.assertIsNotNone(result)
                home_q, away_q, evidence = result
                np.testing.assert_array_equal(home_q.sum(axis=1), self.home)
                np.testing.assert_array_equal(away_q.sum(axis=1), self.away)
                self.assertGreaterEqual(evidence["home_sample"], 6)
                rows = forecast_game_quarters(
                    self.past, GAME, self.home, self.away, base)
                self.assertEqual(len(rows), 4)
                self.assertEqual({r["quarter"] for r in rows}, {1, 2, 3, 4})
                self.assertEqual({r["model_id"] for r in rows}, {quarter_id})
                self.assertAlmostEqual(
                    sum(r["home_points"] for r in rows), self.home.mean(), delta=.01)
                self.assertAlmostEqual(
                    sum(r["away_points"] for r in rows), self.away.mean(), delta=.01)
                for r in rows:
                    self.assertAlmostEqual(
                        r["home_win_pct"] + r["away_win_pct"] + r["tie_pct"], 100)

    def test_profile_and_draws_not_changed_by_future_results(self):
        base = "auto_context_full_v75"
        before = forecast_game_quarters(
            self.past, GAME, self.home, self.away, base)
        next_day = self.past.iloc[0].copy()
        next_day["game_id"] = "402999999"
        next_day["start_utc"] = GAME["start_utc"] + pd.Timedelta(hours=1)
        next_day["home_q1"] = 50
        next_day["home_q2"] = 18
        next_day["home_q3"] = 18
        next_day["home_q4"] = 24
        next_day["home_score"] = 110
        changed = pd.concat([self.past, pd.DataFrame([next_day])], ignore_index=True)
        after = forecast_game_quarters(
            changed, GAME, self.home, self.away, base)
        self.assertEqual(before, after)

    def test_insufficient_history_does_not_invent_quarters(self):
        no_quarters = self.past.drop(columns=["home_q4"])
        self.assertEqual(forecast_game_quarters(
            no_quarters, GAME, self.home, self.away, "auto_legacy_v72"), [])
        self.assertEqual(forecast_game_quarters(
            self.past, GAME, self.home[:10], self.away, "auto_legacy_v72"), [])

    def test_tracker_reports_four_models_without_reforecasting_scores(self):
        scenarios = [{
            "game": GAME, "base_model_id": model,
            "home_draws": self.home, "away_draws": self.away
        } for model in MODEL_IDS]
        rows = build_quarter_forecasts(self.past, scenarios)
        self.assertEqual(len(rows), 16)
        saved_rows = []
        result = run_quarter_cycle(
            pd.DataFrame(), self.past, pd.Timestamp("2026-11-22T10:00:00Z"),
            save_quarter_forecasts=lambda data, season: (
                saved_rows.extend(data) or {"saved": len(data)}),
            settle_quarter_results=lambda completed: 0,
            parent_scenarios=scenarios,
        )
        self.assertEqual(result["new_quarter_rows"], 16)
        self.assertEqual(result["parent_models_with_quarter_forecasts"], 4)
        self.assertEqual(len(saved_rows), 16)

    def test_grouped_accuracy_excludes_unsettled(self):
        rows = forecast_game_quarters(
            self.past, GAME, self.home, self.away, "auto_legacy_v72")
        settled = []
        for row in rows:
            settled.append({
                **row, "home_actual": 28, "away_actual": 26,
            })
        settled.append({**rows[0], "home_actual": None, "away_actual": None})
        metrics = quarter_performance_metrics(pd.DataFrame(settled))
        self.assertEqual(len(metrics), 4)
        self.assertTrue((metrics["n"] == 1).all())
        self.assertTrue((metrics["team_mae"] >= 0).all())
        self.assertTrue((metrics["brier_3way"] >= 0).all())


    def test_admin_report_compares_identical_finished_games(self):
        from admin_model_performance import build_quarter_report
        records = []
        for model in MODEL_IDS:
            rows = forecast_game_quarters(
                self.past, GAME, self.home, self.away, model)
            records.extend({
                **row, "forecast_time_utc": pd.Timestamp("2026-11-22T10:00:00Z"),
                "home_actual": 30, "away_actual": 27,
            } for row in rows)
        report = build_quarter_report(pd.DataFrame(records))
        self.assertEqual(report["paired_games"], 1)
        self.assertEqual(len(report["models"]), 4)
        self.assertEqual(len(report["paired"]), 4)
        self.assertTrue(all(m["n_quarters"] == 4 for m in report["paired"]))


if __name__ == "__main__":
    unittest.main()
