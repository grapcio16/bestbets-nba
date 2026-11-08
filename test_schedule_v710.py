"""Regressions for the fixture cards and calendar introduced in v7.10."""
import unittest
from datetime import date
from zoneinfo import ZoneInfo

import pandas as pd

from schedule_data import fixtures_for_day, missing_archive_months, required_utc_months
from schedule_ui import result_type, real_score, card_html


class ScheduleCardsTest(unittest.TestCase):
    def setUp(self):
        self.zone=ZoneInfo("Europe/Warsaw")
        self.basic={
            "game_id":"2026game","start_utc":"2026-11-09T00:30:00Z",
            "away":"BKN","away_name":"Brooklyn Nets",
            "home":"ATL","home_name":"Atlanta Hawks",
            "status":"Final","status_code":3,"away_score":112,"home_score":119,
            # Values from other modules must NEVER leak into fixture cards.
            "simulated_score":"99 : 101","predicted_winner":"BKN",
            "total_points_forecast":220,
        }

    def test_final_actual_score_and_no_predictions(self):
        html=card_html(self.basic,self.zone)
        self.assertIn("112 : 119",html)
        self.assertIn("WYNIK KOŃCOWY",html)
        self.assertIn("Brooklyn Nets",html)
        self.assertIn("Atlanta Hawks",html)
        for forbidden in ("99 : 101","predicted_winner","total_points_forecast",
                          "symulacji","Symulacja","prognoza","przewidywany"):
            self.assertNotIn(forbidden,html)

    def test_future_game_shows_only_real_start_time(self):
        future=dict(self.basic,status_code=1,status="Scheduled",
                    away_score=0,home_score=0)
        html=card_html(future,self.zone)
        self.assertIn("01:30",html)
        self.assertIn("Zaplanowany",html)
        self.assertNotIn("0 : 0",html)
        self.assertIsNone(real_score(future))
        self.assertEqual(result_type(future),"scheduled")

    def test_live_actual_score(self):
        live=dict(self.basic,status_code=2,status="In Progress",
                  away_score=68,home_score=64)
        html=card_html(live,self.zone)
        self.assertIn("68 : 64",html)
        self.assertIn("WYNIK NA ŻYWO",html)
        self.assertNotIn("WYNIK KOŃCOWY",html)

    def test_missing_score_not_invented(self):
        missing=dict(self.basic,status_code=3,away_score=None,home_score=None)
        html=card_html(missing,self.zone)
        self.assertIn("01:30",html)
        self.assertNotIn("WYNIK KOŃCOWY",html)

    def test_unsafe_external_team_name_escaped(self):
        unsafe=dict(self.basic,away_name='<img src=x onerror=alert(1)>')
        html=card_html(unsafe,self.zone)
        self.assertNotIn('<img src=x onerror=',html)
        self.assertIn('&lt;img src=x',html)


class DateArchiveTest(unittest.TestCase):
    def test_date_browse_previous_month(self):
        self.assertEqual(
            missing_archive_months(date(2026,10,26),ZoneInfo("Europe/Warsaw"),
                current_utc="2026-11-08T15:00:00Z"),
            ["202610"],
        )
        calls=[]
        def mocked_fetch(month, nonce):
            calls.append((month,nonce))
            return pd.DataFrame([{
                "game_id":"oct","start_utc":"2026-10-25T23:30:00Z",
                "away":"BOS","home":"NYK","status_code":3,
            }]), {"stale":False}
        rows, issues=fixtures_for_day(
            pd.DataFrame(),date(2026,10,26),ZoneInfo("Europe/Warsaw"),
            nonce=4,fetcher=mocked_fetch,now_utc="2026-11-08T15:00:00Z")
        self.assertEqual(rows["game_id"].tolist(),["oct"])
        self.assertEqual(calls,[("202610",4)])
        self.assertFalse(issues)

    def test_future_month_and_local_day_in_pacific(self):
        months=required_utc_months(date(2027,1,1),ZoneInfo("America/Los_Angeles"))
        self.assertEqual(months,["202701"])
        self.assertEqual(missing_archive_months(
            date(2027,1,1),ZoneInfo("America/Los_Angeles"),
            current_utc="2026-11-08T20:00:00Z"),["202701"])

    def test_dst_boundary_with_archive(self):
        self.assertEqual(required_utc_months(
            date(2026,11,1),ZoneInfo("America/Los_Angeles")),["202611"])


if __name__=="__main__":
    unittest.main()
