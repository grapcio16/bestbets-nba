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
            page.locator('[data-market="PRA"]').click()
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
                          "role": "admin", "name": "Test Admin"}},
            )
            expect(page.locator("#hz-premium .hz-premium-text")).to_have_text("ADMIN")
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
