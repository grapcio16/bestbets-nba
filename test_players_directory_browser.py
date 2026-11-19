"""Headless browser checks for the paid player directory and licensed-safe avatars.

All numerical fixtures stay in this test; production never fabricates stats.
"""
from pathlib import Path
from shutil import which
import unittest

from playwright.sync_api import Error as PlaywrightError, sync_playwright


PAGE = (Path(__file__).resolve().parent / "bestbets_reference_frontend" / "index.html").as_uri()


class PlayersDirectoryBrowserTests(unittest.TestCase):
    def test_free_teaser_and_premium_view(self):
        with sync_playwright() as pw:
            executable = which("chromium") or which("google-chrome")
            if not executable:
                self.skipTest("No Chromium binary installed for browser QA")
            try:
                browser = pw.chromium.launch(
                    headless=True, executable_path=executable, args=["--no-sandbox"])
            except PlaywrightError as exc:
                if "Operation not permitted" in str(exc):
                    self.skipTest("Sandbox blocks Chromium sockets; browser QA requires CI")
                raise
            page = browser.new_page(viewport={"width": 1231, "height": 691})
            errors, requests = [], []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.on("request", lambda request: requests.append(request.url))
            page.goto(PAGE, wait_until="load")
            page.evaluate("""() => {
              window.__premiumRequests = [];
              window.addEventListener('message', e => {
                if(e.data?.type === 'streamlit:setComponentValue' &&
                   e.data?.value?.type === 'premium_player_averages') {
                  window.__premiumRequests.push(e.data.value);
                }
              });
            }""")
            page.locator('.nav-btn[data-page="players"]').click()
            self.assertTrue(page.locator("#hzp-players-pane").is_visible())
            self.assertTrue(page.locator("#blank-pane").is_hidden())
            self.assertTrue(page.locator("#footer").is_hidden())
            # The Spotlight has an honest loading profile immediately on entry;
            # it must never be a blank dark rectangle before ESPN responds.
            self.assertIn("Jayson Tatum", page.locator("#hzp-spotlight-body").inner_text())
            self.assertIn("Trwa pobieranie", page.locator("#hzp-spotlight-body").inner_text())
            rows = [{"id": str(i), "name": name, "team": "BOS" if i % 2 else "DEN",
                     "position": "SF" if i % 2 else "C"}
                    for i, name in enumerate(["Jayson Tatum", "Nikola Jokić", "Stephen Curry",
                                              "Luka Dončić", "Anthony Edwards", "Shai Gilgeous-Alexander",
                                              "Test Athlete Seven", "Test Athlete Eight", "Test Athlete Nine"])]
            page.evaluate("payload => window.postMessage({type:'streamlit:render',args:{payload}}, '*')",
                          {"auth": {"role": "free"}, "player_catalog": {"players": rows},
                           "premium_player_averages": {"rows": {"jaysontatum": {"pts": 28.1,
                              "reb": 8.1, "ast": 4.9, "games": 14, "three_pct": 37.5}}}})
            page.wait_for_function("document.querySelectorAll('.hzp-player-row').length===7")
            self.assertEqual(page.locator(".hzp-table-header span").count(), 5)
            self.assertEqual(page.locator(".hzp-table-header span").nth(2).inner_text(), "MECZE")
            self.assertEqual(page.locator(".hzp-player-avatar img").count(), 0)
            first_avatar = page.locator(".hzp-player-avatar").first
            self.assertGreaterEqual(first_avatar.bounding_box()["width"], 43)
            self.assertEqual(first_avatar.locator(".hzp-avatar-fallback").inner_text(), "JT")
            self.assertEqual(first_avatar.evaluate("el => getComputedStyle(el).borderRadius"), "50%")
            self.assertIn("gradient", first_avatar.evaluate("el => getComputedStyle(el).backgroundImage"))
            # A stale caller must not be able to re-enable the old CDN path.
            page.evaluate("() => window.HoopzaroPortraits.observe(document.querySelector('#hzp-table-rows'))")
            page.wait_for_timeout(150)
            self.assertEqual(page.locator(".hzp-player-avatar img").count(), 0)
            self.assertEqual(page.locator(".hzp-stat.is-locked").count(), 7)
            self.assertEqual(page.locator(".hzp-games.is-locked").count(), 7)
            self.assertTrue(all(text == "♢" for text in page.locator(".hzp-games").all_text_contents()))
            self.assertNotIn("28,1", page.locator("#hzp-table-rows").inner_text())
            self.assertIn("Jayson Tatum", page.locator("#hzp-spotlight-body").inner_text())
            self.assertEqual(page.locator(".hzp-player-row[aria-pressed='true']").count(), 1)
            self.assertIn("♢", page.locator("#hzp-spotlight-body").inner_text())
            self.assertNotIn("28,1", page.locator("#hzp-spotlight-body").inner_text())
            box_list = page.locator(".hzp-table-card").bounding_box()
            box_spotlight = page.locator(".hzp-spotlight").bounding_box()
            self.assertGreater(box_spotlight["x"], box_list["x"] + box_list["width"])
            self.assertLessEqual(box_spotlight["x"] + box_spotlight["width"],
                                 page.locator("#hzp-players-pane").bounding_box()["x"] +
                                 page.locator("#hzp-players-pane").bounding_box()["width"] + 1)
            page.locator(".hzp-player-row").nth(1).click()
            self.assertIn("Stephen Curry", page.locator("#hzp-spotlight-body").inner_text())
            page.locator("#hzp-search").fill("does-not-exist")
            self.assertIn("Stephen Curry", page.locator("#hzp-spotlight-body").inner_text())
            self.assertIn("ostatnio wybrany profil", page.locator("#hzp-spotlight-body").inner_text())
            page.locator("#hzp-search").fill("")
            page.evaluate("payload => window.postMessage({type:'streamlit:render',args:{payload}}, '*')",
                          {"auth": {"role": "free"},
                           "player_catalog": {"players": [], "error": "ESPN niedostępny"}})
            self.assertIn("Stephen Curry", page.locator("#hzp-spotlight-body").inner_text())
            page.evaluate("payload => window.postMessage({type:'streamlit:render',args:{payload}}, '*')",
                          {"auth": {"role": "free"}, "player_catalog": {"players": rows}})
            page.locator(".hzp-player-row").first.click()
            page.locator("#hzp-cta").click()
            self.assertTrue(page.locator("#hz-paywall-dialog").is_visible())
            self.assertIn("9.99", page.locator("#hz-paywall-dialog").inner_text())
            page.locator("#hz-paywall-close").click()

            page.evaluate("payload => window.postMessage({type:'streamlit:render',args:{payload}}, '*')",
                          {"auth": {"role": "premium"}, "player_catalog": {"players": rows},
                           "premium_player_averages": {"scope": "sezon zasadniczy", "source": "NBA Stats",
                             "rows": {"jaysontatum": {"pts": 28.1, "reb": 8.1, "ast": 4.9,
                                                    "three_pm": 3.0, "three_pa": 8.0,
                                                    "three_pct": 37.5}}}})
            page.wait_for_function("document.querySelector('#hzp-table-rows').textContent.includes('28,1')")
            page.wait_for_function("window.__premiumRequests.length > 0")
            ids = page.evaluate("window.__premiumRequests[0].player_ids")
            self.assertEqual(len(ids), 7)
            self.assertTrue(all(identifier.isdigit() for identifier in ids))
            self.assertEqual(page.locator("#hzp-team").evaluate(
                "element => getComputedStyle(element).appearance"), "none")
            self.assertEqual(page.locator(".hzp-stat.is-locked").count(), 0)
            self.assertEqual(page.locator(".hzp-games.is-locked").count(), 0)
            self.assertEqual(page.locator(".hzp-player-avatar img").count(), 0)
            self.assertIn("37,5%", page.locator("#hzp-spotlight-body").inner_text())
            self.assertIn("8,0", page.locator("#hzp-spotlight-body").inner_text())
            # When verified ESPN IDs exist, never fall back to a conflicting
            # same-name athlete's historical row.
            page.evaluate("payload => window.postMessage({type:'streamlit:render',args:{payload}}, '*')",
                          {"auth": {"role": "premium"}, "player_catalog": {"players": rows},
                           "premium_player_averages": {
                             "rows": {"jaysontatum": {"pts": 99.9}},
                             "id_rows": {"0": {"pts": 22.2, "reb": 7.0,
                                                "ast": 5.0, "games": 3,
                                                "three_pm_games": 1,
                                                "three_pa_games": 1,
                                                "three_pct_games": 1}},
                             "attempted_ids": ["0"], "unavailable_ids": []}})
            page.wait_for_function("document.querySelector('#hzp-table-rows').textContent.includes('22,2')")
            self.assertEqual(page.locator(".hzp-player-row").first.locator(".hzp-games").inner_text(), "3")
            self.assertEqual(page.locator(".hzp-player-row").first.locator(".hzp-player-identity small").inner_text(), "C")
            self.assertIn("22,2", page.locator("#hzp-spotlight-body").inner_text())
            self.assertEqual(page.locator(".hzp-spotlight-games strong").inner_text(), "3")
            self.assertNotIn("99,9", page.locator("#hzp-table-rows").inner_text())
            page.locator("#hzp-search").fill("Tatum")
            self.assertEqual(page.locator(".hzp-player-row").count(), 1)
            page.locator("#hzp-search").fill("")
            page.locator("#hzp-next").click()
            self.assertIn("2 / 2", page.locator("#hzp-page").inner_text())
            self.assertEqual(page.locator(".hzp-player-row[aria-pressed='true']").count(), 1)
            self.assertIn(page.locator(".hzp-player-row[aria-pressed='true'] .hzp-player-identity strong").inner_text(),
                          page.locator("#hzp-spotlight-body").inner_text())
            self.assertFalse(any("/headshots/" in url or
                                 "commons.wikimedia.org" in url for url in requests))
            self.assertFalse(errors, errors)
            browser.close()


if __name__ == "__main__":
    unittest.main()
