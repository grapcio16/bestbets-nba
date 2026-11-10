"""Regression tests: nested ESPN season logs, fallback coverage and card data."""
import unittest

import pandas as pd

from core import norm_name, normalize_logs
from espn_player_data import parse_gamelog, full_season_team_boxscores
from screenshot_import import parse_ocr_tokens, market_from_header
from season_props import clean_player_season, observed_hit_rates, analyze_season_offers


def season_fixture(n=13):
    labels=["MIN","FG","3PT","FT","REB","AST","PTS"]
    events={};stats=[]
    start=pd.Timestamp("2026-10-12T00:00:00Z")
    for i in range(n):
        event_id=str(401999100+i)
        day=start+pd.Timedelta(days=i)
        events[event_id]={
            "id":event_id,"date":day.isoformat(),
            "opponent":{"abbreviation":"NYK"},
            "team":{"abbreviation":"BOS"},"atVs":"vs."}
        stats.append({"eventId":event_id,
                      "stats":[str(23+i%6),"7-15","2-5","1-2",
                               str(4+i%3),str(3+i%4),str(15+i%9)]})
    return {"labels":labels,
            "events":events,
            "seasonTypes":[{"id":2,"displayName":"Regular Season",
                            "categories":[{"events":stats}]}]}


class EspnNestedLogTests(unittest.TestCase):
    def test_thirteen_real_game_stats_not_event_metadata_only(self):
        p=season_fixture(13)
        df,meta=parse_gamelog(p,"123","Sample Player","BOS",return_meta=True)
        self.assertEqual(len(df),13)
        self.assertEqual(meta["parsed_games"],13)
        self.assertEqual(meta["source_format"],"nested-seasonTypes")
        self.assertEqual(int(df.iloc[0]["PTS"]),15)
        self.assertEqual(int(df.iloc[-1]["PTS"]),18)
        self.assertEqual(set(df["PLAYER_ID"]),{"123"})
        self.assertEqual(set(df["TEAM_ABBREVIATION"]),{"BOS"})
        self.assertTrue((df["FG3M"]==2).all())
        self.assertEqual(df["GAME_ID"].nunique(),13)

    def test_duplicate_category_does_not_duplicate_games(self):
        p=season_fixture(11)
        p["seasonTypes"][0]["categories"].append(
            {"events":p["seasonTypes"][0]["categories"][0]["events"][:2]})
        self.assertEqual(len(parse_gamelog(p,"123","Sample Player","BOS")),11)

    def test_dnp_future_and_playoff_missing_stat_are_never_fake_games(self):
        p=season_fixture(12)
        p["seasonTypes"][0]["categories"][0]["events"].append(
            {"eventId":"unseen","stats":["DNP","--","--","--","--","--","--"]})
        p["seasonTypes"].append({
            "id":3,"displayName":"Postseason","categories":[
                {"events":[{"eventId":"playoffs","stats":["33","4-9",
                    "1-3","2-2","4","2","11"]}]}]})
        self.assertEqual(len(parse_gamelog(p,"123","Sample Player","BOS")),12)

    def test_malformed_stats_fail_closed(self):
        with self.assertRaises(ValueError):
            parse_gamelog({"events":{"1":{"date":"2026-11-01"}},
                           "labels":["MIN","PTS"]},
                          "123","Name","BOS")

    def test_recover_complete_team_season_from_final_boxscores(self):
        days=pd.date_range("2026-10-20",periods=12,freq="D",tz="UTC")
        finals=pd.DataFrame([{
            "game_id":str(40000+i),"start_utc":day,
            "home":"BOS","away":"NYK","status_code":3}
            for i,day in enumerate(days)])
        called=[]
        def fake_box(game):
            called.append(game["game_id"])
            return [{
                "PLAYER_NAME":"Sample Player","PLAYER_ID":"123",
                "GAME_ID":game["game_id"],"GAME_DATE":game["start_utc"],
                "TEAM_ABBREVIATION":"BOS","MATCHUP":"BOS vs NYK",
                "MIN":29,"PTS":18,"REB":4,"AST":5,"FG3M":2,
            }]
        box,meta=full_season_team_boxscores(
            finals,{"BOS"},pd.Timestamp("2026-11-10T00:00:00Z"),
            boxscore_fetch=fake_box,max_workers=2)
        self.assertEqual(len(box),12)
        self.assertEqual(meta["success"],12)
        self.assertFalse(meta["partial"])
        self.assertEqual(len(called),12)

    def test_unfinished_games_not_used_in_recovery(self):
        events=pd.DataFrame([
            {"game_id":"1","start_utc":"2026-11-08T02:00:00Z",
             "home":"BOS","away":"NYK","status_code":3},
            {"game_id":"2","start_utc":"2026-11-15T02:00:00Z",
             "home":"BOS","away":"NYK","status_code":3},
            {"game_id":"3","start_utc":"2026-11-08T02:00:00Z",
             "home":"BOS","away":"NYK","status_code":1},
        ])
        captured=[]
        def one(game):
            captured.append(game["game_id"])
            return [{"GAME_ID":game["game_id"],"PLAYER_ID":"123"}]
        box,meta=full_season_team_boxscores(
            events,{"BOS"},"2026-11-10T00:00:00Z",boxscore_fetch=one)
        self.assertEqual(captured,["1"])
        self.assertEqual(meta["attempted"],1)


class ScreenshotUiDataTests(unittest.TestCase):
    def test_l5_l10_l15_season_and_noninvented_model(self):
        game=season_fixture(13)
        raw=parse_gamelog(game,"123","Sample Player","BOS")
        clean=clean_player_season(
            normalize_logs(raw),"Sample Player","2026-27",
            "2026-11-10T00:00:00Z",player_id="123")
        self.assertEqual(len(clean),13)
        hits=observed_hit_rates(clean,"PTS",17.5)
        self.assertEqual(hits["season"]["n"],13)
        self.assertEqual(hits["last5"]["n"],5)
        self.assertEqual(hits["last10"]["n"],10)
        self.assertEqual(hits["last15"]["n"],13)
        self.assertAlmostEqual(
            hits["season"]["over_pct"]+hits["season"]["under_pct"],100,places=1)

        offers=pd.DataFrame([{"Zawodnik":"Sample Player",
                              "Rynek":"PTS","Linia":17.5,
                              "Kurs OVER":1.75,"Kurs UNDER":1.96}])
        identities={norm_name("Sample Player"):{"id":"123","team":"BOS",
                    "source":"ESPN nested","partial":False,"position":"SF"}}
        histories={norm_name("Sample Player"):normalize_logs(raw)}
        analyzed=analyze_season_offers(
            offers,histories,identities,{},pd.DataFrame(),
            "2026-27","2026-11-10T00:00:00Z")
        self.assertEqual(analyzed.iloc[0]["Występy sezon"],13)
        self.assertEqual(analyzed.iloc[0]["Pozycja"],"SF")
        self.assertIn("OVER L5 %",analyzed.columns)
        self.assertIn("OVER L15 %",analyzed.columns)
        self.assertEqual(analyzed.iloc[0]["Status"],"MODEL TESTOWY")

    def test_mixed_3pt_and_assists_are_distinct_markets(self):
        def t(text,left,top):
            return {"text":text,"left":left,"top":top,"width":42,
                    "height":14,"conf":91}
        tokens=[
            t("Test",10,60),t("Player",74,60),
            t("Powyżej",170,60),t("1,5",270,60),
            t("3PM",330,60),t("1,85",450,60),
            t("Other",10,111),t("Person",74,111),
            t("Powyżej",170,111),t("2,5",270,111),
            t("Asysty",330,111),t("1,77",450,111),
        ]
        result,_=parse_ocr_tokens(tokens,500,default_market="PTS")
        self.assertEqual(len(result),2)
        self.assertEqual(result.loc[result["Zawodnik"]=="Test Player","Rynek"].iloc[0],"FG3M")
        self.assertEqual(result.loc[result["Zawodnik"]=="Other Person","Rynek"].iloc[0],"AST")


if __name__=="__main__":
    unittest.main()
