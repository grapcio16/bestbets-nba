"""Match Intelligence: all fixtures and factors are synthetic test evidence."""
from pathlib import Path
from shutil import which

from playwright.sync_api import sync_playwright

PAGE = (Path(__file__).parent / "bestbets_reference_frontend" / "index.html").as_uri()
OUT = Path("test-results/premium-match-intelligence")
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
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(PAGE, wait_until="load")
        page.locator('.nav-btn[data-page="simulations"]').click()
        day, game_id = "2026-11-23", "401999467"
        ctx = {
            "source": "NBA Advanced + ESPN", "completed_games": 130,
            "away_sample": 25, "home_sample": 24,
            "venue_samples": [10, 12], "rest_days": [2, 1],
            "score_sd_samples": [20, 18], "advanced_available": True,
            "team_comparison": {
                "away": {"n10": 10, "wins10": 6, "losses10": 4,
                         "pts10": 113.4, "allowed10": 109.2},
                "home": {"n10": 10, "wins10": 7, "losses10": 3,
                         "pts10": 117.6, "allowed10": 108.5},
            },
            "warnings": ["Wystarczająca próbka historyczna."],
            "v75_factors": {
                "venue_away_pts": -1.0, "venue_home_pts": 1.5,
                "rest_away_pts": 0.4, "rest_home_pts": -0.8,
                "injury_away_pts": 0.0, "injury_home_pts": -1.2,
                "injuries_espn_fresh": True,
            },
        }
        game = {
            "date": day, "game_id": game_id, "model_id": "research_context_v75",
            "away_points": 112.0, "home_points": 115.0,
            "total_points": 227.0,
            "away_win_pct": 47.0, "home_win_pct": 53.0,
            "distributions": {}, "n_sims": 5000,
            "model_context": ctx,
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
                "entitled": True, "game": game,
                "players": None, "scenario": None, "minute_scenario": None,
            },
        }

        def push():
            page.evaluate(
                "data => window.postMessage({type:'streamlit:render',args:{payload:data}}, '*')",
                payload)

        push()
        # The native date control is intentionally hidden behind the custom
        # calendar; Playwright's fill() requires visibility and would hang.
        page.locator("#hzm-day-input").evaluate(
            """(el, day) => {el.value=day;
                 el.dispatchEvent(new Event('change',{bubbles:true}));}""", day)
        page.locator("#hzm-model-trigger").click()
        page.locator("#hzm-model-option-research_context_v75").click()
        page.locator("#hzm-lab-tab-intelligence").click()
        assert page.locator("#hzm-intel-panel").is_visible()
        assert page.locator(".hzm-hero").is_hidden(), (
            "Premium Match Intelligence should not repeat the match hero.")
        assert page.locator("#hzm-intel-main-grid").count() == 0
        geometry = page.locator("#hzm-intel-panel").evaluate("""el => {
          const get = s => el.querySelector(s).getBoundingClientRect();
          const teams = get('.hzm-intel-teams'), factors = get('.hzm-intel-factors');
          const evidence = get('.hzm-intel-evidence');
          const tag = get('.hzm-intel-research-tag'), version = get('.hzm-intel-model');
          return {teamTop:teams.top, factorTop:factors.top,
            kpiBottom:evidence.bottom, cardsWidth:teams.width, factorWidth:factors.width,
            badgeOverlap:tag.right>version.left+1, panelTop:el.getBoundingClientRect().top};
        }""")
        assert abs(geometry["teamTop"]-geometry["factorTop"]) < 4, geometry
        assert geometry["cardsWidth"] > geometry["factorWidth"] > 180, geometry
        assert not geometry["badgeOverlap"], geometry
        assert geometry["panelTop"] < 210, geometry
        assert page.locator("#hzm-intel-panel").get_attribute("class").find("premium-v2") != -1
        assert page.locator("#hzm-intel-away-form").inner_text() == "6 W / 4 L"
        assert page.locator("#hzm-intel-home-form").inner_text() == "7 W / 3 L"
        assert page.locator("#hzm-intel-away-scored").inner_text() == "113,4"
        assert page.locator("#hzm-intel-home-allowed").inner_text() == "108,5"
        assert page.locator("#hzm-intel-factors-v75").is_visible()
        assert page.locator("#hzm-intel-factors-info").is_hidden()
        # Real browser-computed visual styles, not just CSS source assertions.
        appearance = page.locator("#hzm-intel-panel").evaluate("""el => ({
          radius: parseFloat(getComputedStyle(el).borderRadius),
          background: getComputedStyle(el).backgroundImage,
          columns: getComputedStyle(el.querySelector('.hzm-intel-evidence')).gridTemplateColumns,
        })""")
        assert appearance["radius"] >= 12, appearance
        assert "gradient" in appearance["background"], appearance
        assert len(appearance["columns"].split(" ")) >= 3, appearance
        page.screenshot(path=str(OUT / "match-intelligence-v75-desktop.png"), full_page=True)
        page.locator("#hzm-intel-panel").screenshot(path=str(OUT / "match-intelligence-v75-panel.png"))

        assert page.locator("#hzm-detail-grid").is_hidden()
        assert page.locator("#hzm-scenario-panel").is_hidden()
        assert page.locator("#hzm-intel-completed").inner_text() == "130"
        assert page.locator("#hzm-intel-source").inner_text() == "NBA Advanced + ESPN"
        assert page.locator("#hzm-intel-advanced").inner_text() == "Dostępne"
        assert page.locator("#hzm-intel-away-name").inner_text() == "NYK"
        assert page.locator("#hzm-intel-home-name").inner_text() == "BOS"
        assert page.locator("#hzm-intel-away-sample").inner_text() == "25"
        assert page.locator("#hzm-intel-home-venue-sample").inner_text() == "12"
        assert page.locator("#hzm-intel-home-rest").inner_text() == "1,0 dni"
        assert page.locator("#hzm-intel-venue-away").inner_text() == "-1,0 pkt"
        assert page.locator("#hzm-intel-rest-away").inner_text() == "+0,4 pkt"
        assert page.locator("#hzm-intel-injury-home").inner_text() == "-1,2 pkt"
        assert page.locator("#hzm-intel-total-away").inner_text() == "-0,6 pkt"
        assert page.locator("#hzm-intel-total-home").inner_text() == "-0,5 pkt"
        assert "nieskalibrowane" in page.locator("#hzm-intel-caveat").inner_text().lower() or (
            "niekalibrowane" in page.locator("#hzm-intel-caveat").inner_text().lower()
        )

        # V7.4 has historical evidence but NO V7.5 factor attribution.
        game["model_id"] = "research_form_v74"
        game["model_context"] = {k: v for k, v in ctx.items() if k != "v75_factors"}
        push()
        page.locator("#hzm-model-trigger").click()
        page.locator("#hzm-model-option-research_form_v74").click()
        assert page.locator("#hzm-intel-away-sample").inner_text() == "25"
        assert page.locator("#hzm-intel-venue-away").inner_text() == "—"
        assert page.locator("#hzm-intel-total-home").inner_text() == "—"
        assert "V7.4" in page.locator("#hzm-intel-status").inner_text()
        assert page.locator("#hzm-intel-factors-v75").is_hidden()
        assert page.locator("#hzm-intel-factors-info").is_visible()
        assert "nie" in page.locator("#hzm-intel-factors-info-copy").inner_text().lower() or "V7.4" in page.locator("#hzm-intel-factors-info-copy").inner_text()
        page.screenshot(path=str(OUT / "match-intelligence-v74-desktop.png"), full_page=True)


        # No Premium -> never retain any model data in Match Intelligence.
        payload["auth"] = {"role": "free"}
        payload["premium_simulation"] = {
            "entitled": False, "game": None, "players": None,
            "scenario": None, "minute_scenario": None,
        }
        push()
        assert page.locator("#hzm-intel-completed").inner_text() == "—"
        assert page.locator("#hzm-intel-source").inner_text() == "—"
        assert page.locator("#hzm-intel-total-home").inner_text() == "—"
        assert "Premium" in page.locator("#hzm-intel-status").inner_text()
        # Restoring Premium with a fresh V7.5 snapshot must render all new
        # summary data while narrow viewport stacks the KPI and team cards.
        payload["auth"] = {"role": "premium"}
        game["model_id"] = "research_context_v75"
        game["model_context"] = ctx
        payload["premium_simulation"]["entitled"] = True
        payload["premium_simulation"]["game"] = game
        push()
        page.locator("#hzm-model-trigger").click()
        page.locator("#hzm-model-option-research_context_v75").click()
        page.set_viewport_size({"width": 390, "height": 844})
        page.locator("#hzm-intel-panel").scroll_into_view_if_needed()
        assert page.locator("#hzm-intel-panel").is_visible()
        assert page.locator("#hzm-intel-away-form").inner_text() == "6 W / 4 L"
        assert page.locator("#hzm-intel-factors-v75").is_visible()
        mobile_layout = page.evaluate("""() => {
           const stage=document.querySelector('#stage');
           const shell=document.querySelector('#app-shell');
           const panel=document.querySelector('#hzm-intel-panel');
           return {
             mode:shell.classList.contains('hz-mobile-intelligence'),
             transform:getComputedStyle(stage).transform,
             stageWidth:stage.getBoundingClientRect().width,
             cardWidth:panel.getBoundingClientRect().width,
             labelFont:parseFloat(getComputedStyle(document.querySelector('.hzm-intel-team-stat>span')).fontSize),
             bodyExtent:document.documentElement.scrollHeight,
             bodyScroll:document.body.scrollHeight,
             stageExtent:stage.scrollHeight,
             workExtent:document.querySelector('#work').scrollHeight,
             paneExtent:document.querySelector('#simulations-pane').scrollHeight,
             panelHeight:panel.getBoundingClientRect().height,
             panelBottom:panel.getBoundingClientRect().bottom,
             viewportHeight:window.innerHeight,
             viewHeight:window.innerHeight
           };
        }""")
        assert mobile_layout["mode"], mobile_layout
        assert mobile_layout["transform"]=="none", mobile_layout
        assert 350 <= mobile_layout["stageWidth"] <= 400, mobile_layout
        assert mobile_layout["cardWidth"] >= 315, mobile_layout
        assert mobile_layout["labelFont"] >= 10, mobile_layout
        print("MOBILE LAYOUT DIAGNOSTIC:", mobile_layout, flush=True)
        page.screenshot(path=str(OUT / "mobile-native-first-paint.png"), full_page=True)
        assert max(mobile_layout["bodyExtent"], mobile_layout["bodyScroll"]) > mobile_layout["viewHeight"] + 400, mobile_layout
        page.locator("#hzm-intel-caveat").scroll_into_view_if_needed()
        assert page.locator("#hzm-intel-caveat").is_visible()
        card_overflow = page.locator("#hzm-intel-panel").evaluate("""el =>
           ({client:el.clientWidth, scroll:el.scrollWidth,
             cols:getComputedStyle(el.querySelector('.hzm-intel-teams')).gridTemplateColumns})""")
        assert card_overflow["scroll"] <= card_overflow["client"]+2, card_overflow
        page.screenshot(path=str(OUT / "match-intelligence-v75-mobile.png"), full_page=True)
        page.locator("#hzm-intel-panel").screenshot(path=str(OUT / "match-intelligence-v75-mobile-panel.png"))
        page.locator("#hzm-lab-tab-results").click()
        assert not page.locator("#app-shell").evaluate("el => el.classList.contains('hz-mobile-intelligence')")
        assert page.locator("#hzm-detail-grid").is_visible()
        assert not errors, errors
        browser.close()
        print("Match Intelligence: V7.5 factors, V7.4 isolation and Premium gate OK")


if __name__ == "__main__":
    main()
