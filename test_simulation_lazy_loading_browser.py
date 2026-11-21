"""Premium Simulation Lab request budget and stale fixture switching regression.

Synthetic fixtures only. Verify no player data fetch on team-only views,
no selected-game compute on Backtest, and correct refetch when returning
to a fixture previously visited.
"""
from pathlib import Path
from shutil import which

from playwright.sync_api import sync_playwright

PAGE = (Path(__file__).parent / "bestbets_reference_frontend" / "index.html").as_uri()


def main():
    with sync_playwright() as p:
        executable = which("chromium") or which("google-chrome")
        browser = p.chromium.launch(
            headless=True, args=["--no-sandbox"],
            **({"executable_path": executable} if executable else {}))
        page = browser.new_page(viewport={"width": 1231, "height": 691})
        page.clock.set_fixed_time("2026-11-21T12:00:00Z")
        errors = []
        page.on("pageerror", lambda exc: errors.append(str(exc)))
        page.goto(PAGE, wait_until="load")
        page.locator('.nav-btn[data-page="simulations"]').click()
        page.evaluate("""() => {
          window.__premiumLoadEvents=[];
          window.addEventListener('message', e => {
            if (e.data?.type!=='streamlit:setComponentValue') return;
            const value=e.data.value;
            if (['premium_sim_game','premium_sim_players','premium_sim_backtest'].includes(value?.type))
              window.__premiumLoadEvents.push(value);
          });
        }""")
        day = "2026-11-21"
        first = {"id": "401992001", "day": day, "away": "NYK", "home": "BOS",
                 "state": "scheduled", "start": "2026-11-23T01:00:00Z"}
        second = {"id": "401992002", "day": day, "away": "LAL", "home": "GSW",
                  "state": "scheduled", "start": "2026-11-23T04:00:00Z"}

        def game_result(game):
            return {
                "date": day, "game_id": game["id"], "model_id": "research_form_v74",
                "away_points": 111.0, "home_points": 114.0,
                "total_points": 225.0, "away_win_pct": 45.0,
                "home_win_pct": 55.0, "distributions": {}, "n_sims": 5000,
                "model_context": {"source": "ESPN"},
            }

        payload = {
            "brand": "", "auth": {"role": "premium"},
            "home": {
                "calendar_today": day, "calendar_loaded_days": [day],
                "calendar_games": [first, second],
            },
            "premium_simulation": {
                "entitled": True, "game": None, "players": None,
                "scenario": None, "minute_scenario": None, "backtest": None,
            },
        }

        def push():
            page.evaluate(
                "data => window.postMessage({type:'streamlit:render',args:{payload:data}}, '*')",
                payload,
            )

        def requests(kind):
            return page.evaluate(
                "type => window.__premiumLoadEvents.filter(e=>e.type===type).map(e=>e.game_id)",
                kind,
            )

        push()
        page.wait_for_function(
            "() => window.__premiumLoadEvents.some(e=>e.type==='premium_sim_game')")
        assert requests("premium_sim_game") == [first["id"]]
        assert requests("premium_sim_players") == []

        # Enter Backtest before any game finished loading. Switching fixtures
        # should never trigger match or player model computations.
        page.locator("#hzm-lab-tab-backtest").click()
        page.locator("#hzm-match-picker").click()
        page.locator(f"#hzm-matches [data-hzm-game='{second['id']}']").click()
        assert requests("premium_sim_game") == [first["id"]]
        assert requests("premium_sim_players") == []
        assert requests("premium_sim_backtest") == []

        # Analysis requires the match summary but NOT costly player projections.
        page.locator("#hzm-lab-tab-intelligence").click()
        page.wait_for_function(
            "() => window.__premiumLoadEvents.filter(e=>e.type==='premium_sim_game').length===2")
        assert requests("premium_sim_game") == [first["id"], second["id"]]
        assert requests("premium_sim_players") == []
        payload["premium_simulation"]["game"] = game_result(second)
        push()
        page.locator("#hzm-lab-tab-comparison").click()
        assert requests("premium_sim_players") == []

        # Entering Player Simulations fetches the roster exactly once.
        page.locator("#hzm-lab-tab-players").click()
        page.wait_for_function(
            "() => window.__premiumLoadEvents.filter(e=>e.type==='premium_sim_players').length===1")
        assert requests("premium_sim_players") == [second["id"]]
        page.locator("#hzm-lab-tab-results").click()
        page.locator("#hzm-lab-tab-players").click()
        assert requests("premium_sim_players") == [second["id"]]

        # Re-selecting fixture one resets old in-flight request keys. When
        # the correct game summary arrives, its roster may be fetched anew.
        page.locator("#hzm-match-picker").click()
        page.locator(f"#hzm-matches [data-hzm-game='{first['id']}']").click()
        page.wait_for_function(
            "() => window.__premiumLoadEvents.filter(e=>e.type==='premium_sim_game').length===3")
        assert requests("premium_sim_game")[-1] == first["id"]
        payload["premium_simulation"]["game"] = game_result(first)
        push()
        page.wait_for_function(
            "() => window.__premiumLoadEvents.filter(e=>e.type==='premium_sim_players').length===2")
        assert requests("premium_sim_players") == [second["id"], first["id"]]

        # Guest users cannot cause another Premium fetch on any tab.
        before = page.evaluate("window.__premiumLoadEvents.length")
        payload["auth"] = {"role": "free"}
        payload["premium_simulation"] = {
            "entitled": False, "game": None, "players": None,
            "scenario": None, "minute_scenario": None, "backtest": None,
        }
        push()
        page.locator("#hzm-lab-tab-scenario").click()
        page.locator("#hzm-lab-tab-comparison").click()
        page.locator("#hzm-lab-tab-results").click()
        assert page.evaluate("window.__premiumLoadEvents.length") == before
        assert page.locator("#hzm-score").inner_text() == "— : —"
        assert not errors, errors
        browser.close()
        print("Lazy Premium: no eager player/backtest loads; correct fixture re-fetch and free gate OK")


if __name__ == "__main__":
    main()
