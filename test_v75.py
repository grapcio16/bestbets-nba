"""Regression checks for v7.5 persistence and NBA schedule diagnostics."""
from pathlib import Path
import os
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
import pandas as pd

from match_context import team_schedule_context,matchup_schedule_context
from tracker_storage import tracker_backend,save,read
from performance_tracker import store_forecasts


class ScheduleContextTests(unittest.TestCase):
    def setUp(self):
        games=[]
        for day in (1,3,4,6):
            games.append({
                "game_id":str(401000300+day),
                "start_utc":pd.Timestamp(f"2026-11-{day:02d}T23:00:00Z"),
                "home":"SAS" if day%2 else "POR",
                "away":"POR" if day%2 else "SAS",
                "home_score":110+day,"away_score":105+day,
                "status_code":3
            })
        self.history=pd.DataFrame(games)

    def test_back_to_back_and_days_off(self):
        result=team_schedule_context(
            self.history,"SAS","2026-11-07T23:00:00Z")
        self.assertTrue(result["available"])
        self.assertEqual(result["rest_days"],0)
        self.assertTrue(result["back_to_back"])
        self.assertEqual(result["games_in_4_days"],3)

    def test_ignores_future_and_in_progress(self):
        history=pd.concat([self.history,pd.DataFrame([
            {"start_utc":pd.Timestamp("2026-11-10T23:00:00Z"),
             "home":"SAS","away":"POR","home_score":200,
             "away_score":60,"status_code":3},
            {"start_utc":pd.Timestamp("2026-11-07T15:00:00Z"),
             "home":"SAS","away":"POR","home_score":200,
             "away_score":60,"status_code":2}
        ])],ignore_index=True)
        x=team_schedule_context(
            history,"SAS","2026-11-07T23:00:00Z")
        self.assertEqual(x["last_game"],"2026-11-06")
        self.assertTrue(x["back_to_back"])

    def test_context_for_both_sides(self):
        game={"home":"SAS","away":"POR",
              "start_utc":"2026-11-07T23:00:00Z"}
        result=matchup_schedule_context(self.history,game)
        self.assertTrue(result["away"]["available"])
        self.assertTrue(result["home"]["available"])


class DurableTrackerTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db=Path(self.tmp.name)/"archive.sqlite3"
        self.sample={
            "game_id":"401999999","home":"SAS","away":"POR",
            "start_utc":"2026-11-08T03:00:00Z",
            "home_points":116.1,"away_points":114.2,
            "home_win_pct":55.4,"away_win_pct":44.6,
            "total_points":230.3,"source":"ESPN",
            "model_id":"research_form_v74"
        }

    def test_old_sqlite_schema_migrates_without_deleting_predictions(self):
        with sqlite3.connect(self.db) as connection:
            connection.executescript("""
                CREATE TABLE forecasts (
                    game_id TEXT PRIMARY KEY,
                    season TEXT NOT NULL,
                    forecast_time_utc TEXT NOT NULL,
                    start_utc TEXT NOT NULL,
                    away TEXT NOT NULL,home TEXT NOT NULL,
                    away_points REAL NOT NULL,home_points REAL NOT NULL,
                    away_win_pct REAL NOT NULL,home_win_pct REAL NOT NULL,
                    total_points REAL NOT NULL,
                    source TEXT NOT NULL,warning TEXT NOT NULL DEFAULT '',
                    away_score INTEGER,home_score INTEGER,
                    settled_at_utc TEXT
                );
            """)
            connection.execute(
                """INSERT INTO forecasts
                (game_id,season,forecast_time_utc,start_utc,away,home,
                away_points,home_points,away_win_pct,home_win_pct,
                total_points,source,warning)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                ("401999888","2026-27","2026-11-06T20:00:00+00:00",
                 "2026-11-07T03:00:00+00:00","POR","SAS",
                 114.0,116.0,48.0,52.0,230.0,"ESPN",""))
            connection.commit()
        from performance_tracker import read_forecasts
        frame=read_forecasts(self.db)
        self.assertEqual(len(frame),1)
        self.assertEqual(frame.iloc[0]["model_id"],"legacy_v72")
        stored=store_forecasts(self.db,"2026-27",[self.sample],
                               captured_at="2026-11-07T12:00:00Z")
        self.assertEqual(stored["saved"],1)
        newer=read_forecasts(self.db)
        self.assertEqual(len(newer),2)
        entry=newer[newer["game_id"]=="401999999"].iloc[0]
        self.assertEqual(entry["model_id"],"research_form_v74")

    def test_routes_to_local_if_remote_not_configured(self):
        with patch.dict(os.environ,{"TRACKER_DATABASE_URL":""}):
            with patch("tracker_storage.tracker_database_url",return_value=""):
                config=tracker_backend()
        self.assertFalse(config["remote"])
        self.assertNotIn("postgresql://",config["label"])

    def test_config_never_reveals_secret(self):
        secret="postgresql://u:sensitive-password@example.net/db"
        with patch("tracker_storage.tracker_database_url",return_value=secret):
            config=tracker_backend()
        self.assertTrue(config["remote"])
        self.assertNotIn("sensitive-password",config["label"])

    def test_remote_validation_does_not_echo_connection_string(self):
        from tracker_postgres import connect
        with self.assertRaises(ValueError) as ctx:
            connect("not-a-database")
        self.assertNotIn("not-a-database",str(ctx.exception))


if __name__=="__main__":
    unittest.main()
