"""Injury Watch: fresh ESPN reports independent of the selected model.
All NBA players and injury numbers here are synthetic regression fixtures.
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

        day, game_id = "2026-11-23", "401999456"
        fixture = {
            "id": game_id, "day": day, "away": "NYK", "home": "BOS",
            "state": "scheduled", "start": "2026-11-23T01:00:00Z",
        }
        game = {
            "date": day, "game_id": game_id, "model_id": "research_context_v75",
            "away_points": 112.0, "home_points": 116.0,
            "total_points": 228.0, "away_win_pct": 46, "home_win_pct": 54,
            "distributions": {}, "n_sims": 5000,
            "model_context": {"v75_factors": {
                "injuries_espn_fresh": True,
                "injury_away_pts": 0.0, "injury_home_pts": -1.2,
                "injury_out_away": 0, "injury_out_home": 1,
            }},
        }
        players = {
            "date": day, "game_id": game_id,
            "model_id": "research_context_v75",
            "home": "BOS",
            "injury_report_fresh": True,
            "injury_report_valid_until": "2026-11-21T13:00:00+00:00",
            "injury_watch": {
                "fresh": True, "checked_at": "2026-11-21T12:00:00+00:00",
                "valid_until": "2026-11-21T13:00:00+00:00",
                "rows": [
                    {"name": "Synthetic Guard", "team": "NYK", "status": "Questionable"},
                    {"name": "Synthetic Forward", "team": "BOS", "status": "Out"},
                    {"name": "Synthetic Probable", "team": "BOS", "status": "Probable"},
                ],
            },
            "players": [
                {"name": "Synthetic Guard", "team": "NYK",
                 "availability": "Questionable", "minutes": 28.0,
                 "minutes_sample": 6, "pts": 20, "reb": 3, "ast": 6},
                {"name": "Synthetic Forward", "team": "BOS",
                 "availability": "Out", "minutes": 0.0,
                 "minutes_sample": 5, "pts": None, "reb": None, "ast": None},
                {"name": "Synthetic Reserve", "team": "NYK",
                 "availability": "Niezweryfikowany", "minutes": 16.0,
                 "minutes_sample": 4, "pts": 5, "reb": 2, "ast": 1},
                {"name": "Synthetic Probable", "team": "BOS",
                 "availability": "Probable", "minutes": 22.0,
                 "minutes_sample": 4, "pts": 10, "reb": 3, "ast": 3},
            ],
        }
        payload = {
            "brand": "", "auth": {"role": "premium"},
            "home": {
                "calendar_today": day, "calendar_loaded_days": [day],
                "calendar_games": [fixture],
            },
            "premium_simulation": {
                "entitled": True, "game": game,
                "players": players, "scenario": None,
                "minute_scenario": None,
            },
        }
        def render():
            page.evaluate(
                "data => window.postMessage({type:'streamlit:render',args:{payload:data}}, '*')",
                payload,
            )

        render()
        page.locator("#hzm-day-input").fill(day)
        page.locator("#hzm-day-input").dispatch_event("change")
        page.locator("#hzm-model-trigger").click()
        page.locator("#hzm-model-option-research_context_v75").click()
        page.locator("#hzm-lab-tab-scenario").click()
        assert page.locator("#hzm-availability-panel").is_visible()
        assert "ESPN · POBRANO" in page.locator("#hzm-availability-freshness").inner_text()
        assert page.locator("#hzm-availability-away-code").inner_text() == "NYK"
        assert page.locator("#hzm-availability-home-code").inner_text() == "BOS"
        assert page.locator("#hzm-availability-away-count").inner_text() == "OUT 0 · INNE 1"
        assert page.locator("#hzm-availability-home-count").inner_text() == "OUT 1 · INNE 1"
        assert "Synthetic Guard" in page.locator("#hzm-availability-away-list").inner_text()
        assert "Synthetic Forward" in page.locator("#hzm-availability-home-list").inner_text()
        assert "Synthetic Probable" in page.locator("#hzm-availability-home-list").inner_text()
        assert "Synthetic Reserve" not in page.locator("#hzm-availability-away-list").inner_text()
        assert "-1,2 pkt" in page.locator("#hzm-availability-home-impact").inner_text()
        assert "OUT uwzględnione: 1" in page.locator("#hzm-availability-home-impact").inner_text()

        # Expired ESPN source data must not stay visible just because the
        # server response was cached and the fixture identity is unchanged.
        players["injury_watch"]["valid_until"] = "2026-11-21T11:59:00+00:00"
        render()
        assert "BRAK ŚWIEŻEGO" in page.locator("#hzm-availability-freshness").inner_text()
        assert "Synthetic Forward" not in page.locator("#hzm-availability-home-list").inner_text()
        assert page.locator("#hzm-availability-home-count").inner_text() == "—"
        assert page.locator("#hzm-availability-home-impact").inner_text().endswith("—")

        # V7.5 factor validity and separately fetched ESPN report are distinct.
        players["injury_watch"]["valid_until"] = "2026-11-21T13:00:00+00:00"
        game["model_context"]["v75_factors"]["injuries_espn_fresh"] = False
        render()
        assert "Synthetic Forward" in page.locator("#hzm-availability-home-list").inner_text()
        assert "korekta OUT niedostępna" in page.locator("#hzm-availability-home-impact").inner_text()

        # Switch to V7.4 and keep report informational only.
        game["model_context"]["v75_factors"]["injuries_espn_fresh"] = True
        game["model_id"] = "research_form_v74"
        players["model_id"] = "research_form_v74"
        page.locator("#hzm-model-trigger").click()
        page.locator("#hzm-model-option-research_form_v74").click()
        render()
        assert "Synthetic Forward" in page.locator("#hzm-availability-home-list").inner_text()
        assert "brak korekty prognozy" in page.locator("#hzm-availability-home-impact").inner_text()
        game["model_id"] = "research_context_v75"
        players["model_id"] = "research_context_v75"

        payload["premium_simulation"] = {
            "entitled": False, "game": None,
            "players": None, "scenario": None, "minute_scenario": None,
        }
        payload["auth"] = {"role": "free"}
        render()
        assert "Premium" in page.locator("#hzm-availability-message").inner_text()
        assert "Synthetic Guard" not in page.locator("#hzm-availability-away-list").inner_text()
        assert "Synthetic Forward" not in page.locator("#hzm-availability-home-list").inner_text()
        assert "—" in page.locator("#hzm-availability-home-impact").inner_text()
        assert not errors, errors
        browser.close()
        print("Injury Watch: source freshness, cross-model display, V7.5 context, Premium access OK")


if __name__ == "__main__":
    main()
