"""Regression tests: no fabricated snapshots, no hindsight, valid settlements and recency."""
import tempfile
import unittest
from pathlib import Path
import pandas as pd

from performance_tracker import (
    store_forecasts,settle_forecasts,read_forecasts,performance_metrics)
from simulation_engine import completed_team_scores,matchup_means
from simulation_backtest import walk_forward_comparison


class TrackerTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db=Path(self.temp.name)/"games.sqlite3"
        self.pred={
            "game_id":"401999910", "home":"SAS","away":"POR",
            "start_utc":"2026-11-08T03:00:00Z",
            "home_points":116.1,"away_points":114.2,
            "home_win_pct":55.4,"away_win_pct":44.6,
            "total_points":230.3,"source":"ESPN"
        }

    def test_cannot_overwrite_or_capture_after_tipoff(self):
        ts="2026-11-07T12:00:00Z"
        first=store_forecasts(self.db,"2026-27",[self.pred],captured_at=ts)
        self.assertEqual(first["saved"],1)
        changed=dict(self.pred,home_points=150.,total_points=264.2)
        second=store_forecasts(self.db,"2026-27",[changed],captured_at=ts)
        self.assertEqual(second["saved"],0)
        self.assertEqual(read_forecasts(self.db).iloc[0]["home_points"],116.1)
        late=dict(self.pred,game_id="401999911")
        outcome=store_forecasts(self.db,"2026-27",[late],
                                captured_at="2026-11-08T04:00:00Z")
        self.assertEqual(outcome["saved"],0)

    def test_settle_only_completed_after_start(self):
        store_forecasts(self.db,"2026-27",[self.pred],
                        captured_at="2026-11-07T12:00:00Z")
        base={"game_id":"401999910","away_score":105,"home_score":119}
        pending=pd.DataFrame([dict(base,status_code=1)])
        self.assertEqual(settle_forecasts(self.db,pending,
            settled_at="2026-11-08T05:30:00Z"),0)
        final=pd.DataFrame([dict(base,status_code=3)])
        self.assertEqual(settle_forecasts(self.db,final,
            settled_at="2026-11-08T05:30:00Z"),1)
        self.assertEqual(settle_forecasts(self.db,final,
            settled_at="2026-11-08T05:31:00Z"),0)
        df=read_forecasts(self.db)
        self.assertEqual(int(df.iloc[0]["home_score"]),119)
        rows,metrics=performance_metrics(df)
        self.assertEqual(metrics["games"],1)
        self.assertEqual(metrics["winner_accuracy"],1.0)

    def test_missing_history_metrics(self):
        rows,metrics=performance_metrics(read_forecasts(self.db))
        self.assertEqual(metrics["games"],0)

    def test_bad_forecast_rejected(self):
        bad=dict(self.pred,home_win_pct=75.,away_win_pct=44.6)
        out=store_forecasts(self.db,"2026-27",[bad],
                            captured_at="2026-11-07T12:00:00Z")
        self.assertEqual(out["saved"],0)


class SimulationFormTests(unittest.TestCase):
    def test_complete_games_keep_opponent_and_team_orientation(self):
        df=pd.DataFrame([{
            "game_id":"401000001","home":"SAS","away":"POR",
            "start_utc":pd.Timestamp("2026-11-03",tz="UTC"),
            "home_score":120,"away_score":101,"status_code":3
        }])
        t=completed_team_scores(df)
        self.assertEqual(t["SAS"][0][1:],(120,101,"POR"))
        self.assertEqual(t["POR"][0][1:],(101,120,"SAS"))

    def test_recent_form_matters_without_future_data(self):
        records={k:[] for k in ("SAS","POR")}
        for i in range(8):
            date=pd.Timestamp("2026-10-20",tz="UTC")+pd.Timedelta(days=i)
            records["SAS"].append((date,100+i*3,105-i,"POR"))
            records["POR"].append((date,110-i,112+i,"SAS"))
        mean=matchup_means("POR","SAS",{},records)
        self.assertIsNotNone(mean)
        self.assertIn("form",mean)
        self.assertLess(mean["home"],mean["away"])

    def test_walk_forward_never_fits_the_same_game(self):
        games=[]
        for i in range(12):
            date=pd.Timestamp("2026-10-20",tz="UTC")+pd.Timedelta(days=i)
            games.append({"game_id":str(401000000+i),
                          "home":"SAS" if i%2 else "POR",
                          "away":"POR" if i%2 else "SAS",
                          "start_utc":date,"home_score":110+i,
                          "away_score":100+i,"status_code":3})
        rows,metrics=walk_forward_comparison(pd.DataFrame(games))
        self.assertGreater(len(rows),0)
        self.assertEqual(metrics["games"],len(rows))
        self.assertTrue((rows["date"]>pd.Timestamp("2026-10-23",tz="UTC")).all())


if __name__=="__main__":
    unittest.main()
