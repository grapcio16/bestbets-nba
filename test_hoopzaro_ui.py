"""HOOPZARO 2.0 desktop visual and interaction smoke test.

Uses synthetic example players ONLY in this test, not in the public frontend.
"""
from __future__ import annotations

from base64 import b64encode
from pathlib import Path
from playwright.sync_api import expect, sync_playwright


ROOT = Path(__file__).resolve().parent
DOCUMENT = (ROOT / "bestbets_reference_frontend" / "index.html").as_uri()
BRAND = "data:image/svg+xml;base64," + b64encode(
    (ROOT / "assets" / "hoopzaro.svg").read_bytes()
).decode("ascii")
EXAMPLE_PLAYER = {
    "name": "Test Athlete", "team": "BOS", "position": "SF",
    "opponent": "CHA", "season": "2026-27", "next_game": "",
    "market": "REB", "line": 7.5, "side": "OVER",
    "photo": "", "logo": "", "defense": None, "defense_recent": None,
    "source": "SYNTHETIC TEST DATA (NOT PUBLIC NBA FACTS)",
    "games": [
        {"date": f"2026-11-{day:02d}", "matchup": f"BOS vs. {team}",
         "PTS": 20 + i, "REB": reb, "AST": 3 + i % 5,
         "FG3M": 2, "PRA": 25 + i + reb}
        for i, (day, team, reb) in enumerate(
            [(1, "MIA", 9), (2, "ORL", 7), (3, "CHI", 5), (4, "HOU", 7),
             (5, "NYK", 4), (6, "ORL", 6), (7, "CHA", 8), (8, "MIL", 4),
             (9, "PHI", 6), (10, "TOR", 7)]
        )
    ],
}


def main() -> None:
    with sync_playwright() as tool:
        browser = tool.chromium.launch(headless=True)
        for width, height in [(1800, 900), (1366, 768), (390, 844)]:
            page = browser.new_page(viewport={"width": width, "height": height}, device_scale_factor=1)
            errors: list[str] = []
            page.on("pageerror", lambda exc: errors.append(str(exc)))
            page.goto(DOCUMENT, wait_until="load")
            page.evaluate(
                "payload => window.postMessage({type:'streamlit:render',args:{payload}},'*')",
                {"player": None, "home": {"games": [], "ticker": [], "finals": [],
                 "free_leaders": [], "form": [], "players": [], "source": "NBA/ESPN",
                 "calendar_today": "2026-11-14", "calendar_loaded_days": ["2026-11-14"]},
                 "brand": BRAND, "error": ""},
            )
            page.wait_for_function("document.querySelector('#brand-img').naturalWidth > 0")
            assert page.locator("#brand-img").get_attribute("src") == "hoopzaro.svg"
            assert page.locator("#bestbets-centre").is_visible()
            assert page.locator("#props-heading").is_hidden()
            assert page.locator(".brand .wordmark").inner_text().startswith("HOOPZARO")
            if width < 768:
                # The compact iPhone layout intentionally replaces the
                # desktop bottom tiles with a fixed mobile tab bar.
                assert page.locator(".bc-bottom").is_hidden()
                expect(page.locator("#hz-mobile-nav")).to_be_visible()
            else:
                home_rect = page.locator(".bc-bottom").bounding_box()
                assert home_rect and home_rect["width"] > 100
            if width >= 1300:
                assert home_rect["y"] + home_rect["height"] < height, (width, home_rect)
            if width == 1800:
                page.screenshot(path=str(ROOT / "hoopzaro_centre_smoke.png"))
            props_tab = ('#hz-mobile-nav [data-page="props"]' if width < 768
                         else '.nav-btn[data-page="props"]')
            page.locator(props_tab).click()
            page.evaluate(
                "payload => window.postMessage({type:'streamlit:render',args:{payload}},'*')",
                {"player": EXAMPLE_PLAYER, "home": None, "brand": BRAND, "error": ""},
            )
            page.wait_for_function("document.querySelector('#player-name').textContent==='Test Athlete'")
            assert page.locator("#brand-img").get_attribute("src") == "hoopzaro.svg"
            assert page.locator("#props-heading").is_visible()
            assert page.locator("#chart-svg .bb-plot-bar").count() == 10
            assert page.locator("#hero-rate").inner_text().endswith("%")
            # A background payload refresh must leave the existing SVG bars
            # intact instead of restarting every chart animation.
            page.locator("#chart-svg .bb-plot-bar").first.evaluate(
                "el => el.setAttribute('data-render-probe', 'preserved')"
            )
            page.evaluate(
                "payload => window.postMessage({type:'streamlit:render',args:{payload}},'*')",
                {"player": EXAMPLE_PLAYER, "home": {"games": [], "source": "refreshed"},
                 "brand": BRAND, "error": ""},
            )
            expect(page.locator("#chart-svg .bb-plot-bar").first).to_have_attribute(
                "data-render-probe", "preserved"
            )
            page.locator('[data-market="PRA"]').click()
            # Changing a Props control MUST invalidate the cached chart.
            assert page.locator("#chart-svg .bb-plot-bar").first.get_attribute(
                "data-render-probe"
            ) is None
            # The chart now labels the combined market PRA directly.
            expect_heading = "PRA"
            actual_heading = page.locator("#chart-heading").inner_text()
            assert expect_heading in actual_heading, (
                f"PRA heading={actual_heading!r}, "
                f"market={page.locator('#market').input_value()!r}, "
                f"selected={page.locator('[data-market=PRA]').get_attribute('class')!r}"
            )
            page.locator('[data-market="REB"]').click()
            page.locator("#line-plus").click()
            assert page.locator("#line").input_value() == "8"
            page.locator('[data-side="UNDER"]').click()
            assert "UNDER" in page.locator("#take-text").inner_text()
            if width == 1800:
                page.screenshot(path=str(ROOT / "hoopzaro_props_smoke.png"))
            # Verified administrator sees an explicit ADMIN badge and the
            # Premium shortcut opens real simulation tools, not an upsell.
            page.evaluate(
                "payload => window.postMessage({type:'streamlit:render',args:{payload}},'*')",
                {"player": EXAMPLE_PLAYER, "home": None, "brand": BRAND, "error": "",
                 "auth": {"configured": True, "logged_in": True,
                          "role": "admin", "name": "Test Admin", "session_epoch": 1}},
            )
            expect(page.locator("#hz-premium .hz-premium-text")).to_have_text("ADMIN")
            page.locator("#query").fill("Private search from account A")
            # Even switching between two accounts of the SAME role must
            # discard the previous account's paid chart and search draft.
            page.evaluate(
                "payload => window.postMessage({type:'streamlit:render',args:{payload}},'*')",
                {"player": None, "home": None, "brand": BRAND, "error": "",
                 "auth": {"configured": True, "logged_in": True,
                          "role": "admin", "name": "Another Admin", "session_epoch": 2}},
            )
            expect(page.locator("#player-name")).to_have_text("Wyszukaj zawodnika")
            expect(page.locator("#query")).to_have_value("")
            assert page.locator("#chart-svg .bb-plot-bar").count() == 0
            # Logout must keep the prior results hidden as well.
            page.evaluate(
                "payload => window.postMessage({type:'streamlit:render',args:{payload}},'*')",
                {"player": None, "home": None, "brand": BRAND, "error": "",
                 "auth": {"configured": True, "logged_in": False,
                          "role": "guest", "session_epoch": 3}},
            )
            expect(page.locator("#query")).to_have_value("")
            page.evaluate(
                "payload => window.postMessage({type:'streamlit:render',args:{payload}},'*')",
                {"player": EXAMPLE_PLAYER, "home": None, "brand": BRAND, "error": "",
                 "auth": {"configured": True, "logged_in": True,
                          "role": "admin", "name": "Test Admin", "session_epoch": 4}},
            )
            expect(page.locator("#hz-premium .hz-premium-text")).to_have_text("ADMIN")
            if width == 1800:
                # Administrator can inspect tracker health and filter the
                # saved player-versus-actual audit without changing the model.
                page.locator("#hz-admin-nav").click()
                admin_report = {
                    "season": "2026-27", "models": [{
                        "id": "auto_legacy_v72", "label": "V7.2", "snapshots": 1,
                        "settled": 1, "metrics": {"games": 1}, "recent": [],
                    }],
                    "tracker_monitor": {
                        "last_run_utc": "2026-11-19 16:00", "last_run_age_hours": 1,
                        "stale": False, "last_player_status": "ok",
                        "last_cycle": {"team_new": 2, "team_settled": 4,
                                       "player_new": 20, "player_settled": 10,
                                       "player_games_checked": 1,
                                       "player_games_projected": 1},
                        "team": {"saved": 120, "settled": 90, "pending": 30},
                        "players": {"saved": 44, "settled": 22, "pending": 22},
                    },
                    "player_tracking": {"models": [{
                        "id": "auto_player_form_v74", "saved": 2,
                        "evaluated_players": 1, "games_with_results": 1,
                        "metrics": {
                            "pra": {"n": 1, "mae": 10, "within_pct": 0,
                                    "tolerance": 7},
                            "minutes": {"n": 1, "mae": 3,
                                        "within_pct": 1, "tolerance": 5},
                        },
                        "recent": [
                            {"game_id": "401001234", "date": "2026-11-19 01:00",
                             "player": "Example Starter", "team": "BOS",
                             "opponent": "NYK", "pred": {"pts": 20, "pra": 30,
                                                         "minutes": 30},
                             "actual": {"pts": 25, "pra": 40, "minutes": 33}},
                            {"game_id": "401001234", "date": "2026-11-19 01:00",
                             "player": "Other Guard", "team": "NYK",
                             "opponent": "BOS", "pred": {"pts": 15, "pra": 20},
                             "actual": {"pts": None, "pra": None}},
                        ],
                    }]},
                }
                page.evaluate(
                    "payload => window.postMessage({type:'streamlit:render',args:{payload}},'*')",
                    {"player": None, "home": None, "brand": BRAND, "error": "",
                     "auth": {"role": "admin", "logged_in": True,
                              "session_epoch": 4},
                     "admin_report": admin_report},
                )
                expect(page.locator(".hz-admin-monitor-state")).to_have_text("AKTYWNY")
                expect(page.locator("#hz-admin-player-market option[value='pra']")).to_have_count(1)
                page.locator("#hz-admin-player-market").select_option("pra")
                page.locator("#hz-admin-player-search").fill("Example")
                expect(page.locator("#hz-admin-player-history-rows tr")).to_have_count(1)
                expect(page.locator("#hz-admin-player-history-rows")).to_contain_text("+10,00")
                page.locator("#hz-admin-player-market").select_option("minutes")
                expect(page.locator("#hz-admin-player-history-rows")).to_contain_text("+3,00")
                page.locator("#hz-admin-player-search").fill("Missing athlete")
                expect(page.locator("#hz-admin-player-history-rows")).to_contain_text("Brak zapisów")
            premium_tab = ('#hz-mobile-nav [data-page="simulations"]' if width < 768
                           else '#hz-premium')
            page.locator(premium_tab).click()
            expect(page.locator("#simulations-pane")).to_be_visible()
            assert not errors, errors
            page.close()
        browser.close()
        print("HOOPZARO: Centrum, Player Props, responsive sizing and interactions PASS")


if __name__ == "__main__":
    main()
