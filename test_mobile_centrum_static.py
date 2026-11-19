"""Static regression checks for the first mobile HOOPZARO Centrum iteration.

Full browser QA is still required in a device/browser-capable environment.
"""
from pathlib import Path
import re
import unittest


FRONTEND = Path(__file__).resolve().parent / "bestbets_reference_frontend"
HTML = (FRONTEND / "index.html").read_text(encoding="utf-8")
CSS = (FRONTEND / "mobile.css").read_text(encoding="utf-8")
CENTRE_JS = (FRONTEND / "centrum.js").read_text(encoding="utf-8")


class MobileCentrumStaticTests(unittest.TestCase):
    def test_desktop_canvas_and_legacy_scaling_remain(self):
        self.assertIn("#app-shell{width:1231px", HTML)
        self.assertIn("#stage{width:1231px;height:691px", HTML)
        self.assertIn("const scale=viewportWidth/1231;", HTML)
        self.assertIn('root.style.transform="scale("+scale+")";', HTML)

    def test_mobile_fluid_mode_and_orientation(self):
        self.assertIn("viewportWidth<=767", HTML)
        self.assertIn("viewportWidth<=1200 && window.innerHeight<=500", HTML)
        self.assertIn('root.style.transform="none";', HTML)
        self.assertIn('shell.style.width="100%";', HTML)
        self.assertIn('shell.style.height="auto";', HTML)
        self.assertIn("#stage.bb-home-active #bestbets-centre", CSS)
        self.assertIn("flex-direction:column", CSS)
        self.assertRegex(CSS, r"@media\s*\(min-width:768px\).*max-height:500px")
        self.assertIn("orientation:landscape", CSS)

    def test_mobile_navigation_and_more_menu_use_existing_routes(self):
        self.assertIn('id="hz-mobile-nav"', HTML)
        for route in ("home", "props", "games", "simulations",
                      "players", "teams", "settings", "admin"):
            self.assertIn(f'data-page="{route}"', HTML)
        self.assertIn('id="hz-mobile-more-trigger"', HTML)
        self.assertIn('id="hz-mobile-more-panel"', HTML)
        self.assertIn('closeMobileMore()', HTML)
        self.assertIn("position:fixed", CSS)

    def test_live_centre_data_and_day_actions_are_reused(self):
        self.assertIn('id="bc-games-list"', HTML)
        self.assertIn('id="bc-ticker-games"', HTML)
        self.assertIn('id="bc-injury-watch"', HTML)
        self.assertIn('id="hz-mobile-day-label"', HTML)
        self.assertIn('data-centre-day-dir="-1"', HTML)
        self.assertIn('data-centre-day-dir="1"', HTML)
        self.assertIn('mobileDateLabel.textContent', CENTRE_JS)
        self.assertIn("changeDay(Number(dayDirection))", CENTRE_JS)
        self.assertIn("window.BestBetsCentre.render", HTML)

    def test_stylesheet_loaded_after_desktop_styles(self):
        self.assertLess(HTML.index('href="teams.css"'),
                        HTML.index('href="mobile.css"'))
        self.assertRegex(CSS, r"@media\s*\(max-width:767px\)")
        self.assertIn("#bestbets-centre .bc-bottom{display:none!important}", CSS)

    def test_team_icons_have_offline_fallbacks(self):
        self.assertIn('bc-team-monogram', CENTRE_JS)
        self.assertIn('data:image/png;base64,', CENTRE_JS)
        self.assertIn(".bc-team-monogram", (FRONTEND / "centrum.css").read_text(encoding="utf-8"))

    def test_mobile_team_record_has_full_two_line_grid(self):
        self.assertIn("grid-template-columns:32px 48px minmax(0,1fr) 34px", CSS)
        self.assertIn("grid-column:3;grid-row:1;font-size:13px;text-align:left", CSS)
        self.assertIn("grid-column:3;grid-row:2;font-size:11px;text-align:left", CSS)


if __name__ == "__main__":
    unittest.main()
