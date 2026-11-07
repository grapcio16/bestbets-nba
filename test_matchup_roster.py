"""Offline checks for roster-first game details; no ESPN requests required."""
import unittest
import pandas as pd
from matchup_roster import roster_projection_table


class MatchupRosterTests(unittest.TestCase):
    def setUp(self):
        self.roster = pd.DataFrame([
            {"PLAYER_NAME":"Stephen Curry","PLAYER_ID":"3975",
             "TEAM_ABBREVIATION":"GSW","POSITION":"PG"},
            {"PLAYER_NAME":"A Player Without Recent Games","PLAYER_ID":"99999",
             "TEAM_ABBREVIATION":"GSW","POSITION":"SF"},
        ])
        self.forecasts = pd.DataFrame([
            {"Zawodnik":"Stephen Curry","Drużyna":"GSW",
             "PTS":26.3,"REB":4.5,"AST":6.2,"3PM":4.1,
             "Minuty":34.5,"Status ESPN":"Brak wpisu w ESPN",
             "Próba występów":7},
            {"Zawodnik":"Former Player","Drużyna":"GSW",
             "PTS":15,"REB":3,"AST":3,"3PM":1,
             "Minuty":21,"Status ESPN":"Brak wpisu w ESPN",
             "Próba występów":7},
        ])

    def test_catalog_lists_missing_player_without_fabricated_numbers(self):
        merged,meta=roster_projection_table(self.roster,self.forecasts,"GSW")
        self.assertEqual(len(merged),2)
        curry=merged[merged["Zawodnik"]=="Stephen Curry"].iloc[0]
        missing=merged[merged["Zawodnik"]=="A Player Without Recent Games"].iloc[0]
        self.assertAlmostEqual(float(curry["PTS"]),26.3)
        self.assertTrue(pd.isna(missing["PTS"]))
        self.assertTrue(pd.isna(missing["AST"]))
        self.assertTrue(pd.isna(missing["Minuty"]))
        self.assertEqual(meta["projected"],1)
        self.assertEqual(meta["missing"],1)

    def test_does_not_show_old_team_forecasts_as_current(self):
        merged,meta=roster_projection_table(self.roster,self.forecasts,"GSW")
        self.assertEqual(meta["not_on_roster"],1)
        self.assertNotIn("Former Player",merged["Zawodnik"].tolist())

    def test_roster_not_available_uses_only_real_forecasts(self):
        result,meta=roster_projection_table(pd.DataFrame(),self.forecasts,"GSW")
        self.assertFalse(meta["roster_available"])
        self.assertEqual(len(result),2)

    def test_wrong_team_forecasts_not_joined(self):
        other=self.forecasts.copy()
        other["Drużyna"]="BOS"
        merged,meta=roster_projection_table(self.roster,other,"GSW")
        self.assertEqual(meta["projected"],0)
        self.assertEqual(meta["missing"],2)


if __name__=="__main__":
    unittest.main()
