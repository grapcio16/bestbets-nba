"""Offline regression suite for confirmed NBA scores and recent player leaders."""
from unittest import TestCase, mock
import pandas as pd
from bestbets_centre_live import extract_recent_leaders, get_centre_live_data, get_centre_day_data

NOW=pd.Timestamp("2026-11-12 21:00:00",tz="Europe/Warsaw")
RAW={"events":[
 {"id":"g1","date":"2026-11-11T23:00:00Z",
  "status":{"type":{"completed":True}},
  "competitions":[{"status":{"type":{"completed":True}},"competitors":[
    {"homeAway":"home","team":{"abbreviation":"BOS","displayName":"Boston Celtics"},
     "score":"112","leaders":[
       {"name":"points","leaders":[{"value":26,"athlete":{"id":"10","displayName":"Jayson Tatum"}}]},
       {"name":"rebounds","leaders":[{"value":10,"athlete":{"id":"11","displayName":"Al Horford"}}]}
     ]},
    {"homeAway":"away","team":{"abbreviation":"NYK","displayName":"New York Knicks"},
     "score":"110","leaders":[
       {"name":"assists","leaders":[{"value":8,"athlete":{"id":"13","displayName":"Jalen Brunson"}}]}
     ]}
   ]}]},
 {"id":"g2","date":"2026-11-12T22:00:00Z",
  "status":{"type":{"completed":False}},
  "competitions":[{"status":{"type":{"state":"pre"}},"competitors":[
    {"homeAway":"home","team":{"abbreviation":"PHI","displayName":"Philadelphia 76ers"},"score":None},
    {"homeAway":"away","team":{"abbreviation":"BOS","displayName":"Boston Celtics"},"score":None}
  ]}]}
]}


class CentreLiveTest(TestCase):
    def test_verified_leaders_from_final_only(self):
        rows=extract_recent_leaders(RAW,NOW,limit=3)
        self.assertEqual(len(rows),3)
        self.assertEqual(rows[0]["name"],"Jayson Tatum")
        self.assertEqual(rows[0]["value"],26)
        self.assertEqual(rows[1]["name"],"Al Horford")
        self.assertEqual(rows[2]["market"],"AST")

    def test_optional_position_comes_from_reported_athlete_only(self):
        import copy
        source=copy.deepcopy(RAW)
        player=source['events'][0]['competitions'][0]['competitors'][0]['leaders'][0]['leaders'][0]['athlete']
        player['position']={'abbreviation':'SF'}
        rows=extract_recent_leaders(source,NOW,limit=3)
        self.assertEqual(rows[0]['position'],'SF')
        self.assertEqual(rows[1]['position'],'')

    def test_schedule_and_final_score_are_actual_and_consistent(self):
        with mock.patch("sources.memoized_json",return_value=(RAW,{"timestamp":"2026-11-12T19:00:00Z","stale":False})) as fetch,\
             mock.patch("team_logos.logo_data_uri",return_value=""):
            snapshot=get_centre_live_data(NOW)
        # Critical regression: ESPN's range query returned an error in CI
        # while date=YYYYMMDD succeeded. Every request must use ONE day.
        import re
        days=[c.kwargs["params"]["dates"] for c in fetch.call_args_list if "dates" in c.kwargs.get("params", {})]
        self.assertGreaterEqual(len(days),8)
        self.assertTrue(all(re.fullmatch(r"\d{8}",d) for d in days),days)
        self.assertEqual(snapshot["source"],"ESPN — rzeczywiste mecze NBA")
        self.assertEqual(len(snapshot["players"]),3)
        self.assertEqual(snapshot["finals"][0]["away_score"],110)
        self.assertEqual(snapshot["finals"][0]["home_score"],112)
        self.assertIsNone(snapshot["games"][-1]["away_score"])
        self.assertEqual(snapshot["ticker"][0]["away"],"BOS")
        self.assertEqual(snapshot["games"][-1]["state"],"scheduled")
        self.assertFalse(snapshot["stale"])

    def test_daily_navigation_requests_two_single_espn_dates(self):
        # Warsaw night-time games can belong to the prior ESPN date.
        with mock.patch("sources.memoized_json",return_value=(RAW,{"stale":False})) as fetch,\
             mock.patch("team_logos.logo_data_uri",return_value=""):
            out=get_centre_day_data("2026-11-12")
        self.assertEqual(out["date"],"2026-11-12")
        self.assertTrue(any(g["state"]=="final" and g["away_score"]==110
                            for g in out["games"]))
        self.assertTrue(any(g["state"]=="scheduled" for g in out["games"]))
        self.assertEqual(len(fetch.call_args_list),2)
        self.assertEqual({c.kwargs["params"]["dates"] for c in fetch.call_args_list},
                         {"20261111","20261112"})

    def test_day_navigation_rejects_unbounded_dates(self):
        with self.assertRaises(ValueError):
            get_centre_day_data("2099-01-01")

    def test_failure_honestly_reports_no_data(self):
        with mock.patch("sources.memoized_json",side_effect=TimeoutError("mock blocked ESPN")),\
             mock.patch("sources.schedule",side_effect=TimeoutError("mock blocked NBA")):
            snapshot=get_centre_live_data(NOW)
        self.assertEqual(snapshot["games"],[])
        self.assertEqual(snapshot["players"],[])
        self.assertTrue(snapshot["stale"])
        self.assertIn("Nie udało się",snapshot["error"])

    def test_tampered_input_never_creates_fake_player_stats(self):
        raw={"events":[{"date":"2026-11-12T20:00:00Z",
              "status":{"type":{"completed":False}},
              "competitions":[{"competitors":[{"team":{"abbreviation":"BOS"},
              "leaders":[{"name":"points","leaders":[{"value":"10000",
                    "athlete":{"displayName":"Fake"}}]}]}]}]}]}
        self.assertEqual(extract_recent_leaders(raw,NOW),[])


if __name__=="__main__":
    import unittest
    unittest.main()
