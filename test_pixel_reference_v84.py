"""BestBets v8.4 visual reset contract, no fake NBA data."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parent

class PixelReferenceResetTests(unittest.TestCase):
    def test_new_theme_is_loaded_after_existing_styles(self):
        app = (ROOT / "mvp_app.py").read_text(encoding="utf8")
        self.assertIn("from mvp_pixel_theme import apply_pixel_theme", app)
        self.assertLess(app.index("    apply_reference_theme()"), app.index("    apply_pixel_theme()"))
        self.assertLess(app.index("    apply_pixel_theme()"), app.index("    _sidebar()"))

    def test_visual_sections_and_mobile_breakpoints(self):
        css = (ROOT / "mvp_pixel_theme.py").read_text(encoding="utf8")
        for token in (
            ".st-key-bb83_search", ".st-key-bb83-suggest", ".bb83-hero",
            ".bb83-portrait", ".bb83-hero-metric", ".bb83-grade",
            ".st-key-bb83-controls", ".st-key-bb83-research",
            ".bb83-rate-grid", ".bb83-defense", ".bb83-take",
            ".st-key-bb83-footer", "@media(max-width:620px)",
            "@media(max-width:900px)", "@media(max-width:1450px)"
        ):
            self.assertIn(token, css, token)

    def test_screen_keeps_live_data_instead_of_mock_values(self):
        ui = (ROOT / "mvp_player_card.py").read_text(encoding="utf8")
        self.assertIn("observed_hit_rates(games,market,line)", ui)
        self.assertIn("_plot(selected,market,line)", ui)
        self.assertIn("_headline_html(", ui)
        self.assertIn("_stats_panel(rates,home_avg,away_avg", ui)
        self.assertIn("_take_html(name,market,float(line),side,all_)", ui)

if __name__ == "__main__":
    unittest.main()
