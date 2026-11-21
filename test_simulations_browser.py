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
        # Keep the synthetic fixture date stable independently of runner date.
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
                "game": {"date": day, "game_id": "40100000", "away": "NYK", "home": "IND",
                         "model_id":"research_form_v74", "away_win_pct": 48.1, "home_win_pct": 51.9,
                         "away_points": 115, "home_points": 116,
                         "total_points": 231, "distributions": distributions,
                         "n_sims": 5000},
                "players": {"date": day, "game_id": "40100000", "home": "IND", "model_id":"research_form_v74",
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
        assert page.locator(".hzm-lab-subtitle").inner_text() == "Simulation Lab 2.0"
        assert page.locator("#hzm-lab-nav button:disabled").count()==0
        assert page.locator("#hzm-lab-tab-backtest").is_enabled()
        assert page.locator("#hzm-lab-tab-comparison").is_enabled()
        assert page.locator("#hzm-lab-tab-intelligence").is_enabled()
        assert page.locator("#hzm-lab-tab-scenario").is_enabled()
        assert page.locator("#hzm-lab-tab-results").get_attribute("aria-selected")=="true"
        assert "216,0" in page.locator("#hzm-lab-range").inner_text()
        assert page.locator("#hzm-match-list").is_hidden()
        page.locator("#hzm-match-picker").click()
        assert page.locator("#hzm-match-list").is_visible()
        assert page.locator("#hzm-match-picker").get_attribute("aria-expanded")=="true"
        assert page.locator("#hzm-match-list button").count()==4
        page.locator("#hzm-matches [data-hzm-game='40100000']").click()
        assert page.locator("#hzm-match-list").is_hidden()
        assert page.locator("#hzm-match-picker").get_attribute("aria-expanded")=="false"
        assert page.locator("#hzm-score").inner_text() == "115 : 116"
        page.locator("#hzm-lab-tab-players").click()
        assert page.locator("#hzm-lab-tab-players").get_attribute("aria-selected")=="true"
        assert page.locator(".hzm-chart-card").is_hidden()
        assert page.locator(".hzm-player-focused-note").is_visible()
        assert page.locator("#hzm-player-rows .hzm-player-row").count()==14
        assert page.locator("#hzm-player-inspector").is_visible()
        assert "Test Player 0" in page.locator("#hzm-player-inspector").inner_text()
        assert "36,9" in page.locator(".hzm-inspector-metric.pra").inner_text()
        assert "brak zweryfikowanego szacunku" in page.locator("#hzm-player-inspector").inner_text()
        # Team filtering and a specific athlete name must narrow the real
        # Premium payload, not display the previous team's projections.
        page.locator('[data-hzm-player-team="away"]').click()
        assert page.locator("#hzm-player-rows .hzm-player-row").count()==7
        assert page.locator("#hzm-player-count").inner_text()=="7 z 14 zawodników"
        page.locator("#hzm-player-search").fill("Test Player 13")
        assert page.locator("#hzm-player-rows .hzm-player-row").count()==1
        assert "Test Player 13" in page.locator("#hzm-player-inspector").inner_text()
        assert "29,1" in page.locator(".hzm-inspector-metric.pra").inner_text()
        page.locator("#hzm-player-rows .hzm-player-row").first.click()
        assert page.locator("#hzm-player-rows .hzm-player-row").first.get_attribute("aria-pressed")=="true"
        page.locator("#hzm-player-search").fill("")
        page.locator('[data-hzm-player-team="all"]').click()
        assert page.locator("#hzm-player-rows .hzm-player-row").count()==14
        page.locator("#hzm-lab-tab-results").click()
        assert page.locator(".hzm-chart-card").is_visible()
        assert page.locator("#hzm-score").inner_text() == "115 : 116"
        assert page.locator("#hzm-plot svg").count() == 1
        tabs = page.locator("#hzm-chart-tabs button")
        assert [tabs.nth(i).inner_text() for i in range(3)] == ["MECZ", "NYK", "IND"]
        page.locator("#hzm-expand-players").click()
        assert page.locator("#hzm-player-rows .hzm-player-row").count() == 14
        assert page.locator("#hzm-expand-players").get_attribute("aria-expanded") == "true"
        assert page.locator("#hzm-players-panel").bounding_box()["height"] >= 400
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
        assert page.locator("#hzm-lab-range").inner_text()=="Przedział 80%: —"
        page.locator("#hzm-lab-tab-players").click()
        assert page.locator("#hzm-player-rows .hzm-player-row").count()==0
        assert "Premium" in page.locator("#hzm-player-rows").inner_text()
        assert "subskrypcji" in page.locator("#hzm-player-rows").inner_text()
        assert "Test Player" not in page.locator("#hzm-player-rows").inner_text()
        assert "Test Player" not in page.locator("#hzm-player-inspector").inner_text()
        assert "Premium" in page.locator("#hzm-player-inspector").inner_text()
        page.locator("#hzm-lab-tab-results").click()
        assert page.locator("#hzm-score").inner_text()=="— : —"
        assert not errors, errors
        browser.close()
        print("Premium simulations: browser layout, dynamic tabs, expanded players and paywall OK")
        print("Screenshot:", SCREENSHOT)


if __name__ == "__main__":
    main()
