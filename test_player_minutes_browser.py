"""Real-browser historical ESPN Player Minutes across models; synthetic fixtures."""
from pathlib import Path
from shutil import which
from playwright.sync_api import sync_playwright

PAGE = (Path(__file__).parent / "bestbets_reference_frontend" / "index.html").as_uri()


def main():
    with sync_playwright() as p:
        exe = which("chromium") or which("google-chrome")
        browser = p.chromium.launch(
            headless=True, args=["--no-sandbox"],
            **({"executable_path": exe} if exe else {}))
        page = browser.new_page(viewport={"width": 1231, "height": 691})
        page.clock.set_fixed_time("2026-11-21T12:00:00Z")
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(PAGE, wait_until="load")
        page.locator('.nav-btn[data-page="simulations"]').click()

        day, game_id = "2026-11-23", "401999347"
        fixture = {
            "id": game_id, "day": day, "away": "NYK", "home": "BOS",
            "state": "scheduled", "start": "2026-11-23T01:00:00Z",
        }
        game = {
            "date": day, "game_id": game_id, "model_id": "research_context_v75",
            "away_points": 112.2, "home_points": 115.4,
            "total_points": 227.6, "away_win_pct": 46.0,
            "home_win_pct": 54.0, "distributions": {}, "n_sims": 5000,
        }
        active = {
            "name": "Test Athlete A", "team": "NYK", "minutes": 30.0,
            "minutes_sample": 4, "availability": "Questionable",
            "pts": 24.0, "reb": 6.0, "ast": 9.0,
        }
        out = {
            "name": "Test Athlete B", "team": "BOS", "minutes": 0.0,
            "minutes_sample": 5, "availability": "Out",
            "pts": None, "reb": None, "ast": None,
        }
        payload = {
            "brand": "", "auth": {"role": "premium"},
            "home": {
                "calendar_today": day,
                "calendar_loaded_days": [day],
                "calendar_games": [fixture],
            },
            "premium_simulation": {
                "entitled": True, "game": game,
                "players": {
                    "date": day, "game_id": game_id,
                    "model_id": "research_context_v75",
                    "home": "BOS", "players": [active, out],
                    "minute_roster": [
                        {"name": "Test Athlete A", "team": "NYK",
                         "position": "PG", "projection_index": 0},
                        {"name": "Reserve NYK", "team": "NYK",
                         "position": "C", "projection_index": None},
                        {"name": "Test Athlete B", "team": "BOS",
                         "position": "SG", "projection_index": 1,
                         "availability": "Out"},
                        {"name": "Reserve BOS", "team": "BOS",
                         "position": "PF", "projection_index": None},
                    ],
                },
                "scenario": None, "minute_scenario": None,
            },
        }
        page.evaluate(
            "data => window.postMessage({type:'streamlit:render',args:{payload:data}}, '*')",
            payload,
        )
        page.locator("#hzm-day-input").fill(day)
        page.locator("#hzm-day-input").dispatch_event("change")
        page.locator("#hzm-model-trigger").click()
        page.locator("#hzm-model-option-research_context_v75").click()
        page.locator("#hzm-lab-tab-scenario").click()
        page.wait_for_function(
            "document.querySelector('#hzm-minute-player')?.disabled === false")
        assert page.locator("#hzm-minute-player option").count() == 1
        assert "Test Athlete A" in page.locator("#hzm-minute-player").input_value() or (
            "Test Athlete A" in page.locator("#hzm-minute-player").inner_text()
        )
        assert page.locator("#hzm-minute-run").is_enabled()
        page.locator("#hzm-minute-picker-trigger").click()
        menu = page.locator("#hzm-minute-picker-menu")
        assert menu.is_visible()
        assert page.locator("#hzm-minute-menu-list .hzm-minute-option").count() == 4
        assert page.locator(".hzm-minute-team-title").count() == 2
        # Show both current roster-only athletes and OUT players honestly.
        assert "Reserve NYK" in menu.inner_text()
        assert "Reserve BOS" in menu.inner_text()
        assert "OUT" in menu.inner_text()
        page.locator('[data-hzm-minute-team="home"]').click()
        assert page.locator("#hzm-minute-menu-list .hzm-minute-option").count() == 2
        page.locator('[data-hzm-minute-team="all"]').click()
        page.locator("#hzm-minute-search").fill("Reserve NYK")
        assert page.locator("#hzm-minute-menu-list .hzm-minute-option").count() == 1
        page.locator("#hzm-minute-menu-list .hzm-minute-option").click()
        assert not menu.is_visible()
        assert page.locator("#hzm-minute-run").is_disabled()
        assert "Bez wystarczających danych" in page.locator("#hzm-minute-status").inner_text()
        # Reopening and choosing a verified athlete restores calculations.
        page.locator("#hzm-minute-picker-trigger").click()
        page.locator("#hzm-minute-search").fill("")
        page.locator("#hzm-minute-menu-list .hzm-minute-option").filter(
            has_text="Test Athlete A").click()
        assert page.locator("#hzm-minute-run").is_enabled()
        assert page.locator("#hzm-minute-pts").inner_text() == "PTS: —"
        page.evaluate("""() => {
          window.__minuteEvents = [];
          window.addEventListener('message', e => {
            if(e.data?.type === 'streamlit:setComponentValue' &&
               e.data.value?.type === 'premium_sim_player_minutes')
              window.__minuteEvents.push(e.data.value);
          });
        }""")
        page.locator("#hzm-minute-delta").evaluate(
            """el => {el.value='5';el.dispatchEvent(new Event('input',{bubbles:true}))}"""
        )
        assert page.locator("#hzm-minute-delta-output").inner_text() == "+5 min"
        page.locator("#hzm-minute-run").click()
        page.wait_for_function("window.__minuteEvents.length === 1")
        event = page.evaluate("window.__minuteEvents[0]")
        assert event["model_id"] == "research_context_v75"
        assert event["game_id"] == game_id
        assert event["player_name"] == "Test Athlete A"
        assert event["team"] == "NYK"
        assert event["minute_delta"] == 5

        payload["premium_simulation"]["minute_scenario"] = {
            "date": day, "game_id": game_id,
            "model_id": "research_context_v75",
            "name": "Test Athlete A", "team": "NYK",
            "minute_delta": 5,
            "baseline_minutes": 30.0, "scenario_minutes": 35.0,
            "minutes_sample": 4, "availability": "Questionable",
            "baseline": {"pts": 24.0, "reb": 6.0, "ast": 9.0, "pra": 39.0},
            "scenario": {"pts": 28.0, "reb": 7.0, "ast": 10.5, "pra": 45.5},
        }
        page.evaluate(
            "data => window.postMessage({type:'streamlit:render',args:{payload:data}}, '*')",
            payload,
        )
        assert "30,0 → 35,0" in page.locator("#hzm-minute-minutes").inner_text()
        assert "24,0 → 28,0" in page.locator("#hzm-minute-pts").inner_text()
        assert "39,0 → 45,5" in page.locator("#hzm-minute-pra").inner_text()
        assert "Bez korekty wyniku drużyny" in page.locator("#hzm-minute-status").inner_text()

        # Old model/athlete/scenario must never appear for a changed delta.
        page.locator("#hzm-minute-delta").evaluate(
            """el => {el.value='-2';el.dispatchEvent(new Event('input',{bubbles:true}))}"""
        )
        assert page.locator("#hzm-minute-pts").inner_text() == "PTS: —"
        assert page.locator("#hzm-minute-pra").inner_text() == "PRA: —"

        # Historical ESPN minutes are also usable with the selected V7.4
        # baseline, without substituting V7.5 player projections.
        game["model_id"] = "research_form_v74"
        payload["premium_simulation"]["players"]["model_id"] = "research_form_v74"
        page.locator("#hzm-model-trigger").click()
        page.locator("#hzm-model-option-research_form_v74").click()
        page.evaluate(
            "data => window.postMessage({type:'streamlit:render',args:{payload:data}}, '*')",
            payload,
        )
        assert page.locator("#hzm-minute-run").is_enabled()
        assert page.locator("#hzm-minute-base-pts").inner_text() == "24,0"
        page.locator("#hzm-minute-run").click()
        page.wait_for_function("window.__minuteEvents.length === 2")
        assert page.evaluate("window.__minuteEvents[1].model_id") == "research_form_v74"

        payload["auth"] = {"role": "free"}
        payload["premium_simulation"] = {
            "entitled": False, "game": None, "players": None,
            "scenario": None, "minute_scenario": None,
        }
        page.evaluate(
            "data => window.postMessage({type:'streamlit:render',args:{payload:data}}, '*')",
            payload,
        )
        assert page.locator("#hzm-minute-player").is_disabled()
        assert page.locator("#hzm-minute-picker-trigger").is_disabled()
        assert page.locator("#hzm-minute-picker-menu").is_hidden()
        assert page.locator("#hzm-minute-run").is_disabled()
        assert page.locator("#hzm-minute-pts").inner_text() == "PTS: —"
        assert "Premium" in page.locator("#hzm-minute-status").inner_text()
        assert not errors, errors
        browser.close()
        print("Player Minutes: V7.5 and V7.4, fixture/player identity, OUT and Premium gate OK")


if __name__ == "__main__":
    main()
