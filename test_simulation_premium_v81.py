"""UI regressions for colorful but strictly data-backed BestBets NBA matchups."""
from pathlib import Path
import unittest
import pandas as pd

from simulation_premium_ui import (
    matchup_card_html,detail_hero_html,show_number,
)

SIM={
    "home":"NYK","away":"MIL",
    "home_points":117.6,"away_points":109.0,
    "total_points":226.6,"home_win_pct":71.3,
    "away_win_pct":28.7,"winner":"NYK",
    "total_p10":201.,"total_p90":252.,
}


def mocked_logo(team):
    return '<span class="logo">'+team+'</span>'


class SimulationPremiumUiTests(unittest.TestCase):
    def test_horizontal_card_has_real_scores_and_probability(self):
        raw=matchup_card_html(
            SIM,"11.11.2026 · 01:30",mocked_logo,
            {"MIL":"Milwaukee Bucks","NYK":"New York Knicks"})
        for needle in ("bbm-sim-game-grid","bbm-sim-matchup",
                       "bbm-sim-winbar","Milwaukee Bucks","New York Knicks",
                       "109.0","117.6","226.6","28.7%","71.3%",
                       "5,000 SIMULATIONS"):
            self.assertIn(needle,raw,needle)
        self.assertIn('width:28.70%',raw)
        self.assertIn('width:71.30%',raw)
        self.assertNotIn("100.0% win probability",raw)

    def test_detail_hero_promotes_team_comparison_without_black_table(self):
        raw=detail_hero_html(
            SIM,mocked_logo,{"MIL":"Milwaukee Bucks","NYK":"New York Knicks"})
        for needle in ("bbm-sim-detail-hero","bbm-sim-detail-match",
                       "PROJECTED SCORE","Milwaukee Bucks","New York Knicks",
                       "109.0","117.6","28.7%","71.3%"):
            self.assertIn(needle,raw,needle)
        self.assertNotIn("<table",raw.lower())

    def test_untrusted_team_strings_are_escaped(self):
        raw=matchup_card_html(
            SIM,"<img src=x onerror=alert(1)>",mocked_logo,
            {"MIL":"<script>alert(1)</script>","NYK":"NYK"})
        self.assertNotIn("<script>",raw)
        self.assertIn("&lt;script&gt;",raw)
        self.assertNotIn('<img src=x onerror=alert(1)>',raw)

    def test_incomplete_metrics_not_fabricated(self):
        self.assertEqual(show_number(None),"—")
        self.assertEqual(show_number(float("nan")),"—")
        self.assertEqual(show_number(float("inf")),"—")
        self.assertEqual(show_number(226.65,1," pkt"),"226.7 pkt")

    def test_source_analytics_unchanged_and_research_separate(self):
        src=Path("simulation_view.py").read_text(encoding="utf8")
        self.assertIn("def build_sims(",src)
        self.assertIn("simulate_game(g,mean,h,a)",src)
        self.assertIn("render_matchup_overview(",src)
        self.assertIn("render_model_audit(",src)
        self.assertIn("render_injuries(",src)
        self.assertIn("rotation_report(",src)
        self.assertIn("if view == '🎯 Linie i wrażliwość':",src)
        self.assertIn("if view == '📊 Rozkład punktów':",src)
        self.assertNotIn("'💹 Kursy bukmacherów'",src)

    def test_vertical_text_no_longer_forced_onto_primary_dialog(self):
        src=Path("simulation_view.py").read_text(encoding="utf8")
        first=src.index("def show_game_details(")
        ending=src.index("if view=='🏟️ Przegląd':",first)
        top=src[first:ending]
        self.assertIn("bbm-sim-kpis",top)
        self.assertNotIn("st.dataframe(",top)
        self.assertNotIn("matchup_audit(",top)
        self.assertNotIn("st.caption('Źródło modelu",top)

    def test_mobile_dialog_colors_and_compact_cards(self):
        theme=Path("mvp_theme.py").read_text(encoding="utf8")
        for name in (
            ".bbm-sim-game-grid",".bbm-sim-matchup",".bbm-sim-kpis",
            ".bbm-sim-form-card",".bbm-sim-injury",
            ".bbm-sim-detail-hero","div[data-testid=\"stDialog\"]",
            "@media(max-width:640px)"):
            self.assertIn(name,theme,name)


if __name__=="__main__":
    unittest.main()
