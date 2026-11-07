"""Offline checks of global player search and calculator history charts."""
import unittest
from unittest.mock import patch
import pandas as pd
from global_player_catalog import build_global_catalog
from roster_view import show_calculator_history_chart


class GlobalCatalogTests(unittest.TestCase):
    def test_automatic_team_and_id_for_players(self):
        def fake_team(team):
            if team=="GSW":
                return pd.DataFrame([{
                    "PLAYER_ID":"3975","PLAYER_NAME":"Stephen Curry",
                    "TEAM_ABBREVIATION":"GSW","POSITION":"PG","ROSTER_STATUS":"?"
                }]),{"stale":False}
            if team=="DEN":
                return pd.DataFrame([{
                    "PLAYER_ID":"2017","PLAYER_NAME":"Aaron Gordon",
                    "TEAM_ABBREVIATION":"DEN","POSITION":"PF","ROSTER_STATUS":"?"
                }]),{"stale":False}
            return pd.DataFrame([{
                "PLAYER_ID":"dummy_"+team,"PLAYER_NAME":"Test "+team,
                "TEAM_ABBREVIATION":team,"POSITION":"?", "ROSTER_STATUS":"?"
            }]),{"stale":False}
        catalog,coverage=build_global_catalog(fake_team)
        self.assertEqual(coverage["teams_loaded"],30)
        self.assertEqual(coverage["missing_teams"],[])
        self.assertIn("Aaron Gordon",catalog["PLAYER_NAME"].tolist())
        self.assertEqual(catalog.loc[catalog["PLAYER_NAME"]=="Aaron Gordon",
                                      "TEAM_ABBREVIATION"].iloc[0],"DEN")
        self.assertIn("Stephen Curry",catalog["PLAYER_NAME"].tolist())

    def test_failed_roster_is_reported_not_silent(self):
        def fake_team(team):
            if team=="DEN":
                raise RuntimeError("ESPN error")
            return pd.DataFrame([{
                "PLAYER_ID":team,"PLAYER_NAME":team,"TEAM_ABBREVIATION":team,
                "POSITION":"?","ROSTER_STATUS":"?"
            }]),{"stale":False}
        catalog,coverage=build_global_catalog(fake_team)
        self.assertEqual(coverage["teams_loaded"],29)
        self.assertEqual(coverage["missing_teams"],["DEN"])
        self.assertEqual(len(catalog),29)

    def test_history_chart_has_game_values_and_both_reference_lines(self):
        sample=pd.DataFrame([
            {"GAME_DATE":pd.Timestamp("2026-11-02",tz="UTC"),"MATCHUP":"DEN vs. UTA","PTS":11},
            {"GAME_DATE":pd.Timestamp("2026-11-03",tz="UTC"),"MATCHUP":"DEN @ GSW","PTS":22},
        ])
        with patch("roster_view.st.plotly_chart") as plot,patch("roster_view.st.caption"):
            show_calculator_history_chart(sample,"Aaron Gordon","PTS",15.5,18.)
        self.assertEqual(plot.call_count,1)
        fig=plot.call_args.args[0]
        self.assertEqual(list(fig.data[0].y),[11,22])
        self.assertEqual(len(fig.layout.shapes),2)

    def test_history_chart_missing_logs_does_not_invent_points(self):
        with patch("roster_view.st.plotly_chart") as plot,patch("roster_view.st.info") as msg:
            show_calculator_history_chart(pd.DataFrame(),"Aaron Gordon","PTS",15.5)
        plot.assert_not_called()
        msg.assert_called_once()


if __name__=="__main__":
    unittest.main()
