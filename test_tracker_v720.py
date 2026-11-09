"""BestBets v7.20 autonomous Tracker: scheduled writes, settlement and data integrity."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from tracker_automation import (
    active_nba_season, upcoming_events, build_automatic_forecasts,
    run_cycle, run_scheduled_job,
)
from performance_tracker import (
    store_forecasts, settle_forecasts, read_forecasts,
)


def fixture(timestamp):
    now = pd.Timestamp(timestamp)
    start = now - pd.Timedelta(days=25)
    historical = pd.DataFrame([{
        "game_id":str(401001000 + i),
        "start_utc":start + pd.Timedelta(days=i),
        "home":"BOS" if i % 2 else "NYK",
        "away":"NYK" if i % 2 else "BOS",
        "home_score":109 + i % 11,
        "away_score":103 + i % 9,
        "status_code":3,
    } for i in range(20)])
    schedule = pd.DataFrame([{
        "game_id":"401999991",
        "start_utc":now + pd.Timedelta(hours=8),
        "home":"BOS","away":"NYK","status_code":1,
    }, {
        "game_id":"401999992",
        "start_utc":now + pd.Timedelta(hours=32),
        "home":"NYK","away":"BOS","status_code":1,
    }, {
        "game_id":"401999993",
        "start_utc":now + pd.Timedelta(hours=40),
        "home":"BOS","away":"NYK","status_code":1,
    }, {
        "game_id":"401999994",
        "start_utc":now - pd.Timedelta(hours=1),
        "home":"BOS","away":"NYK","status_code":3,
    }, {
        "game_id":"401999995",
        "start_utc":now + pd.Timedelta(minutes=5),
        "home":"BOS","away":"NYK","status_code":1,
    }])
    return historical, schedule


class AutomaticTrackerTests(unittest.TestCase):
    def setUp(self):
        self.now = pd.Timestamp("2026-11-10T08:00:00Z")
        self.history, self.schedule = fixture(self.now)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = Path(self.temp.name) / "test.sqlite3"

    def test_season_and_pregame_filter(self):
        self.assertEqual(active_nba_season("2026-11-10T08:00:00Z"),"2026-27")
        self.assertEqual(active_nba_season("2027-05-01T00:00:00Z"),"2026-27")
        future = upcoming_events(self.schedule,self.now)
        self.assertEqual(future["game_id"].tolist(),["401999991","401999992"])

    def test_autonomous_results_are_append_only_and_settled_once(self):
        # An existing and immutable real pregame prediction is already captured.
        past_game=self.history.iloc[-1]
        start=past_game["start_utc"]
        old={
            "game_id":str(past_game["game_id"]),
            "home":str(past_game["home"]),
            "away":str(past_game["away"]),
            "start_utc":start,
            "home_points":113.,"away_points":105.,
            "home_win_pct":62.,"away_win_pct":38.,
            "total_points":218.,"model_id":"legacy_v72",
            "source":"Prior user session",
        }
        result=store_forecasts(
            self.db,"2026-27",[old],
            captured_at=start-pd.Timedelta(hours=12))
        self.assertEqual(result["saved"],1)
        def writer(summaries,season):
            return store_forecasts(
                self.db,season,summaries,captured_at=self.now)
        def settler(completed):
            return settle_forecasts(self.db,completed,settled_at=self.now)
        first=run_cycle(self.schedule,self.history,self.now,writer,settler)
        self.assertEqual(first["matched_forecast_rows_settled"],1)
        self.assertEqual(first["upcoming_games_checked"],2)
        self.assertEqual(first["candidate_forecast_rows"],4)
        self.assertEqual(first["new_pregame_snapshots"],4)
        second=run_cycle(self.schedule,self.history,self.now,writer,settler)
        self.assertEqual(second["matched_forecast_rows_settled"],0)
        self.assertEqual(second["new_pregame_snapshots"],0)
        all_rows=read_forecasts(self.db)
        self.assertEqual(len(all_rows),5)
        existing=all_rows[all_rows["model_id"]=="legacy_v72"].iloc[0]
        self.assertEqual(existing["home_points"],113)
        self.assertEqual(existing["source"],"Prior user session")
        self.assertEqual(int(existing["home_score"]),int(past_game["home_score"]))
        self.assertEqual(
            set(all_rows["model_id"]),
            {"legacy_v72","auto_legacy_v72","auto_research_form_v74"})
        automatic=all_rows[all_rows["model_id"].str.startswith("auto_")]
        self.assertEqual(len(automatic),4)
        self.assertTrue(automatic["away_score"].isna().all())
        self.assertTrue((pd.to_datetime(automatic["forecast_time_utc"],utc=True)
                        < pd.to_datetime(automatic["start_utc"],utc=True)).all())

    def test_new_models_never_see_results_after_run_timestamp(self):
        chosen=upcoming_events(self.schedule,self.now)
        before,_=build_automatic_forecasts(chosen,self.history,self.now)
        invented=pd.DataFrame([{
            "game_id":"401888000","start_utc":self.now+pd.Timedelta(days=1),
            "home":"BOS","away":"NYK","home_score":190,"away_score":61,
            "status_code":3,
        }])
        after,_=build_automatic_forecasts(
            chosen,pd.concat([self.history,invented],ignore_index=True),self.now)
        self.assertEqual(before,after)

    def test_insufficient_history_never_creates_fake_forecast(self):
        short=self.history.head(2)
        c,_=build_automatic_forecasts(
            upcoming_events(self.schedule,self.now),short,self.now)
        self.assertEqual(c,[])

    def test_scheduled_worker_refuses_unconfigured_ephemeral_storage(self):
        with patch("tracker_storage.tracker_backend",
                   return_value={"remote":False,"url":"","label":"SQLite"}):
            with self.assertRaisesRegex(RuntimeError,"TRACKER_DATABASE_URL"):
                run_scheduled_job()


if __name__=="__main__":
    unittest.main()
