"""Static responsive smoke for all SIX Premium Simulation Lab views.

Only synthetic test data. No network NBA requests, no production login.
Validate view routing, horizontal scroll access and vertical panel reachability
at desktop, mobile portrait and landscape sizes. Artifacts are screenshots.
"""
from pathlib import Path
from shutil import which

from playwright.sync_api import sync_playwright

PAGE = (Path(__file__).parent / "bestbets_reference_frontend" / "index.html").as_uri()
OUT = Path("test-results/hoopzaro-responsive")
OUT.mkdir(parents=True, exist_ok=True)

VIEWS = [
    ("results", "#hzm-detail-grid", "#hzm-players-panel"),
    ("players", "#hzm-detail-grid", "#hzm-player-inspector"),
    ("scenario", "#hzm-scenario-panel", "#hzm-availability-panel"),
    ("intelligence", "#hzm-intel-panel", "#hzm-intel-caveat"),
    ("comparison", "#hzm-compare-panel", "#hzm-compare-disclaimer"),
    ("backtest", "#hzm-backtest-panel", "#hzm-backtest-caveat"),
]


def payload():
    day, game_id = "2026-11-23", "401999531"
    sample = [
        {"name": "Synthetic Athlete One", "team": "NYK", "minutes": 31.0,
         "minutes_sample": 6, "availability": "Probable",
         "pts": 22.0, "reb": 6.0, "ast": 5.0},
        {"name": "Synthetic Athlete Two", "team": "BOS", "minutes": 27.0,
         "minutes_sample": 6, "availability": "Questionable",
         "pts": 18.0, "reb": 5.0, "ast": 4.0},
    ]
    comp = {}
    for side, team in (("away", "NYK"), ("home", "BOS")):
        comp[side] = {
            "team": team, "n5": 5, "n10": 10, "sample": 20,
            "pts5": 114.0, "pts10": 111.0, "allowed5": 108.0,
            "allowed10": 109.0, "margin5": 6.0, "margin10": 2.0,
            "wins5": 4, "losses5": 1, "win_pct5": 80.0,
            "wins10": 6, "losses10": 4, "win_pct10": 60.0,
            "venue_sample": 8, "venue_scored": 112.0,
            "venue_allowed": 108.0, "pace": 100.0,
            "off_rating": 116.0, "def_rating": 112.0,
        }
    ctx = {
        "source": "NBA Advanced + ESPN", "completed_games": 110,
        "away_sample": 20, "home_sample": 20,
        "venue_samples": [8, 8], "rest_days": [2, 1],
        "score_sd_samples": [18, 19], "advanced_available": True,
        "team_comparison": {
            "away": comp["away"], "home": comp["home"], "advanced_available": True,
        },
        "v75_factors": {
            "venue_away_pts": -.5, "venue_home_pts": 1.0,
            "rest_away_pts": .2, "rest_home_pts": -.8,
            "injury_away_pts": 0.0, "injury_home_pts": -.4,
            "injuries_espn_fresh": True,
            "injury_out_away": 0, "injury_out_home": 1,
            "away_venue_games": 8, "home_venue_games": 8,
        },
    }
    distributions = {
        k: {
            "bins": [{"x": x, "p": 25/(1+abs(x-avg)/13)}
                     for x in range(start, end, 5)],
            "average": avg, "threshold": avg,
            "p10": avg-18, "p90": avg+18,
        }
        for k, start, end, avg in (
            ("match", 185, 270, 230), ("home", 80, 145, 116),
            ("away", 80, 145, 114))
    }
    methods = [
        {"key": key, "total_mae": 13.4, "team_mae": 9.3,
         "winner_accuracy_pct": 61.0, "brier": .2321}
        for key in ("old", "new", "enriched", "v75")
    ]
    return {
        "brand": "", "auth": {"role": "premium"},
        "home": {
            "calendar_today": day,
            "calendar_loaded_days": [day],
            "calendar_games": [{
                "id": game_id, "day": day, "away": "NYK", "home": "BOS",
                "state": "scheduled", "start": "2026-11-23T01:00:00Z",
            }],
        },
        "premium_simulation": {
            "entitled": True,
            "game": {
                "date": day, "game_id": game_id,
                "model_id": "research_context_v75",
                "away_points": 114, "home_points": 116,
                "total_points": 230, "away_win_pct": 47, "home_win_pct": 53,
                "distributions": distributions, "n_sims": 5000,
                "model_context": ctx,
            },
            "players": {
                "date": day, "game_id": game_id,
                "model_id": "research_context_v75",
                "home": "BOS", "players": sample,
                "injury_report_fresh": False,
            },
            "scenario": None, "minute_scenario": None,
            "backtest": {
                "season": "2026-27", "games": 35, "max_games": 40,
                "first_game": "2026-10-25", "last_game": "2026-11-20",
                "as_of_utc": "2026-11-21T13:00:00+00:00",
                "models": methods,
                "limitation": "Historical offline model only",
            },
        },
    }


def check(page, width, height):
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.clock.set_fixed_time("2026-11-21T12:00:00Z")
    page.goto(PAGE, wait_until="load")
    # The native mobile tab bar replaces desktop sidebar navigation.
    mobile = page.locator('#hz-mobile-nav [data-page="simulations"]')
    desktop = page.locator('.nav-btn[data-page="simulations"]')
    if mobile.is_visible():
        mobile.click()
    else:
        desktop.click()
    data = payload()
    page.evaluate(
        "d => window.postMessage({type:'streamlit:render',args:{payload:d}}, '*')",
        data)
    page.locator("#hzm-day-input").fill("2026-11-23")
    page.locator("#hzm-day-input").dispatch_event("change")
    page.locator("#hzm-model-trigger").click()
    page.locator("#hzm-model-option-research_context_v75").click()
    assert page.locator("#hzm-lab-nav button:disabled").count() == 0

    for view, panel, bottom in VIEWS:
        tab = page.locator("#hzm-lab-tab-"+view)
        tab.scroll_into_view_if_needed(timeout=10000)
        tab.click(timeout=10000)
        assert tab.get_attribute("aria-selected") == "true", (width, height, view)
        assert page.locator(panel).is_visible(), (width, height, view)
        # Verify that the deepest content in each module is reachable by
        # either the independent Simulation Lab scroller or the page scroller.
        target = page.locator(bottom)
        target.scroll_into_view_if_needed(timeout=10000)
        assert target.is_visible(), (width, height, view, bottom)
        scroll = page.evaluate("""() => {
          const pane=document.querySelector('#simulations-pane');
          return {
            height:pane.clientHeight,
            extent:pane.scrollHeight,
            scrollY:pane.scrollTop,
          };
        }""")
        assert scroll["extent"] >= scroll["height"] - 2, (view, scroll)
        page.screenshot(path=str(OUT / f"simlab-{view}-{width}x{height}.png"))
    assert not errors, (width, height, errors)


def main():
    with sync_playwright() as p:
        exe = which("chromium") or which("google-chrome")
        browser = p.chromium.launch(
            headless=True, args=["--no-sandbox"],
            **({"executable_path": exe} if exe else {}))
        for width, height in [(1231, 691), (390, 844), (844, 390)]:
            page = browser.new_page(
                viewport={"width": width, "height": height},
                device_scale_factor=1)
            try:
                check(page, width, height)
            finally:
                page.close()
        browser.close()
    print("Simulation Lab: 6 tabs x 3 viewports navigable and vertically reachable")


if __name__ == "__main__":
    main()
