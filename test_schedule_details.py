"""Deterministic tests for free on-demand ESPN schedule details."""
from __future__ import annotations
import unittest
from unittest.mock import patch

from bestbets_schedule_details import (
    parse_game_details, load_game_details, _verified_schedule_event,
    _periods_from_plays, _verified_scoreboard_quarters, fetch_game_history,
)

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
        with patch("bestbets_schedule_details.fetch_game_history",return_value={"h2h":[],"recent":{},"coverage":[],"error":""}), \
             patch("sources.memoized_json",return_value=(sample(),{"stale":False})) as fetch:
            result=load_game_details(EVENT,"NYK","BOS","final")
        self.assertEqual(result["id"],EVENT)
        self.assertFalse(result["stale"])
        self.assertEqual(fetch.call_count,1)
        self.assertEqual(fetch.call_args.kwargs["params"],{"event":EVENT})

    def test_play_by_play_running_scores_are_converted_to_quarter_points(self):
        raw={"plays":[
            {"period":{"number":1},"awayScore":12,"homeScore":10},
            {"period":{"number":1},"awayScore":24,"homeScore":22},
            {"period":{"number":2},"awayScore":28,"homeScore":29},
            {"period":{"number":2},"awayScore":48,"homeScore":51},
        ]}
        self.assertEqual(_periods_from_plays(raw),[
            {"period":"Q1","away":24,"home":22},
            {"period":"Q2","away":24,"home":29},
        ])

    def test_quarters_use_plays_when_summary_competitors_lack_linescores(self):
        raw=sample()
        for row in raw["header"]["competitions"][0]["competitors"]:
            row.pop("linescores")
        raw["plays"]=[
            {"period":{"number":1},"awayScore":26,"homeScore":29},
            {"period":{"number":2},"awayScore":54,"homeScore":62},
        ]
        self.assertEqual(parse_game_details(raw,EVENT,"NYK","BOS")["quarters"],[
            {"period":"Q1","away":26,"home":29},
            {"period":"Q2","away":28,"home":33},
        ])

    def test_scoreboard_fallback_requires_same_event_and_both_teams(self):
        raw={"events":[
            {"id":EVENT, "competitions":[{"id":EVENT,"competitors":[
                {"homeAway":"away","team":{"abbreviation":"NY"},
                 "linescores":[{"value":26},{"value":28}]},
                {"homeAway":"home","team":{"abbreviation":"BOS"},
                 "linescores":[{"value":29},{"value":33}]}
            ]}]}
        ]}
        with patch("sources.memoized_json",return_value=(raw,{"stale":False})) as fetch:
            result=_verified_scoreboard_quarters(EVENT,"NYK","BOS","2026-11-21T01:00:00Z")
        self.assertEqual(result[1],{"period":"Q2","away":28,"home":33})
        self.assertEqual(fetch.call_args.kwargs["params"]["dates"],"20261120")
        raw["events"][0]["competitions"][0]["competitors"][0]["team"]["abbreviation"]="ATL"
        with patch("sources.memoized_json",return_value=(raw,{"stale":False})):
            self.assertEqual(_verified_scoreboard_quarters(EVENT,"NYK","BOS","2026-11-21T01:00:00Z"),[])

    def test_history_has_only_completed_prior_verified_games_across_seasons(self):
        def fixture(event_id, when, away="CHA", home="ATL", state="post"):
            return {
                "id":str(event_id),"date":when,
                "status":{"type":{"completed":state=="post","state":state}},
                "competitions":[{"id":str(event_id),"date":when,"competitors":[
                    {"homeAway":"away","team":{"abbreviation":away},"score":"97"},
                    {"homeAway":"home","team":{"abbreviation":home},"score":"111"},
                ]}]
            }
        old=fixture("4018100000","2026-03-05T01:00:00Z")
        current=fixture("4018100001","2026-11-01T01:00:00Z")
        future=fixture("4018100002","2026-12-01T01:00:00Z")
        pending=fixture("4018100003","2026-11-10T01:00:00Z",state="pre")
        wrong=fixture("4018100004","2026-11-03T01:00:00Z",away="MIA",home="ATL")
        self.assertIsNone(_verified_schedule_event(pending))
        self.assertIsNone(_verified_schedule_event({"id":"fake"}))
        def response(url,params=None,**kwargs):
            season=params["season"]
            if season==2026:
                return ({"events":[old]},{"stale":False})
            if "/teams/30/" in url:
                return ({"events":[current,future,pending,wrong]},{"stale":False})
            return ({"events":[current]},{"stale":False})
        with patch("sources.memoized_json",side_effect=response) as fetch:
            result=fetch_game_history("CHA","ATL","2026-11-21T01:00:00Z","4018100999")
        self.assertEqual([g["id"] for g in result["h2h"]],["4018100001","4018100000"])
        self.assertEqual(result["recent"]["CHA"][0]["id"],"4018100001")
        self.assertTrue(result["coverage"])
        self.assertFalse(result["error"])
        self.assertEqual(fetch.call_count,3)

    def test_no_invented_history_if_espn_is_unavailable(self):
        with patch("sources.memoized_json",side_effect=TimeoutError("ESPN")):
            result=fetch_game_history("CHA","ATL","2026-11-21T01:00:00Z",EVENT)
        self.assertEqual(result["h2h"],[])
        self.assertEqual(result["recent"]["CHA"],[])
        self.assertTrue(result["error"])

    def test_game_details_integrates_history_and_scoreboard_fallback(self):
        raw=sample()
        for c in raw["header"]["competitions"][0]["competitors"]:
            c.pop("linescores")
        scoreboard={"events":[{"id":EVENT,"competitions":[{
            "id":EVENT,"competitors":[
                {"homeAway":"away","team":{"abbreviation":"NY"},"linescores":[{"value":26}]},
                {"homeAway":"home","team":{"abbreviation":"BOS"},"linescores":[{"value":29}]}
            ]}]}]}
        def response(url,params=None,**kwargs):
            if "scoreboard" in url:return (scoreboard,{"stale":False})
            return (raw,{"stale":False})
        history={"h2h":[],"recent":{"NYK":[],"BOS":[]},"coverage":[{"team":"NYK","season":2027}],"error":""}
        with patch("sources.memoized_json",side_effect=response), \
             patch("bestbets_schedule_details.fetch_game_history",return_value=history):
            result=load_game_details(EVENT,"NYK","BOS","final")
        self.assertEqual(result["quarters"],[{"period":"Q1","away":26,"home":29}])
        self.assertEqual(result["history"],history)


if __name__ == "__main__":
    unittest.main()
