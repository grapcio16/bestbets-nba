"""BestBets 9.1 regression contract: motion and reference fidelity, real data preserved."""
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parent

class NeonReferenceTests(unittest.TestCase):
    def test_live_shell_loads_fx_last(self):
        shell=(ROOT/"bestbets_v90.py").read_text(encoding="utf8")
        self.assertIn("from bestbets_v91_fx import apply_reference_fx",shell)
        self.assertLess(shell.index("    apply_reference_theme()"),shell.index("    apply_v90_theme()"))
        self.assertLess(shell.index("    apply_v90_theme()"),shell.index("    apply_reference_fx()"))
        self.assertIn('"bb91_bootstrapped"',shell)
        self.assertIn('st.session_state["bb90_page"]="props"',shell)

    def test_six_preview_navigation_paths_remain_functional(self):
        shell=(ROOT/"bestbets_v90.py").read_text(encoding="utf8")
        for route in ("home","simulations","games","players","teams","shortcuts"):
            self.assertIn('"'+route+'"',shell)
        self.assertIn('on_click=_route,args=(key,)',shell)
        self.assertIn('with st.container(border=True):',shell)

    def test_glow_animations_reduced_motion_and_color_palette(self):
        css=(ROOT/"bestbets_v91_fx.py").read_text(encoding="utf8")
        for token in (
            "bb91-search-breathe","bb91-orange-breathe",
            "bb91-blue-breathe","bb91-take-shine",
            "prefers-reduced-motion:reduce",
            ".bb83-hero",".bb83-rate-card",
            ".st-key-bb83_search",".st-key-bb90-footer",
            "#ff7a1c","#00baff","#04ec74","#ff514a",
        ):
            self.assertIn(token,css,token)

    def test_real_statistics_and_compact_history_plot_remain(self):
        shell=(ROOT/"bestbets_v90.py").read_text(encoding="utf8")
        card=(ROOT/"mvp_player_card.py").read_text(encoding="utf8")
        self.assertIn("from mvp_prop_ui import render_player_props",shell)
        self.assertIn("get_schedule,load_logs,show_empty=False",shell)
        self.assertIn("observed_hit_rates(games,market,line)",card)
        self.assertIn("height=415,bargap=.20",card)
        for name in ("sources.py","season_props.py","simulation_sources.py"):
            self.assertTrue((ROOT/name).is_file(),name)

if __name__=="__main__":
    unittest.main()
