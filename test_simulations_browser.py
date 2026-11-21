"""Visual smoke for Premium simulations; synthetic data exists only in this test."""
from pathlib import Path
from shutil import which
from playwright.sync_api import sync_playwright

PAGE = (Path(__file__).parent / "bestbets_reference_frontend" / "index.html").as_uri()
SCREENSHOT = Path("/tmp/hoopzaro-premium-simulations-smoke.png")


def main():
    with sync_playwright() as tool:
        executable = which("chromium") or which("google-chrome")
        options = {"executable_path": executable} if executable else {}
        browser = tool.chromium.launch(headless=True, args=["--no-sandbox"], **options)
        page = browser.new_page(viewport={"width": 1231, "height": 691}, device_scale_factor=1)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        # Keep the synthetic November fixture independent of the runner date.
        page.clock.set_fixed_time("2026-11-14T12:00:00Z")
        page.goto(PAGE, wait_until="load")
        page.locator('.nav-btn[data-page="simulations"]').click()
        assert page.locator("#simulations-pane").is_visible()

        day = "2026-11-14"
        fixtures = [
            {"id": f"4010000{i}", "day": day, "away": a, "home": h,
             "state": "scheduled", "start": f"{day}T{2+i:02d}:00:00Z"}
            for i, (a, h) in enumerate((("NYK", "IND"), ("LAL", "GSW"),
                                         ("BOS", "MIA"), ("DEN", "NOP")))
        ]
        players = [
            {"name": f"Test Player {i}", "team": "NYK" if i % 2 else "IND",
             "pts": 26.1-i*.8, "reb": 6.7+i*.1, "ast": 4.1+i*.1}
            for i in range(14)
        ]
        distributions = {
            k: {"bins": [{"x": j, "p": 25/(1+abs(j-mean)/8)} for j in range(start, end, 5)],
                "average": mean, "threshold": round(mean/5)*5, "over_pct": 53.2,
                "p10": mean-15, "p90": mean+15}
            for k, start, end, mean in (("match", 185, 280, 231),
                                        ("away", 80, 150, 115), ("home", 80, 150, 116))
        }
        payload = {
            "brand": "",
            "home": {"calendar_today": day, "calendar_loaded_days": [day],
                     "calendar_games": fixtures, "calendar_extras": {}},
            "premium_simulation": {
                "entitled": True,
                "game": {"model_id": "research_form_v74", "date": day, "game_id": "40100000", "away": "NYK", "home": "IND",
                         "away_win_pct": 48.1, "home_win_pct": 51.9,
                         "away_points": 115, "home_points": 116,
                         "total_points": 231, "distributions": distributions,
                         "n_sims": 5000},
                "players": {"model_id": "research_form_v74", "date": day, "game_id": "40100000", "home": "IND",
                            "players": players},
            },
        }
        page.evaluate(
            "data => window.postMessage({type:'streamlit:render',args:{payload:data}}, '*')",
            payload,
        )
        page.wait_for_function("document.querySelectorAll('#hzm-matches button').length===4")
        assert page.locator("#hzm-score").inner_text() == "115 : 116"
        assert page.locator("#hzm-player-rows .hzm-player-row").count() == 4
        assert page.locator("#hzm-plot svg").count() == 1
        tabs = page.locator("#hzm-chart-tabs button")
        assert [tabs.nth(i).inner_text() for i in range(3)] == ["MECZ", "NYK", "IND"]
        page.locator("#hzm-expand-players").click()
        assert page.locator("#hzm-player-rows .hzm-player-row").count() == 14
        assert page.locator("#hzm-expand-players").get_attribute("aria-expanded") == "true"
        assert page.locator("#hzm-players-panel").bounding_box()["height"] > 400
        page.screenshot(path=str(SCREENSHOT), full_page=True)
        assert not errors, errors

        payload["premium_simulation"] = {"entitled": False, "game": None, "players": None}
        page.evaluate(
            "data => window.postMessage({type:'streamlit:render',args:{payload:data}}, '*')",
            payload,
        )
        assert "—" in page.locator("#hzm-score").inner_text()
        assert page.locator("#hzm-player-rows .hzm-player-row").count() == 0
        assert "Premium" in page.locator("#hzm-plot").inner_text()
        assert not errors, errors
        browser.close()
        print("Premium simulations: browser layout, dynamic tabs, expanded players and paywall OK")
        print("Screenshot:", SCREENSHOT)


if __name__ == "__main__":
    main()
