"""Isolated V8.03 collector and PostgreSQL archive integration tests."""
import os
import unittest
from unittest.mock import Mock
import pandas as pd
from v8_shadow.worker import collect_v803


class CollectorTests(unittest.TestCase):
    def setUp(self):
        self.t = pd.Timestamp("2026-11-27T12:00:00Z")
        self.events = [
            {"game_id": str(i), "start_utc": self.t + pd.Timedelta(hours=2),
             "home": "T01", "away": "T02"} for i in range(1, 4)]
        self.evidence = [{"fixture": True}]

    def test_disabled_or_not_ready_never_calls_predictor(self):
        predict = Mock(side_effect=AssertionError("unexpected call"))
        for enabled, ready in ((False, True), (True, False), (False, False)):
            self.assertEqual(collect_v803(self.evidence, self.events, self.t,
                enabled=enabled, ready=ready, predict=predict), ([], {}))
        predict.assert_not_called()

    def test_failure_isolated_and_common_evidence_cutoff(self):
        output = {"status": "shadow_only", "model_id": "v8_possessions_shadow_v03"}
        predict = Mock(side_effect=[ValueError("fixture"), {"status": "insufficient_evidence"}, output])
        forecasts, skips = collect_v803(self.evidence, self.events, self.t,
            enabled=True, ready=True, predict=predict, now=lambda: self.t)
        self.assertEqual(forecasts, [output])
        self.assertEqual(skips, {"ValueError": 1, "insufficient_evidence": 1})
        for call in predict.call_args_list:
            self.assertIs(call.args[0], self.evidence)
            self.assertEqual(call.args[2], self.t)
            self.assertEqual(call.kwargs["n"], 5000)

    def test_expiration_before_and_after_calculation(self):
        events = [dict(x, start_utc=self.t + pd.Timedelta(minutes=20)) for x in self.events[:2]]
        now = Mock(side_effect=[self.t, self.t + pd.Timedelta(minutes=6),
                               self.t + pd.Timedelta(minutes=7)])
        predict = Mock(return_value={"status": "shadow_only"})
        result, skips = collect_v803(self.evidence, events, self.t,
            enabled=True, ready=True, predict=predict, now=now)
        self.assertEqual(result, [])
        self.assertEqual(skips, {"expired_after_compute": 1, "expired_before_compute": 1})
        predict.assert_called_once()


@unittest.skipUnless(os.environ.get("HOOPZARO_V8_TEST_POSTGRES") ==
    "postgresql://v8qa:v8qa@localhost:5432/v8qa", "Requires disposable local PostgreSQL")
class ArchiveTests(unittest.TestCase):
    def test_append_only_versions_and_database_cutoff(self):
        import psycopg
        from v8_shadow.storage import initialize, save_forecasts, settle_forecasts
        url = os.environ["HOOPZARO_V8_TEST_POSTGRES"]
        initialize(url)
        now = pd.Timestamp.now(tz="UTC")
        def fixture(model, start, game_id):
            return {"status": "shadow_only", "game_id": game_id,
                "model_id": model, "forecast_time_utc": (now-pd.Timedelta(hours=4)).isoformat(),
                "start_utc": start.isoformat(), "home": "T01", "away": "T02",
                "scenario_home": 109, "scenario_away": 102, "mean_home": 109.1,
                "mean_away": 102.3, "home_win_probability_pct": 65.0,
                "away_win_probability_pct": 35.0, "training_examples": 100}
        v02 = fixture("v8_possessions_shadow_v02", now+pd.Timedelta(hours=3), "401999991")
        v03 = dict(v02, model_id="v8_possessions_shadow_v03")
        expired = fixture("v8_possessions_shadow_v03", now+pd.Timedelta(minutes=5), "401999992")
        self.assertEqual(save_forecasts(url, [v02, v03, expired], "2026-27"), 2)
        self.assertEqual(save_forecasts(url, [dict(v03, mean_home=140)], "2026-27"), 0)
        self.assertEqual(settle_forecasts(url, [{"game_id": v03["game_id"], "status_code": 3,
            "home_score": 105, "away_score": 100}])["newly_settled"], 0)
        with psycopg.connect(url) as conn, conn.cursor() as cur:
            cur.execute("SELECT model_id, mean_home, actual_home FROM hoopzaro_v8_shadow_forecasts WHERE game_id=%s ORDER BY model_id", (v03["game_id"],))
            self.assertEqual(cur.fetchall(), [(v02["model_id"], 109.1, None), (v03["model_id"], 109.1, None)])
            cur.execute("SELECT count(*) FROM hoopzaro_v8_shadow_forecasts WHERE game_id=%s", (expired["game_id"],))
            self.assertEqual(cur.fetchone()[0], 0)


if __name__ == "__main__":
    unittest.main()
