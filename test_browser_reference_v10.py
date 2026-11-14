"""Chromium visual smoke for the HOOPZARO 1231 × 691 px screen.

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
        # Centrum is the free landing screen. Player Props uses the matching
        # HOOPZARO design, with the live chart and interaction logic intact.
        assert page.locator("#bestbets-centre").is_visible()
        page.locator('.nav-btn[data-page="props"]').click()
        assert_box(page, "#stage", 0, 0, 1231, 691)
        assert_box(page, ".topsearch", 195, 77, 827, 39)
        assert_box(page, "#hero", 192, 158, 1027, 106)
        assert_box(page, ".controls", 192, 271, 1027, 45)
        assert_box(page, "#chart-panel", 192, 328, 598, 235)
        assert_box(page, "#side-stats", 807, 328, 412, 235)
        assert_box(page, "#take", 192, 576, 1027, 56)
        assert page.locator("#props-heading").is_visible()
        assert page.locator("#footer").is_hidden()
        assert page.locator(".preview").count() == 6
        assert page.locator("#player-name").inner_text() == "Wyszukaj zawodnika"

        page.locator('.nav-btn[data-page="games"]').click()
        assert page.locator("#schedule-pane").is_visible()
        # The schedule fills the workspace from the top, without the old
        # 63-pixel spacer above its header. Its bottom edge stays unchanged.
        assert_box(page, "#schedule-pane", 191, 9, 1025, 635)
        assert page.locator("#blank-pane").is_hidden()
        assert "Terminarz" in page.locator("#schedule-pane").inner_text()
        assert page.locator("#hzs-date-strip button").count() == 7
        selected_day = page.locator(".hzs-date.selected").get_attribute("data-hzs-day")
        schedule_games = [
            {"id": f"layout-{index}", "day": selected_day,
             "away": "DEN", "home": "NOP", "state": status,
             "start": f"{selected_day}T02:00:00Z", "status": "Q3 03:00",
             "away_score": 98, "home_score": 91}
            for index, status in enumerate(("live", "final", "scheduled"))
        ]
        page.evaluate(
            "home => window.postMessage({type:'streamlit:render',args:{payload:{home}}}, '*')",
            {"calendar_today": selected_day, "calendar_loaded_days": [selected_day],
             "calendar_games": schedule_games,
             "form_options": [{"team": "DEN", "wins": 6, "losses": 4,
                               "ppg": 114.5, "record_verified": True}]},
        )
        page.wait_for_function("document.querySelectorAll('#hzs-board .hzs-game').length===3")
        assert page.locator("#hzs-board .hzs-game").count() == 3
        assert page.locator("#hzs-board .hzs-rows").count() == 1
        assert page.locator("#hzs-board .hzs-columns").count() == 0
        assert "NA ŻYWO · 3. KWARTA" in page.locator("#hzs-board").inner_text()
        assert "114,5 PPG" in page.locator("#hzs-board").inner_text()
        board_box = page.locator("#hzs-board").bounding_box()
        game_box = page.locator("#hzs-board .hzs-game").first.bounding_box()
        assert board_box and game_box
        assert game_box["width"] >= board_box["width"] - 16, (board_box, game_box)
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
        assert page.locator("#query").input_value() == "Test Athlete over 25.5 points"
        assert "bb-plot-bar" in page.locator("#chart-svg rect.bb-plot-bar").first.get_attribute("class")
        assert "stat-pop" in page.locator("#rate10").get_attribute("class")
        assert page.locator("#chart-svg rect").count() >= 4
        page.locator('[data-market="REB"]').click()
        assert "Rebounds" in page.locator("#chart-heading").inner_text()
        assert page.locator("#query").input_value() == "Test Athlete over 25.5 rebounds"
        page.locator("#line-plus").click()
        assert page.locator("#line").input_value() == "26"
        assert page.locator("#query").input_value() == "Test Athlete over 26.0 rebounds"
        page.locator('[data-side="UNDER"]').click()
        assert "UNDER" in page.locator("#take-text").inner_text()
        assert page.locator("#query").input_value() == "Test Athlete under 26.0 rebounds"

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

        # The HOOPZARO artwork retains 1231x691 stage coordinates.
        # When wider than its original aspect ratio, use full browser width
        # and allow vertical scrolling. A 'fit height' assertion would
        # reproduce the original black-gutter regression.
        page.set_viewport_size({"width":1664, "height":820})
        page.wait_for_function(
            "Math.abs(document.querySelector('#stage').getBoundingClientRect().width - innerWidth) < 3"
        )
        box=page.locator("#stage").bounding_box()
        assert box and box["width"]>=1662 and box["height"]>820,box
        page.locator("#take").scroll_into_view_if_needed()
        assert page.locator("#take").is_visible()
        page.set_viewport_size({"width":1231, "height":691})
        page.emulate_media(reduced_motion="reduce")
        assert page.locator(".bb-plot-bar").first.evaluate(
            "(node) => getComputedStyle(node).animationName"
        ) == "none"
        page.emulate_media(reduced_motion="no-preference")
        page.screenshot(path=str(OUT), full_page=True)
        assert not errors, errors
        browser.close()
        print("HOOPZARO reference coordinates and all interactions passed.")
        print("Saved test screenshot:", OUT)


if __name__ == "__main__":
    main()
