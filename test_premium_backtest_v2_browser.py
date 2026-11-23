"""Premium Model & Backtest V2 Chromium regression.
All input data are synthetic fixtures solely for testing browser UI; never
stand-ins for actual NBA evidence or model effectiveness.
"""
from pathlib import Path
from shutil import which
from playwright.sync_api import sync_playwright

from test_results_distributions_premium_browser import fixture

ROOT = Path(__file__).parent
URL = (ROOT / "bestbets_reference_frontend" / "index.html").as_uri()
OUTPUT = ROOT / "test-results" / "backtest-premium-v2"
OUTPUT.mkdir(parents=True, exist_ok=True)


def fake_report():
    return {
        "season": "2026-27",
        "games": 20,
        "max_games": 40,
        "first_game": "2026-10-25",
        "last_game": "2026-11-20",
        "as_of_utc": "2026-11-23T12:00:00Z",
        "limitation": (
            "Weryfikacja offline tylko na ukończonych meczach. "
            "Nie odtworzono historycznej dostępności składów."
        ),
        "models": [
            {"key": "old", "total_mae": 15.4, "team_mae": 10.9,
             "winner_accuracy_pct": 50.0, "brier": 0.2701},
            {"key": "new", "total_mae": 13.7, "team_mae": 9.0,
             "winner_accuracy_pct": 55.0, "brier": 0.2421},
            {"key": "enriched", "total_mae": 11.8, "team_mae": 7.7,
             "winner_accuracy_pct": 60.0, "brier": 0.2204},
            {"key": "v75", "total_mae": 10.1, "team_mae": 7.0,
             "winner_accuracy_pct": 65.0, "brier": 0.2022},
        ],
    }


def main():
    with sync_playwright() as p:
        binary = which("chromium") or which("google-chrome")
        browser = p.chromium.launch(
            headless=True, args=["--no-sandbox"],
            **({"executable_path": binary} if binary else {}),
        )
        for width, height, label in ((1672, 941, "desktop"), (390, 844, "iphone")):
            page = browser.new_page(
                viewport={"width": width, "height": height},
                device_scale_factor=1,
                is_mobile=(width == 390), has_touch=(width == 390),
            )
            errors = []
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.clock.set_fixed_time("2026-11-23T12:00:00Z")
            page.goto(URL, wait_until="load")
            assert page.evaluate("""() => [...document.styleSheets].some(s =>
                (s.href || '').endsWith('/backtest_premium_v2.css'))""")
            nav = page.locator('#hz-mobile-nav [data-page="simulations"]')
            if nav.is_visible():
                nav.click()
            else:
                page.locator('.nav-btn[data-page="simulations"]').click()

            data = fixture()
            data["premium_simulation"]["backtest"] = None
            def push():
                page.evaluate(
                    "d => window.postMessage({type:'streamlit:render',args:{payload:d}}, '*')",
                    data,
                )

            push()
            page.wait_for_function(
                "() => document.querySelector('#hzm-score')?.textContent.includes('115 : 116')"
            )
            page.evaluate("""() => {
                window.__backtestRequests=[];
                window.addEventListener('message', e => {
                    if (e.data?.type === 'streamlit:setComponentValue' &&
                        e.data?.value?.type === 'premium_sim_backtest')
                        window.__backtestRequests.push(e.data.value);
                });
            }""")
            page.locator("#hzm-lab-tab-backtest").click()
            assert page.locator("#hzm-lab-tab-backtest").get_attribute(
                "aria-selected"
            ) == "true"
            assert page.locator("#hzm-backtest-panel").is_visible()
            assert page.locator("#hzm-detail-grid").is_hidden()
            assert page.locator("#hzm-backtest-games").inner_text() == "—"
            assert page.locator("#hzm-backtest-v75-total").inner_text() == "—"
            assert page.locator("#hzm-backtest-run").is_enabled()
            assert page.evaluate("window.__backtestRequests.length") == 0, (
                "No offline research request should run on page load or tab change."
            )
            # The Flow screen is excluded from public navigation until validated.
            assert page.locator("#hzm-lab-tab-flow").is_hidden()
            assert page.locator("#hzm-lab-tab-flow").is_disabled()

            if width == 390:
                m = page.evaluate("""() => {
                    const bounds = s => {
                        const b = document.querySelector(s).getBoundingClientRect();
                        return {left:b.left,right:b.right,width:b.width,height:b.height};
                    };
                    return {
                        native:document.querySelector('#app-shell').classList.contains('hz-mobile-intelligence'),
                        stage:bounds('#stage'),
                        panel:bounds('#hzm-backtest-panel'),
                        row:bounds('.hzm-backtest-model'),
                        heading:bounds('.hzm-backtest-metrics-head'),
                        viewport:document.documentElement.clientWidth,
                        scroll:document.documentElement.scrollWidth
                    };
                }""")
                assert m["native"] and m["stage"]["width"] >= 385, m
                assert m["panel"]["width"] >= 325, m
                assert m["row"]["width"] >= 310, m
                assert m["scroll"] <= m["viewport"] + 2, m
                assert page.locator(".hzm-backtest-metrics-head").is_hidden(), m
                metric = page.locator(".hzm-backtest-model b").first
                assert metric.evaluate(
                    "el => getComputedStyle(el,'::before').content"
                ).strip('"') == "MAE SUMY PTS"
            else:
                assert page.locator(".hzm-backtest-metrics-head").is_visible()

            page.screenshot(path=str(OUTPUT / f"{label}-empty.png"), full_page=True)
            page.locator("#hzm-backtest-run").click()
            page.wait_for_function("() => window.__backtestRequests.length===1")
            assert page.locator("#hzm-backtest-run").is_disabled()
            assert "Analizowanie" in page.locator("#hzm-backtest-status").inner_text()

            # An incomplete/invalid report cannot produce numbers.
            data["premium_simulation"]["backtest"] = {
                "season": "2026-27", "games": 99, "models": fake_report()["models"]
            }
            push()
            assert page.locator("#hzm-backtest-v75-total").inner_text() == "—"
            assert "Niekompletny" in page.locator("#hzm-backtest-status").inner_text()

            data["premium_simulation"]["backtest"] = fake_report()
            push()
            page.wait_for_function(
                "() => document.querySelector('#hzm-backtest-v75-total')?.textContent==='10,1'"
            )
            assert page.locator("#hzm-backtest-games").inner_text() == "20 / 40"
            assert page.locator("#hzm-backtest-season").inner_text() == "2026-27"
            assert page.locator("#hzm-backtest-v75-accuracy").inner_text() == "65,0%"
            assert page.locator("#hzm-backtest-v75-brier").inner_text() == "0,2022"
            assert "Walk-forward gotowy" in page.locator("#hzm-backtest-status").inner_text()
            assert "niedostępny" in page.locator(".hzm-backtest-roi").inner_text().lower()
            assert "nie odtworzono" in page.locator("#hzm-backtest-caveat").inner_text().lower()
            page.screenshot(path=str(OUTPUT / f"{label}-verified-fixture.png"), full_page=True)
            if width == 390:
                diagnostic = page.evaluate("""() => {
                    const sels=['#app-shell','#stage','#work','#simulations-pane',
                        '.hzm-content','.hzm-analysis','#hzm-backtest-panel',
                        '.hzm-backtest-results','#hzm-backtest-caveat'];
                    return {
                        viewport:innerHeight, scroll:document.documentElement.scrollHeight,
                        bodyScroll:document.body.scrollHeight,
                        boxes:sels.map(sel=>{
                            const el=document.querySelector(sel);
                            const r=el.getBoundingClientRect(),css=getComputedStyle(el);
                            return {sel,top:Math.round(r.top),bottom:Math.round(r.bottom),
                                height:Math.round(r.height),scrollHeight:el.scrollHeight,
                                overflow:css.overflow,overflowY:css.overflowY,
                                maxHeight:css.maxHeight,position:css.position}
                        })
                    };
                }""")
                print("Mobile Backtest geometry:", diagnostic)
                page.evaluate("window.scrollTo(0, 1300)")
                assert page.evaluate("window.scrollY") > 500, diagnostic
                page.locator("#hzm-backtest-caveat").scroll_into_view_if_needed()
                box = page.locator("#hzm-backtest-caveat").bounding_box()
                assert box and box["y"] < height - 75, (box, diagnostic)
                page.screenshot(path=str(OUTPUT / "iphone-scrolled-bottom.png"), full_page=False)


            # Traverse all released Premium panes; a tab switch must not hide
            # the other pages' content or leak stale selected state.
            selectors = {
                "intelligence": "#hzm-intel-panel",
                "comparison": "#hzm-compare-panel",
                "scenario": "#hzm-scenario-panel",
                "players": "#hzv3",
                "results": "#hzm-detail-grid",
                "backtest": "#hzm-backtest-panel",
            }
            for view, sel in selectors.items():
                page.locator(f"#hzm-lab-tab-{view}").click()
                assert page.locator(f"#hzm-lab-tab-{view}").get_attribute(
                    "aria-selected"
                ) == "true", view
                assert page.locator(sel).is_visible(), view
                assert page.locator("#simulations-pane").get_attribute(
                    "data-hzm-view"
                ) == view
                if width == 390:
                    assert page.evaluate(
                        "document.querySelector('#app-shell').classList.contains('hz-mobile-intelligence')"
                    ), view

            # Entitlement revocation must clear all backtest metrics.
            data["premium_simulation"] = {
                "entitled": False, "game": None, "players": None,
                "backtest": fake_report(),  # malformed payload must not display it
            }
            data["auth"] = {"role": "free", "configured": True}
            push()
            page.locator("#hzm-lab-tab-backtest").click()
            assert page.locator("#hzm-backtest-games").inner_text() == "—"
            assert page.locator("#hzm-backtest-v75-total").inner_text() == "—"
            assert page.locator("#hzm-backtest-v75-brier").inner_text() == "—"
            assert page.locator("#hzm-backtest-run").is_disabled()
            assert "Premium" in page.locator("#hzm-backtest-status").inner_text()
            assert page.evaluate("window.__backtestRequests.length") == 1
            page.screenshot(path=str(OUTPUT / f"{label}-locked.png"), full_page=True)
            assert not errors, errors
            page.close()
        browser.close()
        print("Backtest V2: no automatic report, validated metrics, ROI disclaimer, "
              "Premium revocation, 6-tab navigation and native mobile layout OK")


if __name__ == "__main__":
    main()
