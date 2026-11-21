"""Deterministic tests for free on-demand ESPN schedule details."""
from __future__ import annotations
import unittest
from unittest.mock import patch

from bestbets_schedule_details import parse_game_details, load_game_details

EVENT = "4018100123"


def sample():
    def competitor(code, side, score1, score2):
        return {"homeAway": side, "team": {"abbreviation": code},
                "linescores": [{"value":score1}, {"value":score2}]}

    def stats(code, pct, assists):
        return {"team": {"abbreviation":code}, "statistics":[
            {"name":"fieldGoalPct", "displayValue": str(pct)},
            {"name":"threePointFieldGoalPct", "displayValue":"38.5"},
            {"name":"totalRebounds", "displayValue":"42"},
            {"name":"assists", "displayValue":str(assists)},
            {"name":"totalTurnovers", "displayValue":"11"}
        ]}

    def player(code, name, pts, reb, ast):
        return {"team":{"abbreviation":code}, "statistics":[{
            "labels":["MIN","FG","3PT","REB","AST","PTS"],
            "athletes":[{"athlete":{"id":"1354","displayName":name},
                         "stats":["32","8-16","3-7",str(reb),str(ast),str(pts)]}]
        }]}

    return {"header":{"id":EVENT,"competitions":[{
        "id":EVENT,"date":"2026-11-21T01:00:00Z",
        "competitors":[competitor("BOS","home",29,33),competitor("NY","away",26,28)]
    }]}, "boxscore":{
        "teams":[stats("BOS",49.5,27),stats("NY",45.1,21)],
        "players":[player("BOS","Demo Starter",26,8,4),
                   player("NY","Demo Visitor",22,7,5)]
    }}


class ScheduleDetailsTests(unittest.TestCase):
    def test_quarters_team_stats_and_players_from_verified_summary(self):
        result = parse_game_details(sample(),EVENT,"NYK","BOS")
        self.assertEqual(result["quarters"], [
            {"period":"Q1","away":26,"home":29},
            {"period":"Q2","away":28,"home":33}
        ])
        self.assertEqual(result["team_stats"][0], {"label":"Celne z gry %","away":"45.1%","home":"49.5%"})
        self.assertEqual(result["leaders"]["home"][0]["name"],"Demo Starter")
        self.assertEqual(result["leaders"]["away"][0]["pts"],22)
        self.assertEqual(result["leaders"]["away"][0]["reb"],7)

    def test_rejects_mismatched_id_and_teams(self):
        wrong=sample()
        wrong["header"]["id"]="4018999999"
        with self.assertRaises(ValueError):
            parse_game_details(wrong,EVENT,"NYK","BOS")
        with self.assertRaises(ValueError):
            parse_game_details(sample(),EVENT,"BOS","NYK")

    def test_absent_details_are_not_invented(self):
        src=sample()
        src["boxscore"]={}
        for competitor in src["header"]["competitions"][0]["competitors"]:
            competitor.pop("linescores")
        parsed=parse_game_details(src,EVENT,"NYK","BOS")
        self.assertEqual(parsed["quarters"],[])
        self.assertEqual(parsed["team_stats"],[])
        self.assertEqual(parsed["leaders"],{"away":[],"home":[]})

    def test_only_known_event_types_can_fetch(self):
        for invalid in ("../sample","abc", "4018;1", "4018100123456789"):
            with self.assertRaises(ValueError):
                load_game_details(invalid,"NYK","BOS","final")
        with self.assertRaises(ValueError):
            load_game_details(EVENT,"NYK","BOS","scheduled")

    def test_single_cached_summary_request_for_verified_game(self):
        with patch("sources.memoized_json",return_value=(sample(),{"stale":False})) as fetch:
            result=load_game_details(EVENT,"NYK","BOS","final")
        self.assertEqual(result["id"],EVENT)
        self.assertFalse(result["stale"])
        self.assertEqual(fetch.call_count,1)
        self.assertEqual(fetch.call_args.kwargs["params"],{"event":EVENT})


if __name__ == "__main__":
    unittest.main()
