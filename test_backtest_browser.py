"""UI-only synthetic fixtures for on-demand Premium walk-forward report."""
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
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(PAGE, wait_until="load")
        page.locator('.nav-btn[data-page="simulations"]').click()
        day, game_id = "2026-11-23", "401999499"
        payload = {
            "brand": "", "auth": {"role": "premium"},
            "home": {
                "calendar_today": day, "calendar_loaded_days": [day],
                "calendar_games": [
                    {"id": game_id, "day": day, "away": "NYK", "home": "BOS",
                     "state": "scheduled", "start": "2026-11-23T01:00:00Z"}
                ],
            },
            "premium_simulation": {
                "entitled": True, "game": None, "players": None,
                "scenario": None, "minute_scenario": None, "backtest": None,
            },
        }
        def push():
            page.evaluate(
                "d => window.postMessage({type:'streamlit:render',args:{payload:d}}, '*')",
                payload)
        push()
        page.locator("#hzm-day-input").fill(day)
        page.locator("#hzm-day-input").dispatch_event("change")
        page.evaluate("""() => {
            window.__backtestEvents = [];
            window.addEventListener('message', e => {
              if(e.data?.type==='streamlit:setComponentValue' &&
                 e.data.value?.type==='premium_sim_backtest')
                window.__backtestEvents.push(e.data.value);
            });
        }""")
        page.locator("#hzm-lab-tab-backtest").click()
        assert page.locator("#hzm-backtest-panel").is_visible()
        assert page.locator("#hzm-backtest-games").inner_text() == "—"
        assert page.locator("#hzm-backtest-run").is_enabled()
        assert page.evaluate("window.__backtestEvents.length") == 0
        page.locator("#hzm-backtest-run").click()
        page.wait_for_function("window.__backtestEvents.length===1")
        assert page.locator("#hzm-backtest-run").is_disabled()
        event = page.evaluate("window.__backtestEvents[0]")
        assert event["type"] == "premium_sim_backtest"
        assert "season" not in event and "games" not in event

        payload["premium_simulation"]["backtest"] = {
            "season": "2026-27", "games": 30, "max_games": 40,
            "first_game": "2026-10-30", "last_game": "2026-11-20",
            "as_of_utc": "2026-11-21T12:00:00+00:00",
            "roi_available": False, "odds_available": False,
            "models": [
                {"key": "old", "total_mae": 14.6, "team_mae": 10.4,
                 "winner_accuracy_pct": 55.0, "brier": .2433},
                {"key": "new", "total_mae": 13.6, "team_mae": 9.4,
                 "winner_accuracy_pct": 60.0, "brier": .2367},
                {"key": "enriched", "total_mae": 12.6, "team_mae": 8.4,
                 "winner_accuracy_pct": 63.3, "brier": .2201},
                {"key": "v75", "total_mae": 12.3, "team_mae": 8.1,
                 "winner_accuracy_pct": 63.3, "brier": .2198},
            ],
            "limitation": "Offline research, not full production V7.5.",
        }
        push()
        assert page.locator("#hzm-backtest-season").inner_text() == "2026-27"
        assert page.locator("#hzm-backtest-games").inner_text() == "30 / 40"
        assert "2026-10-30" in page.locator("#hzm-backtest-range").inner_text()
        assert page.locator("#hzm-backtest-old-total").inner_text() == "14,6"
        assert page.locator("#hzm-backtest-new-team").inner_text() == "9,4"
        assert page.locator("#hzm-backtest-enriched-accuracy").inner_text() == "63,3%"
        assert page.locator("#hzm-backtest-v75-brier").inner_text() == "0,2198"
        assert "production V7.5" in page.locator("#hzm-backtest-caveat").inner_text()
        assert "niedostępny" in page.locator(".hzm-backtest-roi").inner_text().lower() or (
            "niedostępne" in page.locator(".hzm-backtest-roi").inner_text().lower()
        )

        # Free users cannot request a test or see the cached paid report.
        payload["auth"] = {"role": "free"}
        payload["premium_simulation"] = {
            "entitled": False, "game": None, "players": None,
            "scenario": None, "minute_scenario": None, "backtest": None,
        }
        push()
        assert page.locator("#hzm-backtest-run").is_disabled()
        assert page.locator("#hzm-backtest-games").inner_text() == "—"
        assert page.locator("#hzm-backtest-v75-brier").inner_text() == "—"
        assert "Premium" in page.locator("#hzm-backtest-status").inner_text()
        assert not errors, errors
        browser.close()
        print("Premium walk-forward: on-demand click, research metrics and guest isolation OK")


if __name__ == "__main__":
    main()
