"""Regression checks for the November 8 international UI release."""
import unittest
from datetime import date, datetime
from zoneinfo import ZoneInfo

import pandas as pd

from viewer_time import choices, resolve_zone, localize, games_on_day, local_day_start_end
from dashboard_data import previous_day_ranking


class Timezones(unittest.TestCase):
    def test_browser_timezone_and_manual_override(self):
        self.assertEqual(str(resolve_zone("Automatyczna", "America/New_York")), "America/New_York")
        self.assertEqual(str(resolve_zone("Asia/Tokyo", "America/New_York")), "Asia/Tokyo")
        self.assertEqual(str(resolve_zone("bad/zone", "Europe/Warsaw")), "UTC")
        self.assertIn("America/Chicago", choices())

    def test_spring_and_fall_dst(self):
        ny = ZoneInfo("America/New_York")
        spring = localize(pd.Series(["2026-03-08T06:30:00Z", "2026-03-08T07:30:00Z"]), ny)
        self.assertEqual(spring.dt.strftime("%H:%M").tolist(), ["01:30", "03:30"])
        fall = localize(pd.Series(["2026-11-01T05:30:00Z", "2026-11-01T06:30:00Z"]), ny)
        self.assertEqual(fall.dt.strftime("%H:%M").tolist(), ["01:30", "01:30"])
        self.assertEqual(fall.dt.strftime("%z").tolist(), ["-0400", "-0500"])

    def test_day_bounds_vary_with_dst(self):
        ny=ZoneInfo("America/New_York")
        first, last = local_day_start_end(date(2026, 3, 8), ny)
        self.assertEqual((last-first).total_seconds()/3600, 23)
        first, last = local_day_start_end(date(2026, 11, 1), ny)
        self.assertEqual((last-first).total_seconds()/3600, 25)

    def test_different_user_dates_same_utc_instant(self):
        g = pd.DataFrame({"game_id": ["1","2"],"start_utc": ["2026-11-08T00:30:00Z", "2026-11-08T21:00:00Z"]})
        self.assertEqual(games_on_day(g,date(2026,11,7),ZoneInfo("America/Los_Angeles"))["game_id"].tolist(),["1"])
        self.assertEqual(games_on_day(g,date(2026,11,8),ZoneInfo("Europe/Warsaw"))["game_id"].tolist(),["1","2"])


class InjuryTeams(unittest.TestCase):
    def test_espn_aliases_and_player_specific_team(self):
        from sources import injury_rows
        payload={"teams":[
            {"team":{"abbreviation":"NY"},"injuries":[{"athlete":{"displayName":"Player One"},"status":"Out"}]},
            {"team":{"abbreviation":"LAL"},"injuries":[{"athlete":{"displayName":"Player Two","team":{"abbreviation":"GS"}},"status":"Questionable"}]}
        ]}
        items=injury_rows(payload)
        self.assertEqual(items.loc[items.player=="Player One","team"].iloc[0],"NYK")
        self.assertEqual(items.loc[items.player=="Player Two","team"].iloc[0],"GSW")


class CenterRanking(unittest.TestCase):
    def test_rank_from_espn_ids_and_completed_games_only(self):
        games=pd.DataFrame([
            {"game_id":"401-espn","start_utc":"2026-11-08T01:00:00Z","status_code":3,"home":"LAL","away":"BOS"},
            {"game_id":"ongoing","start_utc":"2026-11-08T04:00:00Z","status_code":2,"home":"NYK","away":"MIA"}])
        calls=[]
        def fake_fetch(row):
            calls.append(str(row["game_id"]))
            return [
                {"GAME_ID":"401-espn","PLAYER_ID":"42","PLAYER_NAME":"A","TEAM_ABBREVIATION":"LAL","PTS":30,"REB":8,"AST":6},
                {"GAME_ID":"401-espn","PLAYER_ID":"43","PLAYER_NAME":"B","TEAM_ABBREVIATION":"BOS","PTS":36,"REB":6,"AST":3},
                {"GAME_ID":"401-espn","PLAYER_ID":"43","PLAYER_NAME":"B","TEAM_ABBREVIATION":"BOS","PTS":36,"REB":6,"AST":3}]
        top, meta=previous_day_ranking(games,date(2026,11,8),ZoneInfo("America/Los_Angeles"),fetch=fake_fetch)
        self.assertEqual(calls,["401-espn"])
        self.assertEqual(top["PLAYER_NAME"].tolist(),["B","A"])
        self.assertEqual(len(top),2)
        self.assertEqual(meta["complete_games"],1)
        self.assertEqual(meta["requested_games"],1)


if __name__ == "__main__":
    unittest.main()
