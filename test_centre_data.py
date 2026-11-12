"""Unit tests for truthful, timezone-aware free Centrum fixtures."""
import unittest
import pandas as pd

from bestbets_centre_data import build_centre_snapshot


class CentreSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.now=pd.Timestamp("2026-11-12 19:00:00",tz="Europe/Warsaw")
        self.table=pd.DataFrame([
            {"game_id":"1","start_utc":"2026-11-12T18:00:00Z",
             "away":"BOS","home":"PHI","status_code":2,"status":"Q2 04:00",
             "away_score":64,"home_score":61},
            {"game_id":"2","start_utc":"2026-11-12T21:00:00Z",
             "away":"NYK","home":"MIL","status_code":1,"status":"Scheduled",
             "away_score":None,"home_score":None},
            {"game_id":"3","start_utc":"2026-11-11T18:00:00Z",
             "away":"LAL","home":"DEN","status_code":3,"status":"Final",
             "away_score":92,"home_score":105},
        ])
    def test_home_content_real_and_local_day(self):
        d=build_centre_snapshot(self.table,{"source":"ESPN"},self.now,logo_provider=lambda _: "")
        self.assertEqual(d["day_label"],"Dziś")
        self.assertEqual([g["id"] for g in d["games"]],["1","2"])
        self.assertEqual([g["state"] for g in d["ticker"]],["live","scheduled"])
        self.assertEqual(d["games"][0]["away_score"],64)
        self.assertEqual(d["games"][1]["away_score"],None)
        self.assertEqual(d["finals"][0]["id"],"3")
        self.assertEqual(d["form"][0]["sample"],1)
        self.assertNotIn("prediction",str(d).lower())
        self.assertNotIn("71.3%",str(d))
    def test_next_real_date_not_falsely_today(self):
        d=build_centre_snapshot(self.table,{"source":"ESPN"},
            pd.Timestamp("2026-11-12 23:00:00",tz="Europe/Warsaw"))
        self.assertTrue(d["day_label"].startswith("Najbliższe:"))
        self.assertEqual(d["games"][0]["id"],"2")
    def test_failure_no_fake_games(self):
        d=build_centre_snapshot(pd.DataFrame(),{"source":"ESPN"},self.now)
        self.assertEqual(d["games"],[])
        self.assertEqual(d["ticker"],[])
        self.assertNotEqual(d["error"],"")
    def test_scores_and_invalid_fields(self):
        table=self.table.copy()
        table.loc[0,"away_score"]="not-a-number"
        table.loc[0,"away"]="INVALID TEAM"
        d=build_centre_snapshot(table,{},self.now)
        self.assertEqual(d["games"][0]["away_score"],None)
        self.assertEqual(d["games"][0]["away"],"NBA")
    def test_stale_source_flagged(self):
        d=build_centre_snapshot(self.table,{"stale":True},self.now)
        self.assertIn("nieaktualny",d["error"])


if __name__=="__main__":
    unittest.main()
