"""Synthetic provider contract tests; no network, credentials or production."""
import unittest
from copy import deepcopy
from player_intelligence.nba_boxscore import parse_regulation_boxscore

TIP = "2026-11-25T01:00:00Z"
OBS = "2026-11-25T06:00:00Z"

def fixture():
    expected = {"verified":True,"provider":"nba","game_id":"0022600201",
                "start_utc":TIP,"home":"BOS","away":"NYK",
                "home_score":110,"away_score":105}
    game = {"gameId":expected["game_id"],"gameStatus":3,"period":4,"gameTimeUTC":TIP}
    for offset,side in ((100,"home"),(200,"away")):
        score=expected[side+"_score"]
        players=[{"personId":offset+i,"played":"1","statistics":{
            "minutes":"PT48M00.00S","points":score//5,"reboundsTotal":5,
            "assists":3,"threePointersMade":2}} for i in range(5)]
        players.append({"personId":offset+5,"played":"0"})
        game[side+"Team"]={"teamTricode":expected[side],"score":score,"players":players}
    return {"game":game},expected


class NBABoxTests(unittest.TestCase):
    def test_namespaces_reconciled_stats_and_explicit_dnp(self):
        payload,expected=fixture()
        rows=parse_regulation_boxscore(payload,expected,OBS)
        self.assertEqual(len(rows),12)
        self.assertEqual(rows[0]["game_id"],"nba:0022600201")
        self.assertEqual(rows[0]["player_id"],"nba:100")
        self.assertEqual(rows[5]["minutes"],0)
        self.assertFalse(rows[5]["played"])
        for side in ("home","away"):
            team=[r for r in rows if r["team"]==expected[side]]
            self.assertEqual(sum(r["minutes"] for r in team),240)
            self.assertEqual(sum(r["PTS"] for r in team),expected[side+"_score"])

    def test_reject_nonfinal_overtime_missing_period(self):
        for patch in ({"gameStatus":2},{"period":5},{"period":None},{"gameStatus":None}):
            payload,expected=fixture()
            payload["game"].update(patch)
            with self.subTest(patch=patch),self.assertRaises(ValueError):
                parse_regulation_boxscore(payload,expected,OBS)

    def test_wrong_game_team_time_or_score(self):
        for key,value in (("gameId","0022600202"),("gameTimeUTC","2026-11-25T02:00:00Z")):
            payload,expected=fixture()
            payload["game"][key]=value
            with self.assertRaises(ValueError):
                parse_regulation_boxscore(payload,expected,OBS)
        for key,value in (("teamTricode","MIA"),("score",109)):
            payload,expected=fixture()
            payload["game"]["homeTeam"][key]=value
            with self.assertRaises(ValueError):
                parse_regulation_boxscore(payload,expected,OBS)

    def test_missing_minutes_and_missing_stats_never_become_zero(self):
        for key,value in (("minutes",""),("points",None),("minutes","PT47M60S"),("minutes","PT-1M")):
            payload,expected=fixture()
            payload["game"]["homeTeam"]["players"][0]["statistics"][key]=value
            with self.subTest(key=key,value=value),self.assertRaises(ValueError):
                parse_regulation_boxscore(payload,expected,OBS)

    def test_incomplete_minutes_or_points_fail_atomically(self):
        for key,value in (("minutes","PT47M00S"),("points",21)):
            payload,expected=fixture()
            payload["game"]["homeTeam"]["players"][0]["statistics"][key]=value
            with self.assertRaisesRegex(ValueError,"reconcile"):
                parse_regulation_boxscore(payload,expected,OBS)

    def test_no_ambiguous_played_flag_or_duplicate_identity(self):
        payload,expected=fixture()
        payload["game"]["homeTeam"]["players"][-1].pop("played")
        with self.assertRaisesRegex(ValueError,"played flag"):
            parse_regulation_boxscore(payload,expected,OBS)
        payload,expected=fixture()
        payload["game"]["awayTeam"]["players"][0]["personId"]=100
        with self.assertRaisesRegex(ValueError,"duplicate"):
            parse_regulation_boxscore(payload,expected,OBS)

    def test_no_cross_provider_preseason_or_unverified_fixture(self):
        for patch in ({"provider":"espn"},{"verified":False},{"game_id":"0012600201"}):
            payload,expected=fixture()
            expected.update(patch)
            with self.assertRaises(ValueError):
                parse_regulation_boxscore(payload,expected,OBS)

    def test_capture_time_required_and_conservative_final_delay(self):
        payload,expected=fixture()
        for stamp in ("2026-11-25T03:00:00Z","2026-11-25T06:00:00"):
            with self.assertRaises(ValueError):
                parse_regulation_boxscore(payload,expected,stamp)

if __name__=="__main__":
    unittest.main()
