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
        assert page.locator("#schedule-pane").is_visible()
        assert page.locator("#schedule-pane .hzs-footnote").count() == 0
        assert page.locator("#hzs-source-note").count() == 0
        assert_box(page, "#schedule-pane", 191, 9, 1025, 635)
        assert page.locator("#schedule-pane .hzv-sport-nav").count() == 0
        assert page.locator("#blank-pane").is_hidden()
        assert page.locator("#hzv-calendar-toggle").is_visible()
        assert page.locator("#hzv-game-page").is_hidden()
        assert page.locator("#hzs-date-strip button").count() == 7
        selected_day = page.locator(".hzs-date.selected").get_attribute("data-hzs-day")
        schedule_games = [
            {"id": str(4018100000 + index), "day": selected_day,
             "away": "DEN", "home": "NOP", "state": status,
             "start": f"{selected_day}T02:00:00Z", "status": "Q3 03:00",
             "away_score": 98, "home_score": 91}
            for index, status in enumerate(("live", "final", "scheduled"))
        ]
        schedule_data = {
            "calendar_today": selected_day, "calendar_loaded_days": [selected_day],
            "calendar_games": schedule_games,
            "form_options": [
                {"team": "DEN", "name": "Denver Nuggets", "wins": 6, "losses": 4,
                 "ppg": 114.5, "record_verified": True},
                {"team": "NOP", "name": "New Orleans Pelicans", "wins": 5, "losses": 5,
                 "ppg": 112.3, "record_verified": True},
                {"team": "BOS", "name": "Boston Celtics", "wins": 8, "losses": 2,
                 "ppg": 113.6, "record_verified": True},
                {"team": "NYK", "name": "New York Knicks", "wins": 6, "losses": 4,
                 "ppg": 110.2, "record_verified": True},
            ]
        }
        page.evaluate(
            "home => { window.__scheduleHome=home; window.postMessage({type:'streamlit:render',args:{payload:{home}}}, '*') }",
            schedule_data,
        )
        page.wait_for_function("document.querySelectorAll('#hzs-board .hzs-game').length===3")
        assert page.locator("#hzs-board .hzs-game").count() == 3
        assert page.locator("#hzv-featured-button").is_visible()
        assert page.locator("#hzs-board .hzs-game").first.evaluate("e=>e.tagName") == "BUTTON"
        assert "MECZ DNIA" in page.locator("#hzv-hero").inner_text()
        assert page.locator("#hzs-match-count").inner_text() == "3 mecze"
        # Compact Terminarz: controls precede a shorter hero, with cards
        # visible immediately on the initial desktop screen.
        controls_box = page.locator(".hzv-controls").bounding_box()
        hero_box = page.locator("#hzv-hero").bounding_box()
        board_box = page.locator("#hzs-board").bounding_box()
        first_game_box = page.locator("#hzs-board .hzs-game").first.bounding_box()
        pane_box = page.locator("#schedule-pane").bounding_box()
        assert controls_box and hero_box and board_box and first_game_box and pane_box
        assert controls_box["y"] < hero_box["y"] < board_box["y"], (
            controls_box, hero_box, board_box)
        assert controls_box["y"] - pane_box["y"] < 100, (
            "Controls should begin immediately below schedule title", controls_box, pane_box)
        assert 100 <= hero_box["height"] <= 125, hero_box
        assert first_game_box["y"] + first_game_box["height"] < pane_box["y"] + pane_box["height"] - 15, (
            first_game_box, pane_box)
        # Never cut off the match's starting time / result caption.
        caption_box = page.locator("#hzs-board .hzs-mini-bottom").first.bounding_box()
        assert caption_box
        assert caption_box["y"] + caption_box["height"] <= (
            first_game_box["y"] + first_game_box["height"] - 3), (caption_box, first_game_box)
        assert page.locator("#hzs-board .hzs-mini-bottom").first.evaluate(
            "e => e.scrollHeight <= e.clientHeight + 2")
        assert page.locator("#hzv-day-title").count() == 0
        assert page.locator("#hzv-search").is_visible()
        assert page.locator("#hzs-today").is_visible()
        assert len(page.locator("#hzs-board .hzs-rows").first.evaluate(
            "e => getComputedStyle(e).gridTemplateColumns.split(' ').filter(Boolean)")) == 3
        assert page.locator("#hzv-east .hzv-stand-row").count() == 3
        assert page.locator("#hzv-west .hzv-stand-row").count() == 3
        assert "Celtics" in page.locator("#hzv-east").inner_text()
        assert "Nuggets" in page.locator("#hzv-west").inner_text()
        assert "PREMIUM" not in page.locator("#schedule-pane").inner_text()
        # The month popover must be closed by default; clicking a day
        # changes the selected schedule without moving the standings aside.
        assert page.locator("#hzv-calendar-popup").is_hidden()
        page.locator("#hzv-calendar-toggle").click()
        assert page.locator("#hzv-calendar-popup").is_visible()
        assert page.locator("#hzv-calendar-grid button").count() >= 28
        page.keyboard.press("Escape")
        assert page.locator("#hzv-calendar-popup").is_hidden()
        page.locator('[data-hzs-filter="live"]').click()
        assert page.locator("#hzs-board .hzs-game").count() == 1
        page.locator('[data-hzs-filter="final"]').click()
        assert page.locator("#hzs-board .hzs-game").count() == 1
        page.locator('[data-hzs-filter="scheduled"]').click()
        assert page.locator("#hzs-board .hzs-game").count() == 1
        # Clicking does not expand a box inside the match list.
        page.locator("#hzs-board .hzs-game").click()
        assert page.locator("#hzv-game-page").is_visible()
        assert page.locator("#hzs-board #hzv-game-content").count() == 0
        assert "Spotkanie jeszcze się nie rozpoczęło" in page.locator("#hzv-game-content").inner_text()
        assert page.locator("#hzv-game-content .hzv-gc-stat-row").count() == 0
        page.locator("#hzv-game-back").click()
        assert page.locator("#hzv-game-page").is_hidden()
        # Final score: request the one verified ESPN box score only on click.
        page.evaluate("""() => {
          window.__scheduleRequests = [];
          window.addEventListener('message', event => {
            if(event.data?.type==='streamlit:setComponentValue' &&
              event.data.value?.type==='schedule_game_details')
              window.__scheduleRequests.push(event.data.value);
          });
        }""")
        page.locator('[data-hzs-filter="final"]').click()
        page.locator("#hzs-board .hzs-game").click()
        assert page.locator("#hzv-game-page").is_visible()
        page.wait_for_function("window.__scheduleRequests.length===1")
        request = page.evaluate("window.__scheduleRequests[0]")
        assert request["game_id"] == str(4018100001)
        assert request["date"] == selected_day
        page.evaluate(
            "details => window.postMessage({type:'streamlit:render',args:{payload:{home:window.__scheduleHome,schedule_game_details:details}}},'*')",
            {"id": str(4018100001), "day": selected_day, "error": "",
             "data": {"id": str(4018100001), "away": "DEN", "home": "NOP",
                      "quarters": [{"period":"Q1","away":28,"home":25},
                                   {"period":"Q2","away":22,"home":26}],
                      "team_stats": [{"label":"Zbiórki","away":"42","home":"39"}],
                      "leaders": {"away":[{"name":"Verified Player","pts":22,"reb":7,"ast":3}],
                                  "home":[{"name":"Another Player","pts":20,"reb":8,"ast":5}]},
                      "arena": "Test Arena", "source":"ESPN"}},
        )
        page.wait_for_function("document.querySelector('#hzv-game-content')?.textContent.includes('Verified Player')")
        assert "Q1" in page.locator("#hzv-game-content").inner_text()
        assert "Test Arena" in page.locator("#hzv-game-content").inner_text()
        assert page.locator("#hzv-game-content .hzv-gc-stat-row").count() == 1
        assert page.locator("#hzv-game-content .hzv-xfactor-chart svg").count() == 1
        assert page.locator('[data-hzv-history="h2h"]').is_visible()
        page.locator('[data-hzv-history="recent"]').click()
        assert page.locator('[data-hzv-history="recent"]').get_attribute("class") == "selected"
        # Simulate a genuine Streamlit iframe remount while Game Center
        # is open; the selected public game must survive the reload.
        page.reload(wait_until="load")
        assert page.locator("#schedule-pane").is_visible()
        page.evaluate(
            "args => window.postMessage({type:'streamlit:render',args:{payload:args}},'*')",
            {"home":schedule_data, "schedule_game_details":{
                "id":str(4018100001), "day":selected_day, "error":"",
                "data":{"id":str(4018100001),"away":"DEN","home":"NOP",
                        "quarters":[{"period":"Q1","away":28,"home":25}],
                        "team_stats":[{"label":"Zbiórki","away":"42","home":"39"}],
                        "leaders":{"away":[{"name":"Verified Player","pts":22,"reb":7,"ast":3}],
                                   "home":[]}, "source":"ESPN"}
            }},
        )
        page.wait_for_function(
            "document.querySelector('#hzv-game-content')?.textContent.includes('Verified Player')")
        assert page.locator("#hzv-game-page").is_visible()
        assert page.locator("#hzs-board .hzs-game").first.is_hidden()
        page.locator("#hzv-game-back").click()
        assert page.evaluate("!sessionStorage.getItem('hoopzaro.schedule.openGame.v1')")
        # An error for an earlier game must not obscure the loading state
        # when the user opens a different NBA match.
        page.locator('[data-hzs-filter="live"]').click()
        page.locator("#hzs-board .hzs-game").click()
        assert page.locator("#hzv-game-page").is_visible()
        page.evaluate(
            "args => window.postMessage({type:'streamlit:render',args:{payload:args}},'*')",
            {"home":schedule_data, "schedule_game_details":{
                "id":str(4018100001),"day":selected_day,
                "data":None,"error":"Poprzedni mecz jest niedostępny"
            }},
        )
        assert "Poprzedni mecz jest niedostępny" not in page.locator("#hzv-game-content").inner_text()
        assert "Pobieranie zweryfikowanego" in page.locator("#hzv-game-content").inner_text()
        page.evaluate(
            "args => window.postMessage({type:'streamlit:render',args:{payload:args}},'*')",
            {"home":schedule_data, "schedule_game_details":{
                "id":str(4018100000),"day":selected_day,
                "data":None,"error":"Szczegółowe statystyki ESPN są chwilowo niedostępne."
            }},
        )
        retry_button = page.locator("[data-hzv-retry-game]")
        assert retry_button.is_visible()
        retry_button.click()
        assert "Pobieranie zweryfikowanego" in page.locator("#hzv-game-content").inner_text()
        page.locator("#hzv-game-back").click()
        page.locator('[data-hzs-filter="all"]').click()
        # Unverified records never yield an invented featured matchup.
        page.evaluate(
            "home => window.postMessage({type:'streamlit:render',args:{payload:{home}}},'*')",
            {"calendar_today": selected_day, "calendar_loaded_days": [selected_day],
             "calendar_games": schedule_games,
             "form_options": [{"team": "DEN", "wins": 6, "losses": 4,
                               "ppg": 114.5, "record_verified": True}]},
        )
        page.wait_for_function("document.querySelector('#hzv-hero')?.textContent.includes('Brak zweryfikowanego')")
        assert page.locator("#hzs-board .hzs-game").count() == 3
        # On tall screens the Terminarz uses the extra available height.
        page.set_viewport_size({"width": 1400, "height": 940})
        page.wait_for_function("document.querySelector('#schedule-pane').getBoundingClientRect().height > 750")
        page.set_viewport_size({"width": 1231, "height": 691})
        page.wait_for_function("Math.abs(document.querySelector('#schedule-pane').getBoundingClientRect().height-635)<3")
        # Premium simulations: the final evidence strip must fit inside
        # the canvas, with a two-line heading and no clipped insight cards.
        page.locator('.nav-btn[data-page="simulations"]').click()
        assert page.locator("#simulations-pane").is_visible()
        pane_box = page.locator("#simulations-pane").bounding_box()
        premium_box = page.locator(".hzm-premium").bounding_box()
        date_box = page.locator(".hzm-day-control").bounding_box()
        model_box = page.locator(".hzm-model-choice").bounding_box()
        assert pane_box and premium_box and date_box and model_box
        assert 35 <= premium_box["height"] <= 38, premium_box
        premium_gem = page.locator(".hzm-premium .hz-premium-gem")
        gem_box = premium_gem.bounding_box()
        assert gem_box and 16 <= gem_box["width"] <= 20, gem_box
        assert premium_gem.evaluate(
            "e => getComputedStyle(e).backgroundImage.includes('conic-gradient')"
        ), "Premium diamond needs its gold/cyan facets"
        model_trigger = page.locator("#hzm-model-trigger")
        model_trigger.click()
        model_options = page.locator("#hzm-model-options")
        assert model_options.is_visible()
        assert model_trigger.get_attribute("aria-expanded") == "true"
        assert model_options.locator('[role="option"]').count() == 3
        assert model_options.evaluate(
            "e => getComputedStyle(e).backgroundImage.includes('gradient')"
        ), "Model options must use the HOOPZARO neon panel, not the OS menu"
        options_box = model_options.bounding_box()
        assert options_box and options_box["x"] >= pane_box["x"]
        assert options_box["x"] + options_box["width"] <= pane_box["x"] + pane_box["width"] + 1
        model_options.locator('[data-hzm-model="research_context_v75"]').click()
        assert not model_options.is_visible()
        assert page.locator("#hzm-model-select").input_value() == "research_context_v75"
        assert "V7.5" in model_trigger.inner_text()
        model_trigger.click()
        model_options.locator('[data-hzm-model="research_form_v74"]').click()
        assert page.locator("#hzm-model-select").input_value() == "research_form_v74"
        model_trigger.click()
        model_trigger.press("Escape")
        assert not model_options.is_visible()
        assert 38 <= date_box["height"] <= 41, date_box
        assert model_box["x"] + model_box["width"] + 6 < date_box["x"]
        assert date_box["x"] + date_box["width"] <= pane_box["x"] + pane_box["width"] + 1
        assert page.locator(".hzm-day-control button[data-hzm-shift]").count() == 2
        assert page.locator("#hzm-day-input").get_attribute("type") == "date"
        insights_box = page.locator(".hzm-insights").bounding_box()
        footer_box = page.locator(".hzm-footer").bounding_box()
        assert pane_box and insights_box and footer_box
        assert insights_box["y"] + insights_box["height"] < footer_box["y"] + 1
        assert footer_box["y"] + footer_box["height"] <= pane_box["y"] + pane_box["height"] - 2
        title = page.locator(".hzm-insight-title")
        assert title.evaluate("e => e.scrollWidth <= e.clientWidth + 2")
        assert title.evaluate("e => e.scrollHeight <= e.clientHeight + 2")
        for card in page.locator(".hzm-insights > div:not(:first-child)").all():
            box = card.bounding_box()
            assert box and box["y"] + box["height"] <= insights_box["y"] + insights_box["height"]
            assert card.locator("small").evaluate("e => e.scrollHeight <= e.clientHeight + 2")
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
        # Filter must operate on verified venue before calculating all windows.
        assert page.locator("#chart-svg .bb-venue-label").all_text_contents() == ["A", "H", "A"]
        # Existing average tiles, without popup or additional chart filters.
        assert page.locator(".venue-filter").count() == 0
        assert page.locator("#hz-avg-breakdown").count() == 0
        assert page.locator('[data-venue="ALL"]').get_attribute("aria-pressed") == "true"
        page.locator('[data-venue="HOME"]').click()
        assert page.locator("#chart-svg .bb-plot-bar").count() == 1
        assert page.locator("#chart-svg .bb-venue-label").all_text_contents() == ["H"]
        assert page.locator("#hero-avg").inner_text() == "27.0"
        assert page.locator("#season-avg").inner_text() == "25.3"
        assert page.locator("#rate10").inner_text() == "100%"
        assert page.locator("#home-avg").inner_text() == "27.0"
        assert page.locator("#away-avg").inner_text() == "24.5"
        assert "(Home)" in page.locator("#chart-heading").inner_text()
        assert page.locator("#sample10").inner_text() == "(1/1)"
        assert "meczów domowych" in page.locator("#take-text").inner_text()
        assert page.locator('[data-venue="HOME"]').get_attribute("aria-pressed") == "true"
        page.locator('[data-venue="AWAY"]').click()
        assert page.locator("#chart-svg .bb-plot-bar").count() == 2
        assert page.locator("#chart-svg .bb-venue-label").all_text_contents() == ["A", "A"]
        assert page.locator("#hero-avg").inner_text() == "24.5"
        assert page.locator("#season-avg").inner_text() == "25.3"
        assert page.locator("#rate10").inner_text() == "50%"
        assert page.locator("#home-avg").inner_text() == "27.0"
        assert page.locator("#away-avg").inner_text() == "24.5"
        assert "(Away)" in page.locator("#chart-heading").inner_text()
        assert page.locator("#sample10").inner_text() == "(1/2)"
        assert "meczów wyjazdowych" in page.locator("#take-text").inner_text()
        page.locator('[data-period="L5"]').click()
        assert page.locator("#chart-svg .bb-plot-bar").count() == 2
        page.locator('[data-venue="ALL"]').click()
        page.locator('[data-period="L10"]').click()
        assert "(Home)" not in page.locator("#chart-heading").inner_text()
        assert "(Away)" not in page.locator("#chart-heading").inner_text()
        assert page.locator("#chart-svg .bb-plot-bar").count() == 3
        assert page.locator("#hero-avg").inner_text() == "25.3"
        assert page.locator("#rate10").inner_text() == "67%"
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
