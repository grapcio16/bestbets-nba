"""Pregame data-depth and optional venue research checks (no network)."""
from datetime import datetime, timedelta, timezone
import unittest

import pandas as pd

from simulation_data_audit import (
    verified_history, team_snapshot, matchup_audit, venue_research_candidate,
)


def sample_matches(count=26):
    base=pd.Timestamp("2026-10-10T23:00:00Z")
    data=[]
    for i in range(count):
        bos_home=i%2==0
        data.append({
            "game_id":str(10000+i),
            "start_utc":base+pd.Timedelta(days=i),
            "home":"BOS" if bos_home else "NYK",
            "away":"NYK" if bos_home else "BOS",
            "home_score":110+(i%9),
            "away_score":106+(i%7),
            "status_code":3,
        })
    return pd.DataFrame(data)


class ExtraDataCoverage(unittest.TestCase):
    def setUp(self):
        self.matches=sample_matches(26)
        self.game={
            "game_id":"future", "start_utc":"2026-11-09T23:30:00Z",
            "home":"BOS", "away":"NYK", "status_code":1,
        }

    def test_only_verified_pregame_results(self):
        df=self.matches.copy()
        df=pd.concat([df,pd.DataFrame([{
            "game_id":"future","start_utc":"2026-11-10T01:00:00Z",
            "home":"BOS","away":"NYK","home_score":199,"away_score":100,"status_code":3
        }, {
            "game_id":"invalid","start_utc":"2026-11-02T01:00:00Z",
            "home":"BOS","away":"NYK","home_score":0,"away_score":100,"status_code":3
        }])],ignore_index=True)
        filtered=verified_history(df,self.game["start_utc"])
        self.assertEqual(len(filtered),26)
        self.assertNotIn("future",set(filtered["game_id"]))
        self.assertNotIn("invalid",set(filtered["game_id"]))

    def test_sample_profiles_5_10_20_and_venue(self):
        df=verified_history(self.matches,self.game["start_utc"])
        prof=team_snapshot(df,"BOS",opponent="NYK",venue="home")
        self.assertEqual((prof["n5"],prof["n10"],prof["n20"]),(5,10,20))
        self.assertEqual(prof["venue_sample"],10)
        self.assertEqual(prof["h2h_sample"],20)
        self.assertIsNotNone(prof["pts10"])
        self.assertIsNotNone(prof["total_sd10"])

    def test_advanced_only_with_real_columns(self):
        adv=pd.DataFrame([
          {"TEAM_ABBREVIATION":"BOS","PACE":100.5,"OFF_RATING":116.3,"DEF_RATING":109.7},
          {"TEAM_ABBREVIATION":"NYK","PACE":98.1,"OFF_RATING":110.9,"DEF_RATING":113.5},
        ])
        report,flags=matchup_audit(self.matches,self.game,adv)
        self.assertEqual(len(report),2)
        b=report[report["Drużyna"]=="BOS"].iloc[0]
        self.assertEqual(b["Historia 20"],"20/20")
        self.assertEqual(b["Pace oficjalne"],100.5)
        empty,missing=matchup_audit(self.matches,self.game,pd.DataFrame())
        self.assertTrue(all(pd.isna(x) for x in empty["Pace oficjalne"]))
        self.assertTrue(any("Brak aktualnych NBA Advanced" in x for x in missing))

    def test_candidate_is_research_and_future_safe(self):
        before=venue_research_candidate(self.matches,self.game)
        self.assertIsNotNone(before)
        self.assertIn("BADAWCZY",before["source"])
        self.assertGreaterEqual(before["venue_samples"][0],4)
        invalid_future=pd.DataFrame([{
            "game_id":"too_late",
            "start_utc":"2026-11-10T00:00:00Z",
            "home":"BOS","away":"NYK","home_score":196,"away_score":55,"status_code":3
        }])
        combined=pd.concat([self.matches,invalid_future],ignore_index=True)
        after=venue_research_candidate(combined,self.game)
        self.assertEqual(before["home"],after["home"])
        self.assertEqual(before["away"],after["away"])

    def test_insufficient_data_blocks_candidate(self):
        only_three=sample_matches(3)
        candidate=venue_research_candidate(only_three,self.game)
        self.assertIsNone(candidate)
        report,flags=matchup_audit(only_three,self.game,None)
        self.assertEqual(report["Historia 10"].tolist(),["3/10","3/10"])
        self.assertTrue(any("za mało" in x for x in flags))


if __name__=="__main__":
    unittest.main()
