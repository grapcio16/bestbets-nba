"""Regression tests for verified playing minutes, opponent and position on TOP10."""
import unittest
from datetime import date
from zoneinfo import ZoneInfo

import pandas as pd

from espn_player_data import parse_summary
from dashboard_data import previous_day_ranking
from center_leaderboard import minute_text, player_card_html


def sample_game():
    return {
        "game_id":"401799999","away":"BOS","home":"NYK",
        "status_code":3,"start_utc":"2026-11-08T23:30:00Z",
    }


def sample_espn():
    return {"boxscore":{"players":[
        {"team":{"abbreviation":"NY"},"statistics":[{
            "labels":["MIN","FG","3PT","PTS","REB","AST"],
            "athletes":[{
                "athlete":{"id":"123","displayName":"Example Guard",
                           "position":{"abbreviation":"PG"}},
                "stats":["36:15","12-21","3-9","31","7","11"]},
                {"athlete":{"id":"456","displayName":"Example Wing"},
                 "stats":["29:00","8-16","2-6","24","5","3"]}
            ]}]}
    ]}}


class BoxscoreMetadata(unittest.TestCase):
    def test_espn_source_minutes_opponent_and_position(self):
        game=sample_game()
        rows=parse_summary(sample_espn(),game)
        self.assertEqual(len(rows),2)
        pg=next(r for r in rows if r["PLAYER_NAME"]=="Example Guard")
        self.assertEqual(pg["POSITION"],"PG")
        self.assertEqual(pg["OPPONENT"],"BOS")
        self.assertEqual(pg["MIN"],36.25)
        self.assertEqual(pg["MATCHUP"],"NYK vs. BOS")
        self.assertEqual(minute_text(pg["MIN"]),"36:15")
        self.assertEqual(next(r for r in rows if r["PLAYER_NAME"]=="Example Wing")["POSITION"],"")

    def test_ranking_preserves_real_boxscore_metadata(self):
        game=sample_game()
        matches=pd.DataFrame([game])
        def fake_fetch(g):
            return parse_summary(sample_espn(),g)
        top,coverage=previous_day_ranking(
            matches,date(2026,11,10),ZoneInfo("Europe/Warsaw"),fetch=fake_fetch)
        # 2026-11-08 23:30 UTC is Nov 9 00:30 in Warsaw: previous day of Nov 10.
        self.assertEqual(coverage["complete_games"],1)
        self.assertEqual(top["PLAYER_NAME"].tolist(),["Example Guard","Example Wing"])
        self.assertEqual(top.iloc[0]["MIN"],36.25)
        self.assertEqual(top.iloc[0]["OPPONENT"],"BOS")
        self.assertEqual(top.iloc[0]["POSITION"],"PG")
        card=player_card_html(top.iloc[0].to_dict(),1)
        for field in ["36:15","BOS","PG","MINUTY","PRZECIWNIK","POZYCJA"]:
            self.assertIn(field,card)

    def test_missing_position_not_guessed(self):
        rows=parse_summary(sample_espn(),sample_game())
        wing=next(r for r in rows if r["PLAYER_NAME"]=="Example Wing")
        card=player_card_html(wing,2)
        self.assertIn("29:00",card)
        self.assertIn("POZYCJA",card)
        self.assertIn(">—</strong>",card)

    def test_legacy_rows_keep_ranking_without_new_fields(self):
        game=sample_game()
        rows=[{"GAME_ID":"401799999","PLAYER_ID":"11","PLAYER_NAME":"Legacy",
               "TEAM_ABBREVIATION":"BOS","PTS":27,"REB":4,"AST":3}]
        top,_=previous_day_ranking(
            pd.DataFrame([game]),date(2026,11,10),ZoneInfo("Europe/Warsaw"),
            fetch=lambda g: rows)
        self.assertEqual(top.iloc[0]["OPPONENT"],"NYK")
        self.assertTrue(pd.isna(top.iloc[0]["MIN"]))
        self.assertIn(">—</strong>",player_card_html(top.iloc[0].to_dict(),1))

    def test_minutes_are_not_made_up(self):
        self.assertEqual(minute_text(None),"—")
        self.assertEqual(minute_text(float("nan")),"—")
        self.assertEqual(minute_text("bad"),"—")
        self.assertEqual(minute_text(-1),"—")
        self.assertEqual(minute_text(21),"21:00")
        self.assertEqual(minute_text(42.5),"42:30")


if __name__=="__main__":
    unittest.main()
