"""UI regression tests: remove only redundant Center KPI cards, not real features."""
from pathlib import Path
import unittest

import pandas as pd

from center_leaderboard import player_card_html, stat_text


class CenterRedesignTests(unittest.TestCase):
    def test_numbered_stat_cards(self):
        html=player_card_html({"PLAYER_NAME":"Luka Dončić","TEAM_ABBREVIATION":"LAL",
                               "PTS":53,"REB":5,"AST":5},1)
        self.assertIn("#01",html)
        self.assertIn("Luka Dončić",html)
        self.assertIn("LAL",html)
        self.assertIn("53",html)
        self.assertIn("5",html)
        self.assertIn("PUNKTY",html)
        self.assertIn("ZBIÓRKI",html)
        self.assertIn("ASYSTY",html)
        self.assertIn("medal1",html)

    def test_missing_stats_not_replaced_with_zero(self):
        self.assertEqual(stat_text(None),"—")
        self.assertEqual(stat_text(float("nan")),"—")
        self.assertEqual(stat_text(30.0),"30")
        self.assertEqual(stat_text(15.5),"15.5")

    def test_sanitizes_external_names(self):
        html=player_card_html({"PLAYER_NAME":"<img src=x onerror=alert(1)>",
                               "TEAM_ABBREVIATION":"BOS","PTS":28,"REB":9,"AST":6},3)
        self.assertNotIn("<img src=x onerror=",html)
        self.assertIn("&lt;img src=x",html)
        self.assertIn("#03",html)

    def test_center_keeps_schedule_and_injury(self):
        app=Path("app.py").read_text(encoding="utf-8")
        start=app.index("if page == '🏠 Centrum':")
        end=app.index("elif page == '📆 Terminarz':", start)
        center=app[start:end]
        self.assertIn('st.markdown("#### Terminarz dnia")',center)
        self.assertIn('day_navigation("center", zone)',center)
        self.assertIn("display_cards(chosen, zone, compact=True)",center)
        self.assertIn("st.markdown('#### Injury report')",center)
        self.assertIn("show_top10(top)",center)
        self.assertNotIn("c1,c2,c3,c4=st.columns(4)",center)
        self.assertNotIn("labelled_metric(",center)
        self.assertNotIn("st.dataframe(top.rename",center)


if __name__=="__main__":
    unittest.main()
