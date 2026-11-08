"""v7.8 regression: store and settle both frozen models for one NBA game."""
import tempfile
import unittest
from pathlib import Path
import pandas as pd
from performance_tracker import store_forecasts,read_forecasts,settle_forecasts,performance_metrics


class MultiModelTrackerTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db=Path(self.tmp.name)/"tracker.db"
        self.game={
            "game_id":"401999997","home":"NYK","away":"CLE",
            "start_utc":"2026-11-08T02:00:00Z",
            "home_points":112.0,"away_points":116.0,
            "home_win_pct":41.0,"away_win_pct":59.0,
            "total_points":228.0,"source":"legacy",
            "model_id":"legacy_v72"
        }

    def test_two_models_independent_same_match(self):
        old=dict(self.game)
        research=dict(self.game,model_id="research_form_v74",
                      home_win_pct=46.0,away_win_pct=54.0,
                      home_points=115.0,away_points=113.0,
                      total_points=228.0,source="research")
        tm="2026-11-07T21:00:00Z"
        r1=store_forecasts(self.db,"2026-27",[old],captured_at=tm)
        r2=store_forecasts(self.db,"2026-27",[research],captured_at=tm)
        self.assertEqual(r1["saved"],1)
        self.assertEqual(r2["saved"],1)
        frozen=read_forecasts(self.db)
        self.assertEqual(len(frozen),2)
        self.assertEqual(set(frozen["model_id"]),
                         {"legacy_v72","research_form_v74"})
        self.assertEqual(set(frozen["home_points"]),{112.0,115.0})
        # Rerunning either model must NOT rewrite it.
        changed=dict(research,home_points=123.,away_points=105.)
        retry=store_forecasts(self.db,"2026-27",[changed],captured_at=tm)
        self.assertEqual(retry["saved"],0)
        self.assertEqual(set(read_forecasts(self.db)["home_points"]),{112.0,115.0})

    def test_settle_same_match_both_models_and_filter_brier(self):
        old=dict(self.game)
        research=dict(self.game,model_id="research_form_v74",
                      home_win_pct=65.0,away_win_pct=35.0,
                      home_points=120.,away_points=108.)
        for sample in (old,research):
            ret=store_forecasts(self.db,"2026-27",[sample],
                captured_at="2026-11-07T21:00:00Z")
            self.assertEqual(ret["saved"],1)
        completed=pd.DataFrame([{"game_id":"401999997",
            "status_code":3,"away_score":97,"home_score":109}])
        n=settle_forecasts(self.db,completed,
                          settled_at="2026-11-08T07:00:00Z")
        self.assertEqual(n,2)
        self.assertEqual(set(read_forecasts(self.db)["home_score"]),{109})
        df=read_forecasts(self.db)
        for code in ("legacy_v72","research_form_v74"):
            _,stats=performance_metrics(df[df.model_id==code])
            self.assertEqual(stats["games"],1)
        # No duplicate settlements.
        self.assertEqual(settle_forecasts(self.db,completed,
            settled_at="2026-11-08T07:30:00Z"),0)

    def test_missing_future_result_does_not_settle(self):
        ret=store_forecasts(self.db,"2026-27",[self.game],
            captured_at="2026-11-07T21:00:00Z")
        self.assertEqual(ret["saved"],1)
        outcome=pd.DataFrame([{"game_id":"401999997",
            "status_code":1,"away_score":0,"home_score":0}])
        self.assertEqual(settle_forecasts(self.db,outcome,
            settled_at="2026-11-08T07:00:00Z"),0)

if __name__=="__main__":
    unittest.main()
