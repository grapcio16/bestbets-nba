"""Static-browser checks for the licensed-logo-free HOOPZARO team directory."""
from pathlib import Path
from shutil import which
import unittest

from playwright.sync_api import Error as PlaywrightError, sync_playwright


PAGE = (Path(__file__).resolve().parent / "bestbets_reference_frontend" / "index.html").as_uri()


class TeamsDirectoryBrowserTests(unittest.TestCase):
    def test_free_premium_filters_and_favorites(self):
        with sync_playwright() as pw:
            executable = which("chromium") or which("google-chrome")
            if not executable:
                self.skipTest("No Chromium binary installed for browser QA")
            try:
                browser = pw.chromium.launch(headless=True, executable_path=executable,
                                             args=["--no-sandbox"])
            except PlaywrightError as exc:
                if "Operation not permitted" in str(exc):
                    self.skipTest("Local sandbox blocks Chromium; CI has browser QA")
                raise
            page = browser.new_page(viewport={"width": 1231, "height": 691})
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(PAGE, wait_until="load")
            page.locator('.nav-btn[data-page="teams"]').click()
            self.assertTrue(page.locator("#hzt-teams-pane").is_visible())
            self.assertTrue(page.locator("#blank-pane").is_hidden())
            # Three rows fit the space freed by moving Premium details into a dialog.
            self.assertEqual(page.locator(".hzt-team-card").count(), 9)
            self.assertEqual(page.locator("#hzt-team-grid img").count(), 0)
            self.assertTrue(page.locator("#hzt-modal-backdrop").is_hidden())
            payload = {"auth": {"role": "free"}, "home": {"form_period": "2026/27",
                "form_available": True, "form_options": [
                    {"team": "BOS", "wins": 11, "losses": 4, "record_verified": True},
                    {"team": "GSW", "wins": 14, "losses": 2, "record_verified": False}]}}
            page.evaluate("payload => window.postMessage({type:'streamlit:render',args:{payload}}, '*')", payload)
            self.assertIn("11–4", page.locator('[data-hzt-team="BOS"]').inner_text())
            self.assertNotIn("14–2", page.locator('[data-hzt-team="GSW"]').inner_text())
            page.locator('[data-hzt-team="BOS"] [data-hzt-fav]').click()
            self.assertTrue(page.locator("#hzt-modal-backdrop").is_hidden())
            self.assertEqual(page.locator('[data-hzt-team="BOS"] [data-hzt-fav]').get_attribute("aria-pressed"), "true")
            page.locator('[data-hzt-team="GSW"] [data-hzt-fav]').click()
            page.locator('[data-hzt-team="NYK"] [data-hzt-fav]').click()
            self.assertIn("Maksymalnie 2", page.locator("#hzt-team-message").inner_text())
            favs = page.evaluate("JSON.parse(localStorage.getItem('bestbets.centrum.favoriteTeams.v1'))")
            self.assertEqual(favs, ["BOS", "GSW"])
            page.locator('[data-hzt-conference="west"]').click()
            self.assertNotIn("BOS", page.locator("#hzt-team-grid").inner_text())
            page.locator("#hzt-search").fill("Denver")
            self.assertEqual(page.locator(".hzt-team-card").count(), 1)
            page.locator("#hzt-search").fill("")
            page.locator('[data-hzt-conference="all"]').click()
            page.locator('[data-hzt-team="BOS"]').click()
            self.assertTrue(page.locator("#hzt-team-dialog").is_visible())
            self.assertEqual(page.locator("#hzt-modal-name").inner_text(), "Boston Celtics")
            self.assertEqual(page.locator("#hzt-modal-record").inner_text(), "11–4")
            self.assertTrue(page.locator("#hzt-premium-locked").is_visible())
            self.assertTrue(page.locator("#hzt-premium-unlocked").is_hidden())
            self.assertIn("blur(", page.locator("#hzt-modal-backdrop").evaluate(
                "element => getComputedStyle(element).backdropFilter"))
            page.locator("#hzt-premium-cta").click()
            self.assertTrue(page.locator("#hz-paywall-dialog").is_visible())
            page.locator("#hz-paywall-close").click()
            self.assertTrue(page.locator("#hzt-team-dialog").is_visible())
            self.assertEqual(page.evaluate("document.activeElement.id"), "hzt-modal-close")
            page.keyboard.press("Escape")
            self.assertTrue(page.locator("#hzt-modal-backdrop").is_hidden())
            self.assertEqual(page.evaluate("document.activeElement.dataset.hztTeam"), "BOS")
            page.locator('[data-hzt-team="GSW"]').focus()
            page.keyboard.press("Enter")
            self.assertEqual(page.locator("#hzt-modal-name").inner_text(), "Golden State Warriors")
            page.locator("#hzt-modal-backdrop").click(position={"x": 6, "y": 6})
            self.assertTrue(page.locator("#hzt-modal-backdrop").is_hidden())
            # NBA Advanced can reject cloud hosting. The three requested
            # ratings remain visible and load from finished-game boxscores.
            fallback_payload = {**payload, "auth": {"role": "premium"},
                "premium_team_analytics": {"teams": {"BOS": {"sample": 10,
                    "points": 110.4, "allowed": 99.3, "home": 121.6,
                    "away": 112.1, "last5": "WWLWL", "off": None,
                    "def": None, "pace": None}, "GSW": {"sample": 10,
                    "points": 116.5, "allowed": 111.0, "home": 120.1,
                    "away": 113.3, "last5": "WLWWW"}}}}
            page.evaluate("payload => window.postMessage({type:'streamlit:render',args:{payload}}, '*')",
                          fallback_payload)
            page.locator('[data-hzt-team="BOS"]').click()
            metrics = page.locator("#hzt-premium-metrics")
            self.assertEqual(page.locator(".hzt-metric").count(), 5)
            self.assertIn("OFF RATING", metrics.inner_text())
            self.assertIn("DEF RATING", metrics.inner_text())
            self.assertIn("PACE", metrics.inner_text())
            self.assertNotIn("FORMA L5", metrics.inner_text())
            self.assertIn("Pobieranie", metrics.inner_text())
            estimated_payload = {**payload, "auth": {"role": "premium"},
                "premium_team_analytics": {"teams": {"BOS": {"sample": 10,
                    "points": 110.4, "allowed": 99.3,
                    "off": 116.9, "def": 105.1, "pace": 99.7,
                    "rating_sample": 10, "rating_estimated": True,
                    "rating_attempted": True,
                    "rating_source": "ESPN — szacunek z boxscore"},
                    "GSW": {"sample": 10, "points": 116.5, "allowed": 111.0,
                    "off": 115.2, "def": 110.3, "pace": 101.4,
                    "rating_sample": 10, "rating_estimated": True,
                    "rating_attempted": True,
                    "rating_source": "ESPN — szacunek z boxscore"}}}}
            page.evaluate("payload => window.postMessage({type:'streamlit:render',args:{payload}}, '*')",
                          estimated_payload)
            self.assertIn("116,9", metrics.inner_text())
            self.assertIn("105,1", metrics.inner_text())
            self.assertIn("99,7", metrics.inner_text())
            self.assertIn("szacunek", page.locator("#hzt-analytics-source").inner_text())
            page.locator("#hzt-compare").select_option("GSW")
            self.assertIn("115,2", metrics.inner_text())
            page.locator("#hzt-modal-close").click()
            premium_payload = {**payload, "auth": {"role": "premium"},
                "premium_team_analytics": {"teams": {"BOS": {"sample": 10, "points": 113.3,
                    "allowed": 107.4, "off": 115.2, "def": 108.9, "pace": 100.3,
                    "rating_source": "NBA Stats — advanced",
                    "home": 116.5, "away": 109.2}, "GSW": {"sample": 10,
                    "points": 119.8, "allowed": 110.1, "off": 120.9,
                    "def": 111.5, "pace": 102.5, "rating_source": "NBA Stats — advanced",
                    "home": 123.1, "away": 116.6}}}}
            page.evaluate("payload => window.postMessage({type:'streamlit:render',args:{payload}}, '*')",
                          premium_payload)
            self.assertTrue(page.locator("#hzt-modal-backdrop").is_hidden())
            page.locator('[data-hzt-team="BOS"]').click()
            page.locator("#hzt-premium-unlocked").wait_for(state="visible", timeout=10000)
            self.assertTrue(page.locator("#hzt-premium-unlocked").is_visible())
            self.assertTrue(page.locator("#hzt-premium-cta").is_hidden())
            self.assertEqual(page.locator(".hzt-metric").count(), 5)
            self.assertIn("OFF RATING", page.locator("#hzt-premium-metrics").inner_text())
            self.assertIn("DEF RATING", page.locator("#hzt-premium-metrics").inner_text())
            self.assertIn("PACE", page.locator("#hzt-premium-metrics").inner_text())
            self.assertIn("115,2", page.locator("#hzt-premium-metrics").inner_text())
            self.assertIn("113,3", page.locator("#hzt-premium-metrics").inner_text())
            page.locator("#hzt-compare").select_option("GSW")
            self.assertIn("119,8", page.locator("#hzt-premium-metrics").inner_text())
            page.locator("#hzt-modal-close").click()
            self.assertTrue(page.locator("#hzt-modal-backdrop").is_hidden())
            page.locator('[data-hzt-team="GSW"]').click()
            self.assertEqual(page.locator("#hzt-modal-name").inner_text(), "Golden State Warriors")
            self.assertIn("119,8", page.locator("#hzt-premium-metrics").inner_text())
            page.locator("#hzt-modal-close").click()
            self.assertFalse(errors, errors)
            browser.close()


if __name__ == "__main__":
    unittest.main()
