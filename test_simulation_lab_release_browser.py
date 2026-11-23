"""Hoopzaro Simulation Lab final integrated acceptance smoke.

All fixtures are synthetic and remain only inside Chromium QA.
This verifies UI state, not model predictive accuracy or licensing approval.
"""
from pathlib import Path
from shutil import which

from playwright.sync_api import sync_playwright

from test_results_distributions_premium_browser import fixture

ROOT = Path(__file__).parent
PAGE = (ROOT / "bestbets_reference_frontend" / "index.html").as_uri()
OUT = ROOT / "test-results" / "simulation-lab-final"
OUT.mkdir(parents=True, exist_ok=True)

SCREENS = {
    "results": "#hzm-detail-grid",
    "players": "#hzv3",
    "scenario": "#hzm-scenario-panel",
    "intelligence": "#hzm-intel-panel",
    "comparison": "#hzm-compare-panel",
    "backtest": "#hzm-backtest-panel",
}
CSS_FILES = [
    "match_intelligence_premium.css",
    "team_comparison_premium.css",
    "scenario_builder_premium_v2.css",
    "player_simulations_premium_v4.css",
    "results_distributions_premium_v2.css",
    "backtest_premium_v2.css",
]


def geometry(page, selector):
    return page.locator(selector).evaluate(
        """el => {
            const r=el.getBoundingClientRect();
            return {width:r.width,height:r.height,left:r.left,right:r.right,
                    top:r.top,bottom:r.bottom, scrollHeight:el.scrollHeight};
        }"""
    )


def check_visitor_gate(page, data):
    data["premium_simulation"] = {
        "entitled": False, "game": None, "players": None,
        "backtest": {
            # Malicious/untrusted payload should never surface without entitlement.
            "season": "2026-27", "games": 18,
            "models": [{
                "key": "v75", "total_mae": 0.1, "team_mae": 0.1,
                "winner_accuracy_pct": 100.0, "brier": 0.0,
            }],
        },
    }
    data["auth"] = {"role": "free", "configured": True}
    page.evaluate(
        "payload => window.postMessage({type:'streamlit:render',args:{payload}}, '*')",
        data,
    )
    page.wait_for_function(
        "() => document.querySelector('#hzm-score')?.textContent.includes('— : —')"
    )
    assert page.locator("#hzm-hero-away-points").inner_text() == "—"
    assert page.locator("#hzm-hero-home-points").inner_text() == "—"
    assert page.locator("#hzm-lab-tab-flow").is_hidden()
    assert page.locator("#hzm-lab-tab-flow").is_disabled()
    for view, panel in SCREENS.items():
        page.locator(f"#hzm-lab-tab-{view}").click()
        assert page.locator(panel).is_visible(), view
        if view == "results":
            assert page.locator("#hzm-plot svg").count() == 0
            assert "Premium" in page.locator("#hzm-plot").inner_text()
        elif view == "players":
            assert page.locator("#hzv3-roster .hzv3-player").count() == 0
            assert "QA Test Player" not in page.locator("#hzv3-inspector").inner_text()
        elif view == "scenario":
            assert page.locator("#hzm-scenario-whatif").inner_text() == "—"
        elif view == "intelligence":
            assert page.locator("#hzm-intel-away-scored").inner_text() == "—"
        elif view == "comparison":
            assert page.locator("#hzm-compare-away-pace").inner_text() == "—"
        elif view == "backtest":
            assert page.locator("#hzm-backtest-games").inner_text() == "—"
            assert page.locator("#hzm-backtest-v75-total").inner_text() == "—"
            assert page.locator("#hzm-backtest-run").is_disabled()


def run():
    with sync_playwright() as p:
        executable = which("chromium") or which("google-chrome")
        browser = p.chromium.launch(
            headless=True, args=["--no-sandbox"],
            **({"executable_path": executable} if executable else {}),
        )
        dimensions = [
            ("desktop", 1672, 941),
            ("iphone", 390, 844),
            ("compact", 320, 700),
            ("landscape", 844, 390),
        ]
        for label, width, height in dimensions:
            phone = width < 768 or height < 500
            page = browser.new_page(
                viewport={"width": width, "height": height},
                is_mobile=phone, has_touch=phone, device_scale_factor=1,
            )
            errors = []
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.clock.set_fixed_time("2026-11-23T12:00:00Z")
            page.goto(PAGE, wait_until="load")
            for css in CSS_FILES:
                assert page.evaluate(
                    """css => [...document.styleSheets]
                      .filter(s => (s.href||'').endsWith('/'+css)).length""",
                    css,
                ) == 1, f"Missing or duplicated stylesheet: {css}"
            nav = page.locator('#hz-mobile-nav [data-page="simulations"]')
            if nav.is_visible():
                nav.click()
            else:
                page.locator('.nav-btn[data-page="simulations"]').click()
            data = fixture()
            data["premium_simulation"]["backtest"] = None
            data["home"]["calendar_games"].append({
                "id": "401000002", "day": "2026-11-23", "away": "BOS",
                "home": "MIA", "state": "scheduled",
                "start": "2026-11-23T23:30:00Z",
            })
            page.evaluate(
                "payload => window.postMessage({type:'streamlit:render',args:{payload}}, '*')",
                data,
            )
            page.wait_for_function(
                "() => document.querySelector('#hzm-score')?.textContent.includes('115 : 116')"
            )
            tabs = page.locator('#hzm-lab-nav [role="tab"]')
            assert tabs.count() == 7  # Six released modules + hidden research Flow.
            assert page.locator("#hzm-lab-tab-flow").is_hidden()
            assert page.locator("#hzm-lab-tab-flow").is_disabled()

            for view, panel in SCREENS.items():
                page.locator(f"#hzm-lab-tab-{view}").click()
                page.wait_for_function(
                    "(view) => document.querySelector('#simulations-pane')?.dataset.hzmView===view",
                    arg=view,
                )
                assert page.locator(panel).is_visible(), (label, view)
                assert page.locator("#hzm-lab-main").get_attribute(
                    "aria-labelledby"
                ) == f"hzm-lab-tab-{view}"
                selected = page.locator('#hzm-lab-nav [role="tab"][aria-selected="true"]')
                assert selected.count() == 1 and selected.first.get_attribute(
                    "id"
                ) == f"hzm-lab-tab-{view}", (label, view)
                assert page.locator("#hzm-flow-panel").is_hidden()
                for other, sel in SCREENS.items():
                    if other != view:
                        assert page.locator(sel).is_hidden(), (label, view, other)
                if phone:
                    assert page.locator("#app-shell").get_attribute(
                        "class"
                    ).find("hz-mobile-intelligence") >= 0, (label, view)
                    stage = geometry(page, "#stage")
                    card = geometry(page, panel)
                    assert stage["width"] >= width - 5, (label, view, stage)
                    assert card["width"] >= width - 85, (label, view, card)
                    overflow = page.evaluate(
                        "() => ({actual:document.documentElement.scrollWidth,viewport:document.documentElement.clientWidth})"
                    )
                    assert overflow["actual"] <= overflow["viewport"] + 2, (label, view, overflow)
                    document_height = page.evaluate(
                        "() => Math.max(document.body.scrollHeight, document.documentElement.scrollHeight)"
                    )
                    if document_height > height + 160:
                        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                        page.wait_for_timeout(45)
                        y = page.evaluate("window.scrollY")
                        assert y > 80, (
                            "Long native Premium view must allow genuine vertical page scroll",
                            label, view, document_height, y,
                        )
                        end = geometry(page, panel)
                        assert end["bottom"] <= height - 20, (
                            "Last module cards must be reachable by scrolling", label, view, end,
                        )
                if view == "results":
                    assert page.locator("#hzm-score").inner_text() == "115 : 116"
                    assert page.locator("#hzm-plot svg").count() == 1
                elif view == "players":
                    assert page.locator('#hzv3-roster .hzv3-player[aria-label^="QA Test Player ·"]').count() == 1
                elif view == "scenario":
                    assert "WHAT-IF" in page.locator("#hzm-scenario-panel").inner_text()
                elif view == "intelligence":
                    assert page.locator("#hzm-intel-model").count() == 1
                elif view == "comparison":
                    assert page.locator("#hzm-compare-away-pace").inner_text() == "—", (
                        "Unverified NBA Advanced must stay unavailable", label,
                    )
                elif view == "backtest":
                    assert page.locator("#hzm-backtest-games").inner_text() == "—"
                    assert "niedostępny" in page.locator(
                        ".hzm-backtest-roi"
                    ).inner_text().lower()
                page.evaluate("window.scrollTo(0,0)")
                page.screenshot(path=str(OUT / f"{label}-{view}.png"), full_page=True)

            # The public Flow tab is disabled in markup AND guarded in the JS router.
            page.evaluate(
                """() => document.querySelector('#hzm-lab-tab-flow')
                   .dispatchEvent(new MouseEvent('click',{bubbles:true}))"""
            )
            assert page.locator("#simulations-pane").get_attribute(
                "data-hzm-view"
            ) == "backtest"

            # A different scheduled fixture cannot reuse the first game's
            # paid projections or players when the server has not supplied it.
            page.locator("#hzm-lab-tab-results").click()
            page.locator("#hzm-match-picker").click()
            page.locator('#hzm-matches [data-hzm-game="401000002"]').click()
            assert page.locator("#hzm-score").inner_text() == "— : —"
            assert page.locator("#hzm-hero-away-points").inner_text() == "—"
            assert page.locator("#hzm-hero-home-points").inner_text() == "—"
            assert page.locator("#hzm-plot svg").count() == 0

            # Restore the supplied fixture, then ensure model change cannot
            # display statistics calculated by a different model.
            page.locator("#hzm-match-picker").click()
            page.locator('#hzm-matches [data-hzm-game="401000001"]').click()
            assert page.locator("#hzm-score").inner_text() == "115 : 116"
            page.locator("#hzm-model-trigger").click()
            page.locator("#hzm-model-option-research_context_v75").click()
            assert "V7.5" in page.locator("#hzm-model-current").inner_text()
            assert page.locator("#hzm-score").inner_text() == "— : —"
            page.locator("#hzm-model-trigger").click()
            page.locator("#hzm-model-option-research_form_v74").click()
            assert page.locator("#hzm-score").inner_text() == "115 : 116"

            # Even a malformed packet with 'entitled:false' and fake premium
            # metrics must not render restricted values anywhere in the Lab.
            check_visitor_gate(page, data)
            assert not errors, (label, errors)
            page.close()
        browser.close()
        print("Simulation Lab final integration: 6 modules x 4 viewports, "
              "data isolation, hidden Flow and Premium gate OK")


if __name__ == "__main__":
    run()
