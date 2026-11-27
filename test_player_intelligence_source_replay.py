"""Offline tests for source captures and chronological replay."""
import unittest
import json
from copy import deepcopy
import pandas as pd
from player_intelligence.nba_source import SCHEDULE, BOX, Capture, capture_json, schedule_finals, collect_recent
from player_intelligence.backtest import replay
from test_player_intelligence_nba_boxscore import fixture as box_fixture, OBS
from test_player_intelligence_research import research_fixture, forecast_pair
from test_player_intelligence_pregame_snapshot import NOW, TIP


def schedule_payload():
    payload,expected=box_fixture()
    g=payload["game"]
    return {"leagueSchedule":{"gameDates":[{"games":[{
        "gameId":expected["game_id"],"gameStatus":3,"gameDateTimeUTC":expected["start_utc"],
        "homeTeam":g["homeTeam"],"awayTeam":g["awayTeam"]}]}]}}


class Response:
    def __init__(self,payload,status=200):
        self.raw=json.dumps(payload).encode()
        self.status_code=status
    def __enter__(self): return self
    def __exit__(self,*args): return False
    def iter_content(self,chunk_size): yield self.raw


class Session:
    def __init__(self,*,bad_box=False,status=200):
        self.calls=[]
        self.bad_box=bad_box
        self.status=status
    def get(self,url,**kwargs):
        self.calls.append((url,kwargs))
        if url==SCHEDULE:
            return Response(schedule_payload(),self.status)
        p,_=box_fixture()
        if self.bad_box:
            p["game"]["period"]=5
        return Response(p)


class SourceTests(unittest.TestCase):
    def test_two_bounded_requests_and_provenance(self):
        s=Session()
        result=collect_recent(season_prefix="00226",session=s,clock=lambda:OBS)
        self.assertEqual(result["accepted_games"],1)
        self.assertEqual(result["accepted_player_rows"],12)
        self.assertEqual(len(s.calls),2)
        self.assertEqual(s.calls[1][0],BOX.format("0022600201"))
        self.assertFalse(s.calls[0][1]["allow_redirects"])
        self.assertIn("#sha256=",result["rows"][0]["boxscore_evidence_ref"])

    def test_rejections_are_explicit(self):
        s=Session(bad_box=True)
        result=collect_recent(season_prefix="00226",session=s,clock=lambda:OBS)
        self.assertEqual(result["accepted_games"],0)
        self.assertEqual(len(result["rejected"]),1)
        self.assertIn("regulation-only",result["rejected"][0]["reason"])

    def test_arbitrary_url_redirect_and_wrong_season(self):
        s=Session()
        with self.assertRaisesRegex(ValueError,"unapproved"):
            capture_json("https://example.invalid/",session=s,clock=lambda:OBS)
        self.assertEqual(s.calls,[])
        with self.assertRaisesRegex(ValueError,"HTTP 302"):
            capture_json(SCHEDULE,session=Session(status=302),clock=lambda:OBS)
        cap=Capture(schedule_payload(),OBS,"fixture")
        self.assertEqual(schedule_finals(cap,season_prefix="00225",asof=OBS),[])

    def test_duplicate_and_future_schedule(self):
        p=schedule_payload()
        games=p["leagueSchedule"]["gameDates"][0]["games"]
        games.append(deepcopy(games[0]))
        cap=Capture(p,OBS,"fixture")
        with self.assertRaisesRegex(ValueError,"duplicate"):
            schedule_finals(cap,season_prefix="00226",asof=OBS)
        with self.assertRaisesRegex(ValueError,"future"):
            schedule_finals(cap,season_prefix="00226",asof="2026-11-25T05:00:00Z")


class ReplayTests(unittest.TestCase):
    def test_replay_is_separate_and_excludes_future_logs(self):
        f=research_fixture()
        logs=f.pop("logs")
        f.pop("n")
        f["captured_at"]=NOW+pd.Timedelta(minutes=1)
        _,_,actuals=forecast_pair()
        args=dict(cases=[f],historical_logs=logs,actuals=actuals,
                  evaluation_asof=TIP+pd.Timedelta(hours=6),n=200)
        r=replay(**args)
        self.assertEqual(r["metrics"]["paired_players"],20)
        self.assertEqual(r["forecast_count"],4)
        self.assertIn("not_prospective",r["evaluation_mode"])
        args["historical_logs"]=logs+actuals
        self.assertEqual(replay(**args),r)

    def test_late_or_duplicate_case_rejected(self):
        f=research_fixture()
        logs=f.pop("logs")
        f.pop("n")
        f["captured_at"]=NOW+pd.Timedelta(minutes=1)
        args=dict(historical_logs=logs,actuals=[],evaluation_asof=TIP+pd.Timedelta(hours=6),n=200)
        with self.assertRaisesRegex(ValueError,"one predeclared"):
            replay(cases=[f,f],**args)
        f["captured_at"]=TIP
        with self.assertRaisesRegex(ValueError,"timing"):
            replay(cases=[f],**args)

if __name__=="__main__":
    unittest.main()
