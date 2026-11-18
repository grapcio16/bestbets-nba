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
            self.assertEqual(page.locator(".hzt-team-card").count(), 6)
            self.assertEqual(page.locator("#hzt-team-grid img").count(), 0)
            payload = {"auth": {"role": "free"}, "home": {"form_period": "2026/27",
                "form_available": True, "form_options": [
                    {"team": "BOS", "wins": 11, "losses": 4, "record_verified": True},
                    {"team": "GSW", "wins": 14, "losses": 2, "record_verified": False}]}}
            page.evaluate("payload => window.postMessage({type:'streamlit:render',args:{payload}}, '*')", payload)
            self.assertIn("11–4", page.locator('[data-hzt-team="BOS"]').inner_text())
            self.assertNotIn("14–2", page.locator('[data-hzt-team="GSW"]').inner_text())
            page.locator('[data-hzt-team="BOS"] [data-hzt-fav]').click()
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
            page.locator("#hzt-premium-cta").click()
            self.assertTrue(page.locator("#hz-paywall-dialog").is_visible())
            page.locator("#hz-paywall-close").click()
            premium_payload = {**payload, "auth": {"role": "premium"},
                "premium_team_analytics": {"teams": {"BOS": {"sample": 10, "points": 113.3,
                    "allowed": 107.4, "off": 115.2, "def": 108.9, "pace": 100.3,
                    "home": 116.5, "away": 109.2}}}}
            page.evaluate("payload => window.postMessage({type:'streamlit:render',args:{payload}}, '*')",
                          premium_payload)
            self.assertTrue(page.locator("#hzt-premium-unlocked").is_visible())
            self.assertTrue(page.locator("#hzt-premium-cta").is_hidden())
            self.assertEqual(page.locator(".hzt-metric").count(), 5)
            self.assertFalse(errors, errors)
            browser.close()


if __name__ == "__main__":
    unittest.main()
