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
        # The OPEN market popup must also be HOOPZARO-themed. Styling a native
        # select alone leaves Windows/Opera to draw an unthemed options list.
        market = page.locator("#market")
        trigger = page.locator("#market-trigger")
        menu = page.locator("#market-options")
        assert market.evaluate("e => getComputedStyle(e).opacity") == "0"
        assert menu.is_hidden()
        # Browser/Opera must not draw native grey up/down spinners over the
        # custom neon minus/plus controls around the line threshold.
        line_input = page.locator("#line")
        assert line_input.get_attribute("type") == "number"
        assert line_input.evaluate("e => getComputedStyle(e).appearance") == "textfield"
        # Chromium may not expose author styles on native spinner pseudo-
        # elements through getComputedStyle(), even when their CSS is applied.
        # Guard the explicit WebKit/Opera override in the stylesheet instead.
        stylesheet = (ROOT / "bestbets_reference_frontend" / "hoopzaro.css").read_text(encoding="utf-8")
        assert "#line-group .line-control input::-webkit-inner-spin-button" in stylesheet
        assert "#line-group .line-control input::-webkit-outer-spin-button" in stylesheet
        assert page.locator("#line-minus").is_visible()
        assert page.locator("#line-plus").is_visible()
        # The compact help icon opens a branded, keyboard-accessible guide
        # without using the normal search action or modifying chart data.
        help_trigger = page.locator("#props-help-trigger")
        help_panel = page.locator("#props-help-panel")
        assert help_trigger.is_visible()
        assert help_panel.is_hidden()
        assert help_trigger.get_attribute("aria-expanded") == "false"
        help_trigger.click()
        assert help_panel.is_visible()
        assert help_trigger.get_attribute("aria-expanded") == "true"
        assert help_panel.get_attribute("role") == "dialog"
        assert help_panel.evaluate("e => getComputedStyle(e).position") == "absolute"
        assert "linear-gradient" in help_panel.evaluate("e => getComputedStyle(e).backgroundImage")
        assert "over/under" in help_panel.inner_text()
        assert all(market in help_panel.inner_text() for market in ("PTS", "REB", "AST", "3PM", "PRA"))
        assert page.locator("#props-help-close").evaluate("e => e === document.activeElement")
        page.keyboard.press("Escape")
        assert help_panel.is_hidden()
        assert help_trigger.evaluate("e => e === document.activeElement")
        help_trigger.click()
        page.locator('[data-help-query="Jayson Tatum under 3.5 assists"]').click()
        assert help_panel.is_hidden()
        assert page.locator("#query").input_value() == "Jayson Tatum under 3.5 assists"
        assert page.locator("#query").evaluate("e => e === document.activeElement")
        help_trigger.click()
        page.locator("#hero").click(position={"x":70,"y":40})
        assert help_panel.is_hidden()
        help_trigger.click()
        page.locator('.nav-btn[data-page="games"]').click()
        assert help_panel.is_hidden()
        page.locator('.nav-btn[data-page="props"]').click()
        assert help_trigger.get_attribute("aria-expanded") == "false"
        trigger.click()
        assert menu.is_visible()
        assert trigger.get_attribute("aria-expanded") == "true"
        assert menu.locator('[role="option"]').count() == 5
        assert menu.evaluate("e => getComputedStyle(e).position") == "absolute"
        assert menu.evaluate("e => getComputedStyle(e).backgroundImage").startswith("linear-gradient")
        assert menu.evaluate("e => getComputedStyle(e).borderTopColor") != "rgb(0, 0, 0)"
        assert menu.bounding_box()["width"] > trigger.bounding_box()["width"]
        assert menu.locator('[data-market-choice="PTS"]').get_attribute("aria-selected") == "true"
        menu.locator('[data-market-choice="PRA"]').click()
        assert menu.is_hidden()
        assert market.input_value() == "PRA"
        assert trigger.get_attribute("aria-expanded") == "false"
        assert page.locator("#market-selected-label").inner_text() == "PTS + REB + AST"
        assert page.locator('[data-market="PRA"]').get_attribute("class") == "on"
        trigger.focus()
        page.keyboard.press("ArrowDown")
        assert menu.is_visible()
        assert menu.locator('[data-market-choice="PRA"]').evaluate("e => e === document.activeElement")
        page.keyboard.press("Home")
        page.keyboard.press("ArrowDown")
        assert menu.locator('[data-market-choice="REB"]').evaluate("e => e === document.activeElement")
        page.keyboard.press("Enter")
        assert market.input_value() == "REB"
        assert page.locator("#market-selected-label").inner_text() == "Rebounds"
        trigger.click()
        page.keyboard.press("Escape")
        assert menu.is_hidden()
        trigger.click()
        page.locator("#chart-panel").click(position={"x":500,"y":150})
        assert menu.is_hidden()

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
                               "ppg": 114.5, "record_verified": True},
                              {"team": "NOP", "wins": 5, "losses": 5,
                               "ppg": 112.3, "record_verified": True}]},
        )
        page.wait_for_function("document.querySelectorAll('#hzs-board .hzs-game').length===3")
        assert page.locator("#hzs-board .hzs-game").count() == 3
        assert page.locator("#hzs-board .hzs-rows").count() == 1
        assert page.locator("#hzs-board .hzs-featured").count() == 1
        assert page.locator("#hzs-board .hzs-rows .hzs-game").count() == 2
        assert page.locator("#hzs-board .hzs-feature-ribbon").inner_text().strip().find("MECZ DNIA") >= 0
        assert page.locator("#hzs-match-count").inner_text() == "3 mecze"
        assert len(page.locator("#hzs-board .hzs-rows").evaluate(
            "e => getComputedStyle(e).gridTemplateColumns.split(' ').filter(Boolean)")) == 2
        assert "NA ŻYWO · 3. KWARTA" in page.locator("#hzs-board").inner_text()
        assert "114,5 PPG" in page.locator("#hzs-board").inner_text()
        board_box = page.locator("#hzs-board").bounding_box()
        game_box = page.locator("#hzs-board .hzs-featured").bounding_box()
        assert board_box and game_box
        assert game_box["width"] >= board_box["width"] - 16, (board_box, game_box)
        # The showcase and filters are FREE: no model scores or Premium
        # predictions may be exposed by the schedule renderer.
        assert "PRZEWIDYWANY" not in page.locator("#schedule-pane").inner_text()
        assert "SYMU" not in page.locator("#schedule-pane").inner_text()
        page.locator('[data-hzs-filter="live"]').click()
        assert page.locator("#hzs-board .hzs-game").count() == 1
        assert page.locator("#hzs-board .hzs-featured").count() == 0
        assert page.locator('[data-hzs-filter="live"]').get_attribute("aria-pressed") == "true"
        page.locator('[data-hzs-filter="final"]').click()
        assert page.locator("#hzs-board .hzs-game").count() == 1
        page.locator('[data-hzs-filter="scheduled"]').click()
        assert page.locator("#hzs-board .hzs-game").count() == 1
        assert "NADCHODZĄCE" in page.locator("#hzs-board").inner_text()
        page.locator('[data-hzs-filter="all"]').click()
        assert page.locator("#hzs-board .hzs-game").count() == 3
        assert page.locator("#hzs-board .hzs-featured").count() == 1
        # Unverified standings must not create a fake 'game of the day'.
        page.evaluate(
            "home => window.postMessage({type:'streamlit:render',args:{payload:{home}}}, '*')",
            {"calendar_today": selected_day, "calendar_loaded_days": [selected_day],
             "calendar_games": schedule_games,
             "form_options": [{"team": "DEN", "wins": 6, "losses": 4,
                               "ppg": 114.5, "record_verified": True}]},
        )
        page.wait_for_function("document.querySelectorAll('#hzs-board .hzs-featured').length===0")
        assert page.locator("#hzs-board .hzs-game").count() == 3
        # Four public matchups from the Nov 20 schedule: NYK–MIN is a
        # stronger, more evenly matched pairing than GSW–MEM despite its
        # lower PPG. Never hardcode the chosen teams in production code.
        spotlight_pairs = [("GSW", "MEM"), ("LAC", "SAS"),
                           ("NYK", "MIN"), ("POR", "MIL")]
        public_stats = [
            ("GSW", 8, 7, 113.7), ("MEM", 11, 4, 121.9),
            ("LAC", 4, 9, 111.9), ("SAS", 12, 3, 117.1),
            ("NYK", 8, 6, 110.0), ("MIN", 11, 4, 116.7),
            ("POR", 9, 5, 117.0), ("MIL", 1, 14, 107.7),
        ]
        page.evaluate(
            "home => window.postMessage({type:'streamlit:render',args:{payload:{home}}}, '*')",
            {"calendar_today": selected_day, "calendar_loaded_days": [selected_day],
             "calendar_games": [
                 {"id": f"spotlight-{i}", "day": selected_day,
                  "away": away, "home": home, "state": "scheduled",
                  "start": f"{selected_day}T01:00:00Z"}
                 for i, (away, home) in enumerate(spotlight_pairs)
             ],
             "form_options": [
                 {"team": code, "wins": wins, "losses": losses,
                  "ppg": ppg, "record_verified": True}
                 for code, wins, losses, ppg in public_stats
             ]},
        )
        page.wait_for_function(
            "document.querySelector('#hzs-board .hzs-featured .hzs-team.away .hzs-team-info strong')?.textContent==='NYK'"
        )
        assert "MIN" in page.locator("#hzs-board .hzs-featured").inner_text()
        assert "45%" in (page.locator(".hzs-feature-ribbon").get_attribute("title") or "")
        assert page.locator("#hzs-board .hzs-game").count() == 4
        feature_box = page.locator("#hzs-board .hzs-featured").bounding_box()
        compact_box = page.locator("#hzs-board .hzs-rows .hzs-game").first.bounding_box()
        assert feature_box and feature_box["height"] <= 122, feature_box
        assert compact_box and compact_box["height"] <= 70, compact_box
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
                      # Props search now correctly requires a Premium identity.
                      {"player":player,"error":"","brand":"", "auth":{"role":"premium"}})
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
        page.locator("#line-minus").click()
        assert page.locator("#line").input_value() == "25.5"
        page.locator("#line-plus").click()
        assert page.locator("#line").input_value() == "26"
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
