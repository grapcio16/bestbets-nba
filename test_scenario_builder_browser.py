"""Scenario Builder browser smoke; fixtures are synthetic, never published as NBA data."""
from pathlib import Path
from shutil import which

from playwright.sync_api import sync_playwright

PAGE = (Path(__file__).parent / "bestbets_reference_frontend" / "index.html").as_uri()


def main():
    with sync_playwright() as p:
        executable = which("chromium") or which("google-chrome")
        opts = {"executable_path": executable} if executable else {}
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"], **opts)
        page = browser.new_page(viewport={"width": 1231, "height": 691})
        page.clock.set_fixed_time("2026-11-21T12:00:00Z")
        errors = []
        page.on("pageerror", lambda exc: errors.append(str(exc)))
        page.goto(PAGE, wait_until="load")
        page.locator('.nav-btn[data-page="simulations"]').click()
        day = "2026-11-23"
        game_id = "401999444"
        home = {
            "calendar_today": day,
            "calendar_loaded_days": [day],
            "calendar_games": [{
                "id": game_id, "day": day, "away": "NYK", "home": "BOS",
                "state": "scheduled", "start": "2026-11-23T01:00:00Z"
            }]
        }
        base = {
            "date": day, "game_id": game_id, "model_id": "research_form_v74",
            "away_points": 113.0, "home_points": 117.0,
            "total_points": 230.0, "away_win_pct": 49, "home_win_pct": 51,
            "distributions": {}, "n_sims": 5000
        }
        payload = {
            "auth": {"role": "premium"}, "home": home, "brand": "",
            "premium_simulation": {
                "entitled": True, "game": base, "players": None, "scenario": None
            }
        }
        page.evaluate(
            "data => window.postMessage({type:'streamlit:render',args:{payload:data}}, '*')",
            payload,
        )
        # The fixture day may differ from the app's local current day.
        # Select it explicitly, as a user would in the date control.
        page.locator("#hzm-day-input").fill(day)
        page.locator("#hzm-day-input").dispatch_event("change")
        page.locator("#hzm-lab-tab-scenario").click()
        assert page.locator("#hzm-scenario-panel").is_visible()
        assert page.locator("#hzm-scenario-base").inner_text() == "230,0 pkt"
        assert page.locator("#hzm-scenario-whatif").inner_text() == "—"
        assert page.locator("#hzm-scenario-run").is_enabled()

        page.evaluate("""() => {
          window.__scenarioRequests = [];
          window.addEventListener('message', event => {
            if(event.data?.type === 'streamlit:setComponentValue' &&
               event.data.value?.type === 'premium_sim_scenario')
              window.__scenarioRequests.push(event.data.value);
          });
        }""")
        page.locator("#hzm-scenario-pace").evaluate(
            """el => {el.value='3';el.dispatchEvent(new Event('input',{bubbles:true}))}"""
        )
        assert page.locator("#hzm-scenario-pace-display").inner_text() == "+3%"
        page.locator("#hzm-scenario-run").click()
        page.wait_for_function("window.__scenarioRequests.length===1")
        req = page.evaluate("window.__scenarioRequests[0]")
        assert req["pace_pct"] == 3 and req["game_id"] == game_id
        assert req["model_id"] == "research_form_v74"

        payload["premium_simulation"]["scenario"] = {
            "date": day, "game_id": game_id, "model_id": "research_form_v74",
            "pace_pct": 3,
            "baseline": {
                "total_points": 230.0, "away_points": 113.0,
                "home_points": 117.0, "away_win_pct": 49.0, "home_win_pct": 51.0},
            "scenario": {
                "total_points": 236.0, "away_points": 116.0,
                "home_points": 120.0, "away_win_pct": 48.6, "home_win_pct": 51.4},
        }
        page.evaluate(
            "data => window.postMessage({type:'streamlit:render',args:{payload:data}}, '*')",
            payload,
        )
        assert page.locator("#hzm-scenario-whatif").inner_text() == "236,0 pkt"
        assert page.locator("#hzm-scenario-delta").inner_text() == "+6,0 pkt"
        assert page.locator("#hzm-scenario-away-code").inner_text() == "NYK"
        assert page.locator("#hzm-scenario-home-code").inner_text() == "BOS"
        assert "113,0 pkt → 116,0 pkt" in page.locator("#hzm-scenario-away-points").inner_text()
        assert "117,0 pkt → 120,0 pkt" in page.locator("#hzm-scenario-home-points").inner_text()
        assert "-0,4 pp" in page.locator("#hzm-scenario-away-win").inner_text()
        assert "+0,4 pp" in page.locator("#hzm-scenario-home-win").inner_text()

        # A cached scenario for a different pace value must not appear.
        payload["premium_simulation"]["scenario"]["pace_pct"] = 2
        page.evaluate(
            "data => window.postMessage({type:'streamlit:render',args:{payload:data}}, '*')",
            payload,
        )
        assert page.locator("#hzm-scenario-whatif").inner_text() == "—"
        assert "→ —" in page.locator("#hzm-scenario-away-points").inner_text()

        payload["auth"] = {"role": "free"}
        payload["premium_simulation"] = {
            "entitled": False, "game": None, "players": None, "scenario": None
        }
        page.evaluate(
            "data => window.postMessage({type:'streamlit:render',args:{payload:data}}, '*')",
            payload,
        )
        assert page.locator("#hzm-scenario-whatif").inner_text() == "—"
        assert page.locator("#hzm-scenario-base").inner_text() == "—"
        assert page.locator("#hzm-scenario-run").is_disabled()
        assert page.locator("#hzm-scenario-away-points").inner_text() == "—"
        assert page.locator("#hzm-scenario-home-win").inner_text() == "—"
        assert not errors, errors
        browser.close()
        print("Scenario Builder browser: model switch isolation, render and free gate OK")


if __name__ == "__main__":
    main()
