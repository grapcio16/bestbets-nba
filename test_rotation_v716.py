"""Regression tests for BestBets v7.16 roster/availability insights."""
import unittest
from pathlib import Path

import pandas as pd

from rotation_intelligence import minutes_trends,rotation_report,status_class
from simulation_engine import simulate_game


class RotationMinutesTests(unittest.TestCase):
    def setUp(self):
        self.start=pd.Timestamp("2026-11-11T00:00:00Z")
        days=pd.date_range("2026-11-01T00:00:00Z",periods=7,freq="D")
        self.logs=pd.DataFrame([
            {"PLAYER_NAME":"A Star","TEAM_ABBREVIATION":"BOS",
             "GAME_DATE":day,"GAME_ID":str(200+n),"MIN":v}
            for n,(day,v) in enumerate(zip(days,[18,20,20,22,33,34,35]))
        ]+[
            {"PLAYER_NAME":"A Star","TEAM_ABBREVIATION":"BOS",
             "GAME_DATE":pd.Timestamp("2026-11-12T00:00:00Z"),
             "GAME_ID":"future","MIN":48},
            {"PLAYER_NAME":"Different Team Player","TEAM_ABBREVIATION":"NYK",
             "GAME_DATE":days[-1],"GAME_ID":"another","MIN":40}
        ])

    def test_last_three_and_seven_no_future_leakage(self):
        result=minutes_trends(self.logs,self.start,home="BOS",away="LAL")
        self.assertEqual(len(result),1)
        row=result.iloc[0]
        self.assertEqual(row["n"],7)
        self.assertEqual(row["avg3"],34.)
        self.assertEqual(row["avg7"],26.)
        self.assertEqual(row["delta"],8.)
        self.assertEqual(row["trend"],"Więcej minut")

    def test_short_sample_is_not_trend(self):
        sample=self.logs.iloc[:3]
        row=minutes_trends(sample,self.start).iloc[0]
        self.assertEqual(row["n"],3)
        self.assertEqual(row["trend"],"Za mała próba")
        self.assertTrue(pd.isna(row["delta"]))

    def test_duplicate_match_no_double_weight(self):
        duplicate=pd.concat([self.logs,self.logs.iloc[[0]]],ignore_index=True)
        row=minutes_trends(duplicate,self.start,home="BOS",away="LAL").iloc[0]
        self.assertEqual(row["n"],7)


class InjuryCoverageTests(unittest.TestCase):
    def setUp(self):
        self.players=pd.DataFrame([
            {"Drużyna":"BOS","Zawodnik":"A Star","Minuty":32.0,
             "PTS":24.4,"Próba występów":7},
            {"Drużyna":"BOS","Zawodnik":"Role Player","Minuty":21.0,
             "PTS":11.4,"Próba występów":6},
            {"Drużyna":"LAL","Zawodnik":"A Star","Minuty":30.0,
             "PTS":26,"Próba występów":7},
        ])
        self.inj=pd.DataFrame([
            {"Drużyna":"BOS","Zawodnik":"A Star","Status ESPN":"Out"},
            {"Drużyna":"BOS","Zawodnik":"Bench Player","Status ESPN":"Doubtful"},
            {"Drużyna":"LAL","Zawodnik":"A Star","Status ESPN":"Questionable"},
        ])
        self.rosters={"BOS":pd.DataFrame([
            {"Zawodnik":"A Star","Pozycja":"PG"},
            {"Zawodnik":"Role Player","Pozycja":"SF"}]),
            "LAL":pd.DataFrame([{"Zawodnik":"A Star","Pozycja":"C"}])}
        self.trends=pd.DataFrame([
            {"team":"BOS","player":"A Star","n":7,"avg3":34.0,"avg7":26.0,
             "delta":8.0,"trend":"Więcej minut"},
            {"team":"BOS","player":"Role Player","n":6,"avg3":20.0,"avg7":21.0,
             "delta":-1.0,"trend":"Stabilnie"},
        ])

    def test_strict_team_and_athlete_status_match(self):
        table,summary,alerts=rotation_report(
            self.players,self.inj,"BOS","LAL",rosters=self.rosters,
            trends=self.trends,injury_meta={"available":True,"stale":False})
        boss=table[(table["Drużyna"]=="BOS")&(table["Zawodnik"]=="A Star")].iloc[0]
        laker=table[(table["Drużyna"]=="LAL")&(table["Zawodnik"]=="A Star")].iloc[0]
        self.assertEqual(boss["Status ESPN"],"Out")
        self.assertEqual(boss["Pozycja"],"PG")
        self.assertEqual(boss["Zmiana 3 vs 7"],8.)
        self.assertEqual(laker["Status ESPN"],"Questionable")
        self.assertEqual(laker["Pozycja"],"C")
        self.assertEqual(len(table),4) # injury-only Bench Player included
        self.assertTrue(pd.isna(table.loc[
            table["Zawodnik"]=="Bench Player","Minuty modelu"].iloc[0]))
        c=summary.set_index("Drużyna")
        self.assertEqual(c.loc["BOS","Minuty modelu: Out/Doubtful"],32.)
        self.assertEqual(c.loc["LAL","Minuty modelu: Questionable/DTD"],30.)
        self.assertEqual(c.loc["BOS","Zawodnicy z wahaniem minut >=4"],1)
        self.assertTrue(any("minuty" in a.lower() for a in alerts))

    def test_stale_or_empty_espn_disables_exposure(self):
        for meta in ({"available":True,"stale":True},
                     {"available":False,"stale":False}):
            table,summary,notices=rotation_report(
                self.players,self.inj,"BOS","LAL",
                trends=self.trends,injury_meta=meta)
            self.assertTrue(summary["Minuty modelu: Out/Doubtful"].isna().all())
            self.assertFalse(summary["Dane statusu aktualne"].any())

    def test_unknown_is_not_healthy_or_zero(self):
        table,summary,_=rotation_report(
            self.players,pd.DataFrame(),"BOS","LAL",
            injury_meta={"available":False,"stale":False})
        self.assertTrue((table["Ocena statusu"]=="Brak potwierdzenia").all())
        self.assertTrue(summary["Minuty modelu: Out/Doubtful"].isna().all())

    def test_status_classifier_is_explicit(self):
        self.assertEqual(status_class("Out"),"Out")
        self.assertEqual(status_class("Doubtful"),"Doubtful")
        self.assertEqual(status_class("Questionable"),"Questionable")
        self.assertEqual(status_class("Day-To-Day"),"Day-to-day")
        self.assertEqual(status_class("Probable"),"Probable")
        self.assertEqual(status_class("Not reported"),"Inny / niepotwierdzony")
        self.assertEqual(status_class(""),"Brak potwierdzenia")

    def test_prod_simulation_unchanged_and_research_ui_is_on_demand(self):
        script=Path("simulation_view.py").read_text(encoding="utf-8")
        self.assertIn("'🩺 Rotacja i absencje'",script)
        self.assertIn("rotation_report(",script)
        self.assertIn("return per_game.get(str(g['game_id']),pd.DataFrame()),extra",script)
        # Team score model remains independent from the research table.
        game={"game_id":"102","home":"BOS","away":"LAL"}
        mean={"home":110.,"away":108.,"source":"test"}
        x,_,home1,_=simulate_game(game,mean)
        y,_,home2,_=simulate_game(game,mean)
        self.assertEqual(x["home_points"],y["home_points"])
        self.assertTrue((home1==home2).all())


if __name__=="__main__":
    unittest.main()
