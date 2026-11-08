"""TOP10 v7.13: verified player metadata, cache refresh and compact layout."""
import unittest
from datetime import date
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

from dashboard_data import previous_day_ranking, fill_missing_positions
from center_leaderboard import player_card_html


class RankingMetadataTests(unittest.TestCase):
    def setUp(self):
        self.game={
            "game_id":"401799999","away":"BOS","home":"NYK",
            "status_code":3,"start_utc":"2026-11-08T23:30:00Z",
        }

    def test_live_boxscore_metadata_laid_out_in_one_stat_row(self):
        rows=[{
            "GAME_ID":"401799999","PLAYER_ID":"10",
            "PLAYER_NAME":"Example Player","TEAM_ABBREVIATION":"NYK",
            "PTS":35,"REB":7,"AST":8,"MIN":38.5,"POSITION":"PG",
            "OPPONENT":"BOS",
        }]
        top,_=previous_day_ranking(pd.DataFrame([self.game]),
            date(2026,11,10),ZoneInfo("Europe/Warsaw"),fetch=lambda _:rows)
        self.assertEqual(top.iloc[0]["MATCHUP"],"BOS @ NYK")
        markup=player_card_html(top.iloc[0].to_dict(),1)
        self.assertIn("BOS @ NYK",markup)
        self.assertIn("38:30",markup)
        self.assertIn(">PG</strong>",markup)
        self.assertIn('class="bb-top10-stats"',markup)
        self.assertNotIn("bb-top10-extra-item",markup)
        self.assertIn("MECZ",markup)
        self.assertTrue(markup.index("bb-top10-position") < markup.index("bb-top10-match"))
        self.assertTrue(markup.index("ASYSTY") < markup.index("38:30") < markup.index("MINUTY"))

    def test_roster_fallback_uses_matching_id_and_team_only(self):
        top=pd.DataFrame([{
            "GAME_ID":"401799999","PLAYER_ID":"10",
            "PLAYER_NAME":"Example Player","TEAM_ABBREVIATION":"NYK",
            "PTS":35,"REB":7,"AST":8,"MIN":38.5,"POSITION":"",
            "OPPONENT":"BOS","MATCHUP":"BOS @ NYK",
        }])
        calls=[]
        def roster(team):
            calls.append(team)
            return pd.DataFrame([
                {"PLAYER_ID":"10","POSITION":"SG"},
                {"PLAYER_ID":"11","POSITION":"C"},
            ]),{"stale":False}
        filled=fill_missing_positions(top,roster_fetcher=roster)
        self.assertEqual(calls,["NYK"])
        self.assertEqual(filled.iloc[0]["POSITION"],"SG")
        self.assertEqual(top.iloc[0]["POSITION"],"")

    def test_roster_does_not_guess_when_id_missing_or_source_stale(self):
        top=pd.DataFrame([{
            "GAME_ID":"401799999","PLAYER_ID":"999",
            "PLAYER_NAME":"Example Player","TEAM_ABBREVIATION":"NYK",
            "POSITION": "",
        }])
        def stale(team):
            return pd.DataFrame([{"PLAYER_ID":"999","POSITION":"PG"}]),{"stale":True}
        self.assertEqual(fill_missing_positions(top,stale).iloc[0]["POSITION"],"")
        def mismatched(team):
            return pd.DataFrame([{"PLAYER_ID":"987","POSITION":"PG"}]),{"stale":False}
        self.assertEqual(fill_missing_positions(top,mismatched).iloc[0]["POSITION"],"")

    def test_cache_key_changed_and_center_fixture_remains(self):
        app=Path("app.py").read_text(encoding="utf-8")
        self.assertIn("def load_daily_ranking_v713(",app)
        self.assertIn("load_daily_ranking_v713(season,today",app)
        start=app.index("if page == '🏠 Centrum':")
        end=app.index("elif page == '📆 Terminarz':",start)
        center=app[start:end]
        self.assertIn('day_navigation("center", zone)',center)
        self.assertIn("show_top10(top)",center)
        self.assertIn("Injury report",center)


if __name__=="__main__":
    unittest.main()
