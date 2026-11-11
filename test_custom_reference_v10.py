"""BestBets v10: public canvas contract and backend preservation."""
import re
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parent
HTML=ROOT/"bestbets_reference_frontend"/"index.html"

class CustomReferenceTests(unittest.TestCase):
    def test_new_entrypoint_preserves_old_sources(self):
        entry=(ROOT/"app.py").read_text(encoding="utf-8")
        self.assertIn("from bestbets_custom_screen import main",entry)
        for file in ("mvp_prop_ui.py","mvp_app.py","mvp_player_card.py",
                     "season_props.py","simulation_engine.py","simulation_sources.py",
                     "sources.py","espn_player_data.py"):
            self.assertTrue((ROOT/file).is_file(),file)

    def test_server_reuses_verified_nba_history(self):
        backend=(ROOT/"bestbets_custom_screen.py").read_text(encoding="utf-8")
        for token in (
            "parse_prop_batch(query.strip(), max_items=1)",
            "_match_proposals(parsed, catalog)",
            "_run_research(",
            "clean_player_season(raw, name, SEASON, asof, player_id or None)",
            "normalize_logs(logs)",
            "logo_data_uri(team)",
            "defense_recent",
            "st.rerun()",
            "declare_component(",
        ):
            self.assertIn(token,backend,token)
        self.assertIn('if quality != "exact":',backend)

    def test_custom_canvas_has_all_fixed_reference_sections(self):
        markup=HTML.read_text(encoding="utf-8")
        self.assertIn("width:1231px;height:691px",markup)
        for element in ("search-form","hero","market","line","chart-panel",
                        "chart-svg","side-stats","take","footer"):
            self.assertIn('id="'+element+'"',markup,element)
        for page in ("home","simulations","games","players","teams","shortcuts"):
            self.assertIn('id="card-'+page+'"',markup)
            self.assertIn('data-page="'+page+'"',markup)
        self.assertIn("streamlit:componentReady",markup)
        self.assertIn("streamlit:setComponentValue",markup)
        self.assertIn("streamlit:render",markup)

    def test_data_is_dynamic_and_reduced_motion_supported(self):
        markup=HTML.read_text(encoding="utf-8")
        for token in ("p.games.filter","rate(values.slice(-n))",
                      "chartMarkup(rows)","p.defense","p.defense_recent",
                      "prefers-reduced-motion:reduce",
                      "data-market=\"PRA\"","data-period=\"L10\""):
            self.assertIn(token,markup,token)
        self.assertNotIn("71.3%",markup)
        self.assertNotIn("A-</",markup)
        self.assertNotIn("69 : 54",markup)

if __name__=="__main__":
    unittest.main()
