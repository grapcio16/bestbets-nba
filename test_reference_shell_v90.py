"""BestBets v9 public-shell acceptance tests: UI reset without deleting data."""
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parent

class ScreenshotFirstShellTests(unittest.TestCase):
    def test_public_entry_starts_new_workspace(self):
        entry=(ROOT/"app.py").read_text("utf8")
        self.assertIn("from bestbets_custom_screen import main",entry)
        self.assertNotIn("from mvp_app import main",entry)

    def test_existing_stats_models_and_sources_are_retained(self):
        for name in ("season_props.py","sources.py","mvp_app.py",
                     "mvp_player_card.py","mvp_prop_ui.py",
                     "simulation_sources.py","simulation_view.py"):
            self.assertTrue((ROOT/name).is_file(),name)
        shell=(ROOT/"bestbets_v90.py").read_text("utf8")
        self.assertIn("from mvp_prop_ui import render_player_props",shell)
        self.assertIn("from core import normalize_logs",shell)
        self.assertIn("get_logs(SEASON",shell)
        self.assertIn("get_schedule,load_logs,show_empty=False",shell)

    def test_blank_initial_search_and_six_functioning_navigation_routes(self):
        shell=(ROOT/"bestbets_v90.py").read_text("utf8")
        for page in ("home","simulations","games","players","teams","shortcuts"):
            self.assertIn('"'+page+'"',shell)
            self.assertIn('bb90_footer_',shell)
        self.assertIn('st.session_state["bb90_page"]="props"',shell)
        self.assertIn("def _empty_canvas():",shell)
        self.assertIn("def _blank_page():",shell)
        self.assertIn("on_click=_route,args=(key,)",shell)
        self.assertIn("with st.container(border=True):",shell)

    def test_visual_identity_preserved(self):
        css=(ROOT/"bestbets_v90_theme.py").read_text("utf8")
        for thing in ("#ff791d","#00baff","#05ec78","#ff514c",
                      ".bb90-empty-hero",".bb90-mini-card",
                      ".st-key-bb83_search",".bb83-hero",
                      ".bb90-empty-grid",".bb90-empty-take",
                      "@media(max-width:650px)"):
            self.assertIn(thing,css)

    def test_previous_placeholder_can_be_disabled(self):
        old=(ROOT/"mvp_prop_ui.py").read_text("utf8")
        self.assertIn("show_empty=True",old)
        self.assertIn("if not submitted and show_empty:",old)

if __name__=="__main__":
    unittest.main()
