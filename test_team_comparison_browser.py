"""Team Comparison browser test with synthetic, never-published NBA fixtures."""
from pathlib import Path
from shutil import which

from playwright.sync_api import sync_playwright

PAGE = (Path(__file__).parent / "bestbets_reference_frontend" / "index.html").as_uri()
OUT = Path("test-results/hoopzaro-team-compare")
OUT.mkdir(parents=True, exist_ok=True)


def main():
    with sync_playwright() as p:
        exe = which("chromium") or which("google-chrome")
        browser = p.chromium.launch(
            headless=True, args=["--no-sandbox"],
            **({"executable_path": exe} if exe else {}))
        page = browser.new_page(viewport={"width": 1231, "height": 691})
        page.clock.set_fixed_time("2026-11-21T12:00:00Z")
        errors = []
        page.on("pageerror", lambda exc: errors.append(str(exc)))
        page.goto(PAGE, wait_until="load")
        page.locator('.nav-btn[data-page="simulations"]').click()

        day, game_id = "2026-11-23", "401999481"
        away = {
            "team": "NYK", "sample": 20,
            "n5": 5, "pts5": 115.4, "allowed5": 102.0,
            "margin5": 13.4, "wins5": 4, "losses5": 1, "win_pct5": 80.0,
            "n10": 10, "pts10": 109.5, "allowed10": 107.2,
            "margin10": 2.3, "wins10": 7, "losses10": 3, "win_pct10": 70.0,
            "venue": "away", "venue_sample": 8,
            "venue_scored": 113.4, "venue_allowed": 110.1,
            "pace": 100.1, "off_rating": 113.0, "def_rating": 108.6,
        }
        home = {
            "team": "BOS", "sample": 20,
            "n5": 5, "pts5": 112.8, "allowed5": 108.0,
            "margin5": 4.8, "wins5": 3, "losses5": 2, "win_pct5": 60.0,
            "n10": 10, "pts10": 116.0, "allowed10": 112.5,
            "margin10": 3.5, "wins10": 6, "losses10": 4, "win_pct10": 60.0,
            "venue": "home", "venue_sample": 10,
            "venue_scored": 117.0, "venue_allowed": 111.2,
            "pace": 97.8, "off_rating": 116.0, "def_rating": 111.2,
        }
        model = {
            "date": day, "game_id": game_id, "model_id": "research_form_v74",
            "away_points": 109.0, "home_points": 113.0,
            "total_points": 222.0, "away_win_pct": 46.0,
            "home_win_pct": 54.0, "distributions": {}, "n_sims": 5000,
            "model_context": {
                "source": "NBA Advanced + ESPN",
                "completed_games": 125,
                "advanced_available": True,
                "team_comparison": {
                    "source": "Verified ESPN NBA finals",
                    "advanced_available": True,
                    "away": away,
                    "home": home,
                },
            },
        }
        payload = {
            "brand": "", "auth": {"role": "premium"},
            "home": {
                "calendar_today": day, "calendar_loaded_days": [day],
                "calendar_games": [{
                    "id": game_id, "day": day, "away": "NYK", "home": "BOS",
                    "state": "scheduled", "start": "2026-11-23T01:00:00Z",
                }],
            },
            "premium_simulation": {
                "entitled": True, "game": model,
                "players": None, "scenario": None, "minute_scenario": None,
            },
        }
        def show():
            page.evaluate(
                "data => window.postMessage({type:'streamlit:render',args:{payload:data}}, '*')",
                payload)

        show()
        page.locator("#hzm-day-input").evaluate(
            """(el, day) => {el.value=day;
                el.dispatchEvent(new Event('change',{bubbles:true}));}""", day)
        page.locator("#hzm-lab-tab-comparison").click()
        assert page.locator("#hzm-compare-panel").is_visible()
        assert page.locator("#hzm-detail-grid").is_hidden()
        assert page.locator("#hzm-intel-panel").is_hidden()
        assert page.locator("#hzm-compare-away-name").inner_text() == "NYK"
        assert page.locator("#hzm-compare-home-name").inner_text() == "BOS"
        assert page.locator("#hzm-compare-away-pts").inner_text() == "109,5"
        assert page.locator("#hzm-compare-away-allowed").inner_text() == "107,2"
        assert page.locator("#hzm-compare-home-allowed").inner_text() == "112,5"
        assert page.locator("#hzm-compare-away-record").inner_text() == "7 W / 3 L"
        assert page.locator("#hzm-compare-home-win-pct").inner_text() == "60,0%"
        assert page.locator("#hzm-compare-away-pace").inner_text() == "100,1"
        assert page.locator("#hzm-compare-home-off-rating").inner_text() == "116,0"
        assert page.locator("#hzm-compare-home-def-rating").inner_text() == "111,2"
        assert page.locator("#hzm-compare-away-venue-scored").inner_text() == "113,4"
        # Chart is computed from real ESPN history and valid venue samples.
        assert page.locator("#hzm-compare-profile-svg").is_visible()
        assert page.locator("#hzm-compare-profile-empty").is_hidden()
        away_shape = page.locator("#hzm-compare-polygon-away").get_attribute("points")
        home_shape = page.locator("#hzm-compare-polygon-home").get_attribute("points")
        assert len(away_shape.split(" ")) == 5
        assert len(home_shape.split(" ")) == 5
        assert away_shape != home_shape
        assert "L10" in page.locator("#hzm-compare-profile-window").inner_text()
        panel_geom = page.locator("#hzm-compare-panel").evaluate("""el => {
          const table=el.querySelector('.hzm-compare-table').getBoundingClientRect();
          const chart=el.querySelector('.hzm-compare-v2-profile').getBoundingClientRect();
          return {left:table.left, right:chart.left, gap:chart.left-table.right,
                  topDelta:Math.abs(table.top-chart.top),
                  gradient:getComputedStyle(el).backgroundImage};
        }""")
        assert panel_geom["gap"] >= 7, panel_geom
        assert panel_geom["topDelta"] < 4, panel_geom
        assert "gradient" in panel_geom["gradient"], panel_geom
        page.locator("#hzm-compare-panel").screenshot(path=str(OUT / "team-comparison-v2-l10.png"))


        page.locator("#hzm-compare-l5").click()
        assert page.locator("#hzm-compare-away-pts").inner_text() == "115,4"
        assert page.locator("#hzm-compare-home-allowed").inner_text() == "108,0"
        assert page.locator("#hzm-compare-away-record").inner_text() == "4 W / 1 L"
        assert page.locator("#hzm-compare-away-win-pct").inner_text() == "80,0%"
        assert page.locator("#hzm-compare-pts-window").inner_text() == "L5"
        assert page.locator("#hzm-compare-l5").get_attribute("aria-pressed") == "true"
        assert page.locator("#hzm-compare-profile-window").inner_text() == "L5"
        assert page.locator("#hzm-compare-polygon-away").get_attribute("points") != away_shape
        page.locator("#hzm-compare-panel").screenshot(path=str(OUT / "team-comparison-v2-l5.png"))


        # One missing Advanced team: never invent comparable pace/rating.
        model["model_context"]["team_comparison"]["advanced_available"] = False
        show()
        assert page.locator("#hzm-compare-away-pace").inner_text() == "—"
        assert page.locator("#hzm-compare-home-def-rating").inner_text() == "—"
        assert page.locator("#hzm-compare-home-pts").inner_text() == "112,8"
        assert page.locator("#hzm-compare-profile-svg").is_visible(), (
            "Missing NBA Advanced must not remove factual ESPN profile")


        # A swapped team in a cached model context must be rejected entirely.
        model["model_context"]["team_comparison"]["away"] = {**away, "team": "MIA"}
        show()
        assert "Brak kompletnych danych" in page.locator("#hzm-compare-status").inner_text()
        assert page.locator("#hzm-compare-away-pts").inner_text() == "—"
        assert page.locator("#hzm-compare-profile-svg").is_hidden()
        assert page.locator("#hzm-compare-profile-empty").is_visible()


        # Downgrade must hide ALL Premium comparison data.
        payload["premium_simulation"] = {
            "entitled": False, "game": None,
            "players": None, "scenario": None, "minute_scenario": None,
        }
        payload["auth"] = {"role": "free"}
        show()
        assert page.locator("#hzm-compare-away-pts").inner_text() == "—"
        assert page.locator("#hzm-compare-away-record").inner_text() == "— W / — L"
        assert page.locator("#hzm-compare-home-def-rating").inner_text() == "—"
        assert "Premium" in page.locator("#hzm-compare-status").inner_text()
        assert page.locator("#hzm-compare-profile-svg").is_hidden()
        assert not page.locator("#hzm-compare-polygon-away").get_attribute("points")

        # Real native-width phone view must remain legible and scrollable.
        payload["auth"] = {"role": "premium"}
        model["model_context"]["team_comparison"]["away"] = away
        model["model_context"]["team_comparison"]["advanced_available"] = True
        payload["premium_simulation"] = {
            "entitled": True, "game": model, "players": None,
            "scenario": None, "minute_scenario": None,
        }
        show()
        page.set_viewport_size({"width": 390, "height": 844})
        assert page.locator("#hzm-compare-profile-svg").is_visible()
        mobile = page.evaluate("""() => ({
          native:document.querySelector('#app-shell').classList.contains('hz-mobile-intelligence'),
          transform:getComputedStyle(document.querySelector('#stage')).transform,
          stageWidth:document.querySelector('#stage').getBoundingClientRect().width,
          panelWidth:document.querySelector('#hzm-compare-panel').getBoundingClientRect().width,
          labelFont:parseFloat(getComputedStyle(document.querySelector('.hzm-compare-row>span')).fontSize),
          bodyHeight:document.body.scrollHeight,windowHeight:window.innerHeight,
          panelOverflow:document.querySelector('#hzm-compare-panel').scrollWidth -
                        document.querySelector('#hzm-compare-panel').clientWidth
        })""")
        assert mobile["native"] and mobile["transform"] == "none", mobile
        assert 350 <= mobile["stageWidth"] <= 400, mobile
        assert mobile["panelWidth"] >= 340, mobile
        assert mobile["labelFont"] >= 10, mobile
        assert mobile["panelOverflow"] <= 2, mobile
        assert mobile["bodyHeight"] > mobile["windowHeight"]+250, mobile
        page.locator("#hzm-compare-disclaimer").scroll_into_view_if_needed()
        assert page.locator("#hzm-compare-disclaimer").is_visible()
        page.evaluate("window.scrollTo(0,0); document.body.scrollTop=0")
        page.screenshot(path=str(OUT / "team-comparison-v2-mobile.png"), full_page=True)
        page.locator("#hzm-lab-tab-results").click()
        assert page.locator("#app-shell").evaluate(
            "el => el.classList.contains('hz-mobile-intelligence')")
        page.locator('#hz-mobile-nav [data-page="home"]').click()
        assert not page.locator("#app-shell").evaluate(
            "el => el.classList.contains('hz-mobile-intelligence')")
        assert not errors, errors
        browser.close()
        print("Team Comparison: L5/L10, source gating, team identity and Premium OK")


if __name__ == "__main__":
    main()
