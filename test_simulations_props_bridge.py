"""Real-browser Premium bridge: Props history ↔ selected NBA game forecast.

All fixtures are synthetic test-only records. This is not public app data.
"""
from pathlib import Path
from shutil import which
from playwright.sync_api import sync_playwright

PAGE = (Path(__file__).parent / "bestbets_reference_frontend" / "index.html").as_uri()


def main():
    with sync_playwright() as tool:
        executable = which("chromium") or which("google-chrome")
        options = {"executable_path": executable} if executable else {}
        browser = tool.chromium.launch(headless=True, args=["--no-sandbox"], **options)
        page = browser.new_page(viewport={"width": 1231, "height": 691}, device_scale_factor=1)
        errors = []
        page.on("pageerror", lambda exc: errors.append(str(exc)))
        page.clock.set_fixed_time("2026-11-14T12:00:00Z")
        page.goto(PAGE, wait_until="load")
        page.locator('.nav-btn[data-page="simulations"]').click()
        day = "2026-11-14"
        final_game = {
            "id": "40100000", "day": day, "away": "NYK", "home": "IND",
            "state": "final", "start": "2026-11-14T02:00:00Z"
        }
        future_day = "2026-11-15"
        future_game = {
            "id": "40109999", "day": future_day, "away": "IND", "home": "BOS",
            "state": "scheduled", "start": "2026-11-16T01:00:00Z"
        }
        home = {
            "calendar_today": day, "calendar_loaded_days": [day, future_day],
            "calendar_games": [final_game],
            "calendar_extras": {future_day: {"games": [future_game], "team_logos": {}}}
        }
        player = {"name": "Test Player 0", "team": "IND", "pts": 26.1, "reb": 6.7, "ast": 4.1}
        def premium_for(which, which_day):
            return {
                "entitled": True,
                "game": {
                    "date": which_day, "game_id": which["id"], "model_id": "research_form_v74",
                    "away": which["away"], "home": which["home"],
                    "away_points": 115.0, "home_points": 116.0, "total_points": 231.0,
                    "away_win_pct": 49.2, "home_win_pct": 50.8,
                    "distributions": {}
                },
                "players": {
                    "date": which_day, "game_id": which["id"], "model_id": "research_form_v74",
                    "home": which["home"], "players": [player]
                }
            }
        payload = {
            "brand": "", "auth": {"role": "premium"},
            "home": home, "premium_simulation": premium_for(final_game, day)
        }
        page.evaluate(
            "data => window.postMessage({type:'streamlit:render',args:{payload:data}}, '*')",
            payload
        )
        page.wait_for_function("document.querySelector('#hzm-score')?.textContent==='115 : 116'")
        page.locator("#hzm-lab-tab-players").click()
        assert "Test Player 0" in page.locator("#hzm-player-inspector").inner_text()
        # From model forecast to the historical analysis, with a visibly
        # hypothetical editable half-point starting line.
        page.locator('[data-hzm-history-market="PTS"]').click()
        # Props container has absolutely positioned children and no intrinsic
        # box height. Verify the actually visible Props hero and route instead.
        assert page.locator("#hero").is_visible()
        assert page.locator("#simulations-pane").is_hidden()
        assert page.locator("#query").input_value() == "Test Player 0 over 26.5 points"
        assert "nie jest kursem" in page.locator("#hz-props-bridge-note").inner_text()
        assert page.locator("#hz-paywall-backdrop").is_hidden()

        # Streamlit's trusted response for that same athlete's Player Props.
        payload["player"] = {
            "name": "Test Player 0", "team": "IND", "market": "PTS",
            "line": 26.5, "side": "OVER", "position": "PG",
            "games": [], "season": "2026-27"
        }
        page.evaluate(
            "data => window.postMessage({type:'streamlit:render',args:{payload:data}}, '*')",
            payload
        )
        assert page.locator("#hz-props-open-simulation").is_visible()
        # Props -> nearest confirmed UPCOMING match for IND (not the final
        # game where this player previously appeared, nor an unrelated fixture).
        page.locator("#hz-props-open-simulation").click()
        assert page.locator("#simulations-pane").is_visible()
        assert page.locator("#hzm-lab-tab-players").get_attribute("aria-selected") == "true"
        assert page.locator("#hzm-match-picker-label").inner_text() == "IND – BOS"
        assert page.locator("#hzm-player-search").input_value() == "Test Player 0"
        assert page.locator("#hzm-score").inner_text() == "— : —", \
            "The prior final game's model may not leak into the future fixture"
        assert "Test Player 0" not in page.locator("#hzm-player-inspector").inner_text()

        payload["premium_simulation"] = premium_for(future_game, future_day)
        page.evaluate(
            "data => window.postMessage({type:'streamlit:render',args:{payload:data}}, '*')",
            payload
        )
        assert "Test Player 0" in page.locator("#hzm-player-inspector").inner_text()
        assert page.locator("[data-hzm-return-props]").is_visible()
        page.locator("[data-hzm-return-props]").click()
        assert page.locator("#hero").is_visible()
        assert page.locator("#simulations-pane").is_hidden()
        assert page.locator("#query").input_value() == "Test Player 0 over 26.5 points"
        assert page.locator("#hero-line").inner_text() == "26.5"
        assert page.locator("#hz-paywall-backdrop").is_hidden()

        # Role downgrade must not trigger a new paid run via the bridge.
        payload["auth"] = {"role": "free"}
        payload["premium_simulation"] = {"entitled": False, "game": None, "players": None}
        page.evaluate(
            "data => window.postMessage({type:'streamlit:render',args:{payload:data}}, '*')",
            payload
        )
        page.locator("#hz-props-open-simulation").click()
        assert page.locator("#hz-paywall-backdrop").is_visible()
        assert page.locator("#simulations-pane").is_hidden()
        page.locator("#hz-paywall-close").click()
        assert not errors, errors
        browser.close()
        print("Simulation ↔ Props bridge: real player, verified fixture, return and Premium gate OK")


if __name__ == "__main__":
    main()
