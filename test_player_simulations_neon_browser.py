"""Screenshot-matched Player Simulations, real-history semantics, guest gate.

All player names/statistics here are synthetic and never displayed live.
"""
from pathlib import Path
from shutil import which

from playwright.sync_api import sync_playwright

PAGE = (Path(__file__).parent / "bestbets_reference_frontend" / "index.html").as_uri()
OUT = Path("test-results/hoopzaro-responsive")
OUT.mkdir(parents=True, exist_ok=True)


def main():
    with sync_playwright() as p:
        executable = which("chromium") or which("google-chrome")
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"],
                                    **({"executable_path": executable} if executable else {}))
        for width, height in ((1440, 900), (390, 844)):
            page = browser.new_page(viewport={"width": width, "height": height},
                                    device_scale_factor=1)
            page.clock.set_fixed_time("2026-11-21T12:00:00Z")
            errors = []
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.goto(PAGE, wait_until="load")
            mobile = page.locator('#hz-mobile-nav [data-page="simulations"]')
            if mobile.is_visible():
                mobile.click()
            else:
                page.locator('.nav-btn[data-page="simulations"]').click()
            day, game_id = "2026-11-23", "401999600"
            history = [
                {"date": "2026-11-%02d" % (i + 3),
                 "pts": float(18+i), "reb": float(3+i%2),
                 "ast": float(5+i%3), "pra": float(26+i+i%2+i%3)}
                for i in range(7)
            ]
            payload = {
                "brand": "", "auth": {"role": "premium"},
                "home": {"calendar_today": day, "calendar_loaded_days": [day],
                         "calendar_games": [
                             {"id": game_id, "day": day, "away": "MIL",
                              "home": "PHI", "state": "scheduled",
                              "start": "2026-11-23T02:00:00Z"}]},
                "premium_simulation": {
                    "entitled": True,
                    "game": {
                        "date": day, "game_id": game_id, "model_id": "research_form_v74",
                        "away_points": 111.0, "home_points": 120.0,
                        "total_points": 231.0, "away_win_pct": 28.6,
                        "home_win_pct": 71.4, "distributions": {},
                        "n_sims": 5000,
                    },
                    "players": {
                        "date": day, "game_id": game_id, "model_id": "research_form_v74",
                        "home": "PHI", "players": [
                            {"name": "Test Guard Alpha", "team": "PHI",
                             "pts": 20, "reb": 2.4, "ast": 6.5,
                             "position": "PG", "espn_id": "",
                             "history": history},
                            {"name": "Test Forward Beta", "team": "MIL",
                             "pts": 17, "reb": 7.5, "ast": 3.2,
                             "espn_id": "", "history": []},
                        ],
                    },
                },
            }
            def push():
                page.evaluate(
                    "d => window.postMessage({type:'streamlit:render',args:{payload:d}}, '*')",
                    payload)
            push()
            page.locator("#hzm-day-input").fill(day)
            page.locator("#hzm-day-input").dispatch_event("change")
            page.locator("#hzm-lab-tab-players").click()
            panel = page.locator("#hzm-players-panel")
            assert panel.is_visible()
            assert page.locator("#hzm-player-analytics").is_visible()
            assert page.locator("#hzm-player-inspector").is_visible()
            assert page.locator("#hzm-player-list-wrap").is_visible()
            assert page.locator("#hzm-player-version").inner_text() == "V7.4"
            assert page.locator(".hzm-player-row-rich").count() == 2
            assert "Test Guard Alpha" in page.locator("#hzm-player-inspector").inner_text()
            assert page.locator("#hzm-player-histogram svg").count() == 1
            assert page.locator("#hzm-player-trend svg").count() == 1
            # Geometry matters: the first release overflowed the left card
            # down onto the three evidence tiles. Compare real rectangles,
            # not only whether elements exist in the DOM.
            layout = page.evaluate("""() => {
                const rect = selector => {
                    const el = document.querySelector(selector);
                    const r = el.getBoundingClientRect();
                    return {top:r.top, bottom:r.bottom, height:r.height,
                            scrollHeight:el.scrollHeight, clientHeight:el.clientHeight};
                };
                return {
                    inspector:rect('#hzm-player-inspector'),
                    roster:rect('#hzm-player-list-wrap'),
                    charts:rect('#hzm-player-analytics'),
                    footer:rect('#simulations-pane .hzm-insights'),
                };
            }""")
            if width >= 1261:
                assert abs(layout["inspector"]["top"]-layout["roster"]["top"]) < 9, layout
                assert abs(layout["roster"]["top"]-layout["charts"]["top"]) < 9, layout
                assert abs(layout["inspector"]["height"]-layout["roster"]["height"]) < 9, layout
                assert abs(layout["roster"]["height"]-layout["charts"]["height"]) < 9, layout
            assert layout["footer"]["top"] >= max(
                layout["inspector"]["bottom"],
                layout["roster"]["bottom"],
                layout["charts"]["bottom"]) - 9, layout
            assert "7 meczów" in page.locator("#hzm-player-rates-source").inner_text()
            assert "—" in page.locator("#hzm-player-averages").inner_text(), "L10/L15 must be hidden with only 7 ESPN games"
            assert "20,0" in page.locator(".hzm-inspector-metric.current").inner_text()
            assert "Minuty Minuty" not in page.locator("#hzm-player-inspector").inner_text()
            assert page.locator("[data-hzm-player-market]").count() == 4
            page.locator('[data-hzm-player-market="REB"]').click()
            assert page.locator("#hzm-player-rate-metric").inner_text() == "REB"
            assert "2,4" in page.locator(".hzm-inspector-metric.current").inner_text()
            assert page.locator('[data-hzm-player-market="REB"]').get_attribute("aria-pressed") == "true"
            page.locator('[data-hzm-history-window="10"]').click()
            assert page.locator('[data-hzm-history-window="10"]').get_attribute("aria-pressed") == "true"
            assert page.locator("#hzm-player-trend svg").count() == 1

            page.screenshot(path=str(OUT / f"player-simulations-neon-{width}x{height}.png"))
            payload["premium_simulation"] = {"entitled": False, "game": None, "players": None}
            payload["auth"] = {"role": "free"}
            push()
            assert page.locator("#hzm-player-rows .hzm-player-row").count() == 0
            assert "Test Guard Alpha" not in page.locator("#hzm-player-inspector").inner_text()
            assert page.locator("#hzm-player-histogram svg").count() == 0
            assert "Premium" in page.locator("#hzm-player-rows").inner_text()
            assert not errors, (width, height, errors)
            page.close()
        browser.close()
    print("Player Simulations neon parity, real L5, PTS/REB toggle, responsive and guest isolation OK")


if __name__ == "__main__":
    main()
