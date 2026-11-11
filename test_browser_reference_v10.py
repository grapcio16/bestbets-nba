"""Chromium visual smoke for the custom 1231 × 691 px reference screen.

Uses synthetic ONLY-in-test fixtures to verify layout and chart interaction,
never inserts mock NBA data into the production app.
"""
from __future__ import annotations
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent
DOC = (ROOT / "bestbets_reference_frontend" / "index.html").as_uri()
OUT = ROOT / "reference_v10_smoke.png"


def assert_box(page, selector, x, y, w=None, h=None, tolerance=3):
    actual = page.locator(selector).bounding_box()
    if not actual:
        raise AssertionError("Missing element " + selector)
    for field, target in (("x", x), ("y", y), ("width", w), ("height", h)):
        if target is not None:
            if abs(actual[field] - target) > tolerance:
                raise AssertionError(
                    f"{selector}.{field}: expected {target}, got {actual[field]}"
                )


def main():
    with sync_playwright() as tool:
        browser = tool.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1231, "height": 691}, device_scale_factor=1)
        errors = []
        page.on("pageerror", lambda exc: errors.append(str(exc)))
        page.goto(DOC, wait_until="load")
        assert_box(page, "#stage", 0, 0, 1231, 691)
        assert_box(page, ".topsearch", 303, 10, 708, 38)
        assert_box(page, "#hero", 191, 90, 1028, 89)
        assert_box(page, ".controls", 192, 185, 1027, 42)
        assert_box(page, "#chart-panel", 192, 235, 598, 208)
        assert_box(page, "#side-stats", 807, 235, 412, 208)
        assert_box(page, "#take", 192, 449, 1027, 45)
        assert_box(page, "#card-shortcuts", 975, 519, 250, 128)
        assert page.locator(".preview").count() == 6
        assert page.locator("#player-name").inner_text() == "Wyszukaj zawodnika"

        page.locator("#card-games").click()
        assert page.locator("#blank-pane").is_visible()
        assert page.locator("#blank-title").inner_text() == "Terminarz"
        page.locator('[data-page="props"].nav-btn').click()
        assert page.locator("#hero").is_visible()

        # Simulate the documented component render message using isolated test fixtures.
        player = {
            "name":"Test Athlete","team":"BOS","position":"SF",
            "opponent":"NYK","season":"2026-27","next_game":"",
            "market":"PTS","line":25.5,"side":"OVER",
            "photo":"","logo":"","defense":108.4,"defense_recent":105.9,
            "games":[
                {"date":"2026-10-22","matchup":"BOS @ NYK","PTS":19,"REB":5,"AST":3,"FG3M":2,"PRA":27},
                {"date":"2026-10-25","matchup":"BOS vs. PHI","PTS":27,"REB":6,"AST":5,"FG3M":3,"PRA":38},
                {"date":"2026-10-27","matchup":"BOS @ MIA","PTS":30,"REB":8,"AST":4,"FG3M":2,"PRA":42},
            ]
        }
        page.evaluate("(data) => window.postMessage({type:'streamlit:render',args:{payload:data}}, '*')",
                      {"player":player,"error":"","brand":""})
        page.wait_for_function("document.querySelector('#player-name').textContent==='Test Athlete'")
        assert page.locator("#hero-avg").inner_text() == "25.3"
        assert page.locator("#hero-rate").inner_text() == "67%"
        assert page.locator("#rate10").inner_text() == "67%"
        assert page.locator("#chart-svg rect").count() >= 4
        page.locator('[data-market="REB"]').click()
        assert "Rebounds" in page.locator("#chart-heading").inner_text()
        page.locator("#line-plus").click()
        assert page.locator("#line").input_value() == "26"
        page.locator('[data-side="UNDER"]').click()
        assert "UNDER" in page.locator("#take-text").inner_text()

        page.evaluate("""() => {
          window.__observedSearch = [];
          window.addEventListener('message', e => {
            if (e.data && e.data.type === 'streamlit:setComponentValue')
              window.__observedSearch.push(e.data.value);
          });
        }""")
        page.locator("#query").fill("Jayson Tatum over 25.5 points")
        page.locator("#search-btn").click()
        page.wait_for_function("window.__observedSearch.length > 0")
        event = page.evaluate("window.__observedSearch[0]")
        assert event["type"] == "search"
        assert event["query"] == "Jayson Tatum over 25.5 points"

        page.screenshot(path=str(OUT), full_page=True)
        assert not errors, errors
        browser.close()
        print("Chromium reference coordinates and all interactions passed.")
        print("Saved test screenshot:", OUT)


if __name__ == "__main__":
    main()
