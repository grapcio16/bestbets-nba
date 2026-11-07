"""BestBets v7.7 final-night quality gates: no fictitious lineup or model drift."""
import unittest

import numpy as np
import pandas as pd

from availability_context import matchup_injuries,player_minutes_brief,team_code
from simulation_engine import (completed_team_scores,advanced_ratings,
    select_matchup_means,simulate_game)


class AvailabilityReportTests(unittest.TestCase):
    def test_correct_team_alias_and_exclude_unrelated_injuries(self):
        self.assertEqual(team_code("San Antonio Spurs"),"SAS")
        self.assertEqual(team_code("GS"),"GSW")
        sample=pd.DataFrame([
            {"player":"Victor Wembanyama","team":"SA","status":"Questionable","note":"Back"},
            {"player":"Victor Wembanyama","team":"SA","status":"Questionable","note":"Back"},
            {"player":"Other Player","team":"DEN","status":"Out","note":""},
            {"player":"Unnamed","team":"","status":"Out","note":""},
            {"player":"Jerami Grant","team":"POR","status":"Probable","note":""}
        ])
        result,meta=matchup_injuries(sample,"POR","SAS",{"stale":False})
        self.assertEqual(len(result),2)
        self.assertEqual(set(result["Drużyna"]),{"SAS","POR"})
        self.assertTrue(meta["available"])
        self.assertFalse(meta["stale"])

    def test_empty_report_does_not_mean_healthy(self):
        report,meta=matchup_injuries(pd.DataFrame(),"SAS","POR")
        self.assertTrue(report.empty)
        self.assertFalse(meta["available"])
        self.assertIn("NIE potwierdza zdrowia",meta["warning"])

    def test_stale_status_flagged(self):
        sample=pd.DataFrame([{"player":"Test","team":"SAS",
                              "status":"Out","note":""}])
        data,meta=matchup_injuries(sample,"SAS","POR",{"stale":True})
        self.assertEqual(len(data),1)
        self.assertTrue(meta["stale"])

    def test_minutes_only_existing_observed_player_projections(self):
        players=pd.DataFrame([
            {"Zawodnik":"Victor Wembanyama","Drużyna":"SAS","Minuty":33.4,
             "Próba występów":7},
            {"Zawodnik":"Other SAS player","Drużyna":"SAS","Minuty":25.1,
             "Próba występów":5},
            {"Zawodnik":"Aaron Gordon","Drużyna":"DEN","Minuty":30.0,
             "Próba występów":7},
        ])
        injuries=pd.DataFrame([{"Zawodnik":"Victor Wembanyama",
                               "Drużyna":"SAS","Status ESPN":"Questionable",
                               "Informacja":"Back"}])
        brief=player_minutes_brief(players,"SAS","POR",injuries)
        self.assertEqual(len(brief),2)
        status=brief.loc[brief["Zawodnik"]=="Victor Wembanyama",
                         "Status kontuzji"].iloc[0]
        self.assertEqual(status,"Questionable")
        other=brief.loc[brief["Zawodnik"]=="Other SAS player",
                        "Status kontuzji"].iloc[0]
        self.assertIn("NIEPOTWIERDZONY",other)


class ModelParityTests(unittest.TestCase):
    def setUp(self):
        self.game={"game_id":"401999989","home":"SAS","away":"POR",
                   "start_utc":"2026-11-08T04:00:00Z"}
        self.history={"SAS":[],"POR":[]}
        base=pd.Timestamp("2026-10-24T02:00:00Z")
        for n in range(10):
            t=base+pd.Timedelta(days=n)
            self.history["SAS"].append((t,112+2*n,107-n,"POR"))
            self.history["POR"].append((t,113-n,111+n,"SAS"))

    def test_selecting_legacy_or_research_changes_mean_only_when_requested(self):
        first=select_matchup_means("SAS","POR",{},self.history,False)
        second=select_matchup_means("SAS","POR",{},self.history,True)
        self.assertEqual(first["source"],"ESPN • średnie z 12 meczów (v7.2)")
        self.assertIn("ważona forma",second["source"])
        self.assertNotEqual(first["home"],second["home"])

    def test_cards_and_detail_deterministic_for_each_model(self):
        for research in (False,True):
            mean=select_matchup_means("SAS","POR",{},self.history,research)
            card,_,home,_=simulate_game(self.game,mean)
            detail,_,recomputed,_=simulate_game(self.game,mean)
            self.assertEqual(card["home_win_pct"],detail["home_win_pct"])
            self.assertEqual(card["total_points"],detail["total_points"])
            np.testing.assert_array_equal(home,recomputed)

    def test_verified_advanced_ratings_only_for_complete_teams(self):
        data=pd.DataFrame([
            {"TEAM_ABBREVIATION":"SAS","PACE":100.3,
             "OFF_RATING":115.6,"DEF_RATING":108.9},
            {"TEAM_ABBREVIATION":"POR","PACE":np.nan,
             "OFF_RATING":115.6,"DEF_RATING":108.9}
        ])
        valid=advanced_ratings(data)
        self.assertIn("SAS",valid)
        self.assertNotIn("POR",valid)
        # Without BOTH official advanced ratings, ESPN score history is used.
        result=select_matchup_means("SAS","POR",valid,self.history,False)
        self.assertIn("ESPN",result["source"])


if __name__=="__main__":
    unittest.main()
