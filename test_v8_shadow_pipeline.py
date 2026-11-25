"""V8 Shadow readiness and monitoring regression tests."""
import unittest
import os
from unittest.mock import patch
import pandas as pd
from test_v8_shadow_engine import history
from v8_shadow.readiness import audit_evidence
from v8_shadow.data import categorize_rejection
from v8_shadow.monitored_worker import run_monitored

class V8ReadinessTests(unittest.TestCase):
    def test_insufficient_training_history(self):
        h=history()[:85]
        r=audit_evidence(h,pd.Timestamp(h[-1]["start_utc"])+pd.Timedelta(hours=2))
        self.assertEqual(r["minimum_examples"],56)
        self.assertFalse(r["ready_for_eligible_matchups"])
    def test_sufficient_synthetic_history(self):
        h=history()
        r=audit_evidence(h,pd.Timestamp(h[-1]["start_utc"])+pd.Timedelta(hours=2))
        self.assertTrue(r["ready_for_eligible_matchups"],r)
        self.assertGreaterEqual(r["effective_training_examples"],40)
    def test_future_scores_excluded(self):
        h=history()
        t=pd.Timestamp(h[170]["start_utc"])-pd.Timedelta(seconds=1)
        self.assertEqual(audit_evidence(h,t)["observed_final_games"],170)
    def test_rejection_classification(self):
        self.assertEqual(categorize_rejection(ValueError("overtime not normalized")),"overtime_unmodeled")
        self.assertEqual(categorize_rejection(ValueError("required count absent")),"required_box_stats_missing")
        self.assertEqual(categorize_rejection(ValueError("final score mismatch")),"score_mismatch")
    def test_monitored_worker_only_calls_shadow_writer(self):
        report={"season":"2026-27","boxscore_ingest":{"rejected":3},
            "upcoming_games_checked":5,"shadow_forecasts_calculated":1,
            "new_shadow_forecasts":1,"new_boxscore_games":27}
        readiness={"observed_final_games":120,
            "trainable_chronological_examples":60,
            "minimum_examples":56,"readiness_reason":"training_evidence_sufficient"}
        with patch.dict(os.environ,{"TRACKER_DATABASE_URL":"mock://unused"}),\
            patch("v8_shadow.monitored_worker.run",return_value=report),\
            patch("v8_shadow.monitored_worker.read_boxes",return_value=[]),\
            patch("v8_shadow.monitored_worker.audit_evidence",return_value=readiness),\
            patch("v8_shadow.monitored_worker.record_worker_run") as writer:
            result=run_monitored()
        self.assertEqual(result["readiness"],readiness)
        self.assertEqual(writer.call_args.kwargs["boxes_added"],27)
if __name__=="__main__": unittest.main()
