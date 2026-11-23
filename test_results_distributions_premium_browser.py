"""Results & Distributions V2 Chromium QA. Synthetic fixtures are TEST ONLY."""
from pathlib import Path
from shutil import which
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).parent
URL = (ROOT / "bestbets_reference_frontend" / "index.html").as_uri()
OUT = ROOT / "test-results" / "results-premium-v2"
OUT.mkdir(parents=True, exist_ok=True)


def fixture():
    day = "2026-11-23"
    def dist(avg, start, end):
        return {
            "bins": [{"x": x, "p": 15.0 + (x - start) % 20} for x in range(start, end, 5)],
            "average": avg, "threshold": round(avg / 5) * 5,
            "over_pct": 53.2, "p10": avg - 15, "p90": avg + 15,
        }
    return {
        "brand": "", "auth": {"role": "premium"},
        "home": {
            "calendar_today": day, "calendar_loaded_days": [day],
            "calendar_games": [
                {"id": "401000001", "day": day, "away": "NYK", "home": "IND",
                 "state": "scheduled", "start": "2026-11-23T23:00:00Z"}
            ],
        },
        "premium_simulation": {
            "entitled": True,
            "game": {
                "date": day, "game_id": "401000001", "model_id": "research_form_v74",
                "away_points": 115, "home_points": 116, "total_points": 231,
                "away_win_pct": 48.1, "home_win_pct": 51.9,
                "n_sims": 5000,
                "distributions": {
                    "match": dist(231, 180, 280),
                    "away": dist(115, 80, 150),
                    "home": dist(116, 80, 150),
                },
            },
            "players": {
                "date": day, "game_id": "401000001", "model_id": "research_form_v74",
                "home": "IND", "players": [
                    {"name": "QA Test Player", "team": "IND",
                     "pts": 19.1, "reb": 5.3, "ast": 7.4},
                ],
            },
        },
    }


def test_browser():
    with sync_playwright() as p:
        binary = which("chromium") or which("google-chrome")
        browser = p.chromium.launch(
            headless=True, args=["--no-sandbox"],
            **({"executable_path": binary} if binary else {}),
        )
        for width, height, label in ((1672, 941, "desktop"), (390, 844, "iphone")):
            page = browser.new_page(
                viewport={"width": width, "height": height}, device_scale_factor=1,
                is_mobile=(width == 390), has_touch=(width == 390),
            )
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.clock.set_fixed_time("2026-11-23T12:00:00Z")
            page.goto(URL, wait_until="load")
            css = page.evaluate("""() => [...document.styleSheets].some(s =>
                (s.href || '').endsWith('/results_distributions_premium_v2.css'))""")
            assert css, "Results V2 stylesheet not loaded"
            mobile_nav = page.locator('#hz-mobile-nav [data-page="simulations"]')
            if mobile_nav.is_visible():
                mobile_nav.click()
            else:
                page.locator('.nav-btn[data-page="simulations"]').click()
            data = fixture()
            def push():
                page.evaluate(
                    "d => window.postMessage({type:'streamlit:render',args:{payload:d}}, '*')",
                    data,
                )
            push()
            page.wait_for_function(
                "() => document.querySelector('#hzm-score')?.textContent.includes('115 : 116')"
            )
            assert page.locator("#hzm-lab-tab-results").get_attribute("aria-selected") == "true"
            assert page.locator("#hzm-plot svg").count() == 1
            assert page.locator("#hzm-ou-line").is_enabled()
            assert page.locator("#hzm-chart-tabs button").count() == 3
            style = page.locator("#simulations-pane .hzm-chart-card").evaluate(
                """el => ({
                    background: getComputedStyle(el).backgroundImage,
                    border: getComputedStyle(el).borderTopColor,
                    shadow: getComputedStyle(el).boxShadow
                })"""
            )
            assert "radial-gradient" in style["background"], style
            assert "rgba" in style["shadow"], style
            assert "rgba" in style["border"], style
            tabs = page.locator("#hzm-chart-tabs button")
            for key, team in (("away", "NYK"), ("home", "IND"), ("match", "MECZ")):
                page.locator(f'[data-hzm-chart="{key}"]').click()
                assert page.locator(f'[data-hzm-chart="{key}"]').get_attribute(
                    "aria-pressed"
                ) == "true"
                assert page.locator("#hzm-chart-context").inner_text().startswith(team)
                assert page.locator("#hzm-plot svg").count() == 1
            assert page.locator("#hzm-result-range").count() == 1
            if width == 390:
                measures = page.evaluate("""() => {
                    const rect = q => {
                        const r = document.querySelector(q).getBoundingClientRect();
                        return {width:r.width, height:r.height, left:r.left, right:r.right};
                    };
                    return {
                        root:rect('#stage'),
                        card:rect('.hzm-chart-card'),
                        plot:rect('#hzm-plot'),
                        switcher:rect('#hzm-chart-tabs'),
                        mobile:document.querySelector('#app-shell').classList.contains('hz-mobile-intelligence'),
                        scrollHeight:document.documentElement.scrollHeight,
                        viewport:document.documentElement.clientWidth,
                        horizontalOverflow:document.documentElement.scrollWidth
                    };
                }""")
                assert measures["mobile"], measures
                assert 350 <= measures["root"]["width"] <= 391, measures
                assert measures["card"]["width"] >= 325, measures
                assert measures["plot"]["width"] >= 290, measures
                assert measures["plot"]["height"] >= 200, measures
                assert measures["switcher"]["width"] >= 310, measures
                assert measures["horizontalOverflow"] <= measures["viewport"] + 2, measures
                assert measures["scrollHeight"] > height, measures
                page.evaluate("window.scrollTo(0,document.documentElement.scrollHeight)")
                assert page.evaluate("window.scrollY") > 100
            page.screenshot(path=str(OUT / f"{label}-premium.png"), full_page=True)
            data["premium_simulation"] = {
                "entitled": False, "game": None, "players": None
            }
            data["auth"] = {"role": "free", "configured": True}
            push()
            page.wait_for_function(
                "() => document.querySelector('#hzm-score')?.textContent.includes('— : —')"
            )
            assert page.locator("#hzm-plot svg").count() == 0
            assert "Symulacje wymagają uwierzytelnienia" in page.locator(
                "#hzm-plot"
            ).inner_text()
            assert page.locator("#hzm-lab-range").inner_text() == "Przedział 80%: —"
            assert not errors, errors
            page.screenshot(path=str(OUT / f"{label}-locked.png"), full_page=True)
            page.close()
        browser.close()
        print("Results V2 desktop/mobile styling, chart toggle and Premium data clearance OK")


if __name__ == "__main__":
    test_browser()
