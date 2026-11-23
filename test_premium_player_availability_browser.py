"""Chromium regression for pregame injury exclusion in all three models.

Fixture players are TEST-ONLY. Deliberately inject a stale/unsafe payload,
which browser must reject independently of the selected model.
"""
from pathlib import Path
from shutil import which
from playwright.sync_api import sync_playwright
from test_results_distributions_premium_browser import fixture

URL = (Path(__file__).parent / "bestbets_reference_frontend" / "index.html").as_uri()
OUT = Path("test-results/premium-player-injury-guard")
OUT.mkdir(parents=True, exist_ok=True)

def main():
    with sync_playwright() as p:
        executable = which("chromium") or which("google-chrome")
        browser = p.chromium.launch(
            headless=True, args=["--no-sandbox"],
            **({"executable_path": executable} if executable else {}),
        )
        for width, height in ((1672, 941), (390, 844)):
            page = browser.new_page(viewport={"width": width, "height": height})
            page.clock.set_fixed_time("2026-11-23T12:00:00Z")
            errors = []
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.goto(URL, wait_until="load")
            mobile = page.locator('#hz-mobile-nav [data-page="simulations"]')
            if mobile.is_visible():
                mobile.click()
            else:
                page.locator('.nav-btn[data-page="simulations"]').click()

            data = fixture()
            player_pack = data["premium_simulation"]["players"]
            player_pack["players"] = [
                {"name": "Test Out Alpha", "team": "IND", "espn_id": "10011",
                 "pts": 28.4, "reb": 8.0, "ast": 5.0,
                 "availability": "Niezweryfikowany", "history": []},
                {"name": "Test Risk Beta", "team": "NYK", "espn_id": "10012",
                 "pts": 25.4, "reb": 5.0, "ast": 9.0,
                 "availability": "Questionable", "history": []},
                {"name": "QA Test Player", "team": "IND", "espn_id": "10013",
                 "pts": 19.1, "reb": 5.3, "ast": 7.4,
                 "availability": "Niezweryfikowany", "history": []},
            ]
            watch = player_pack["injury_watch"]
            watch["rows"] = [
                {"name": "Test Out Alpha", "team": "IND",
                 "espn_id": "10011", "status": "Out"},
                {"name": "Test Risk Beta", "team": "NYK",
                 "espn_id": "10012", "status": "Questionable"},
            ]

            def push():
                page.evaluate(
                    "d => window.postMessage({type:'streamlit:render',args:{payload:d}}, '*')",
                    data,
                )

            push()
            page.wait_for_function(
                "() => document.querySelector('#hzm-score')?.textContent.includes('115 : 116')")
            page.locator("#hzm-lab-tab-players").click()
            for model in ("research_form_v74", "legacy_v72", "research_context_v75"):
                if model != "research_form_v74":
                    page.locator("#hzm-model-trigger").click()
                    page.locator("#hzm-model-option-" + model).click()
                    data["premium_simulation"]["game"]["model_id"] = model
                    player_pack["model_id"] = model
                    push()
                page.wait_for_function(
                    "() => document.querySelector('#hzv3-count')?.textContent.includes('1 projekcji')")
                assert page.locator("#hzv3-roster .hzv3-player").count() == 1, model
                assert page.locator(
                    '#hzv3-roster .hzv3-player[aria-label^="QA Test Player ·"]'
                ).count() == 1, model
                assert page.locator(
                    '#hzv3-roster .hzv3-player[aria-label^="Test Out Alpha ·"]'
                ).count() == 0, model
                assert page.locator(
                    '#hzv3-roster .hzv3-player[aria-label^="Test Risk Beta ·"]'
                ).count() == 0, model
                page.locator("#hzm-lab-tab-results").click()
                assert "Test Out Alpha" not in page.locator("#hzm-player-rows").inner_text()
                page.locator("#hzm-lab-tab-players").click()

            # An expired injury report invalidates even the formerly safe
            # player. No recommendations/plots should be left on screen.
            watch["fresh"] = False
            push()
            assert page.locator("#hzv3-roster .hzv3-player").count() == 0
            assert "Wstrzymano" in page.locator("#hzv3-roster").inner_text()
            assert page.locator("#hzv3-hist svg").count() == 0
            assert page.locator("#hzv3-trend svg").count() == 0

            # A new verified injury report can restore *eligible* records.
            watch["fresh"] = True
            push()
            assert page.locator("#hzv3-roster .hzv3-player").count() == 1
            page.screenshot(path=str(OUT / f"injury-safe-{width}.png"),full_page=True)
            assert not errors, errors
            page.close()
        browser.close()
        print("Injury Guard: three models, OUT & uncertain exclusion, "
              "report expiry, historical views, desktop and iPhone OK")


if __name__ == "__main__":
    main()
