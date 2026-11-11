"""BestBets v8.5 regression contract for the approved visual reference."""
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parent

class ReferenceV85Tests(unittest.TestCase):
    def test_fidelity_layer_is_applied_after_previous_theme(self):
        app=(ROOT/"mvp_app.py").read_text("utf8")
        self.assertIn("from mvp_fidelity_theme import apply_fidelity_theme",app)
        self.assertLess(app.index("    apply_pixel_theme()"),app.index("    apply_fidelity_theme()"))
        self.assertLess(app.index("    apply_fidelity_theme()"),app.index("    _sidebar()"))

    def test_all_six_bottom_modules_are_persistent(self):
        footer=(ROOT/"mvp_reference_footer.py").read_text("utf8")
        for route in ("home","simulations","games","players","teams"):
            self.assertIn(f'("{route}"',footer)
            self.assertIn(f"bb83_footer_{{route}}",footer)
        self.assertIn("bb83_footer_shortcut",footer)
        self.assertIn("on_click=on_navigate,args=(route,)",footer)
        self.assertIn("with st.container(border=True)",footer)
        for name in ("PTS","REB","AST","3PM","PRA"):
            self.assertIn(f'("{name}"',footer)

    def test_responsive_reference_sections(self):
        style=(ROOT/"mvp_fidelity_theme.py").read_text("utf8")
        for fragment in (
            "@media(min-width:1650px)",".bb85-preview",".bb85-shortcut-panel",
            ".bb85-sim-versus",".bb85-team-row",".bb85-person-row",
            ".bb83-hero",".bb83-portrait",".bb83-rate-card",
            ".bb83-take",".st-key-bb83-footer",":is(#bb85-force",
        ):
            self.assertIn(fragment,style)

    def test_plot_uses_real_observed_game_values(self):
        card=(ROOT/"mvp_player_card.py").read_text("utf8")
        self.assertIn("observed_hit_rates(games,market,line)",card)
        self.assertIn("actual=[float(x) for x in values]",card)
        self.assertIn("height=465,bargap=.22",card)
        self.assertNotIn("MATCHUP GRADE</small>\n        <b>A+",card)

if __name__=="__main__":
    unittest.main()
