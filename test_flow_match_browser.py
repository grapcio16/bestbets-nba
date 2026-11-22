"""Interactive Premium Flow meczu browser contract. NBA values are synthetic."""
from pathlib import Path
from shutil import which
from playwright.sync_api import sync_playwright

PAGE = (Path(__file__).parent / "bestbets_reference_frontend" / "index.html").as_uri()


def flow():
    return {
        "available": True, "method": "conditional_neutral_6min_v1",
        "n_sims": 5000,
        "source": ("Rekonstrukcja warunkowa z 5 000 wynikow koncowych. "
                   "Nie sa to dane play-by-play ani potwierdzone rotacje."),
        "timeline": [
            {"minute": i*6, "margin_mean": (i/8)*2.5,
             "margin_p10": -10+i/8*2.5,
             "margin_p90": 10+i/8*2.5}
            for i in range(9)
        ],
        "quarters": [
            {"quarter": i+1, "away_outscores_pct": 48.0,
             "home_outscores_pct": 50.0, "tie_pct": 2.0,
             "away_mean": 28.0, "home_mean": 29.0}
            for i in range(4)
        ],
        "clutch": {"home_margin_mean": 1.3, "away_outscores_pct": 42.0,
                   "home_outscores_pct": 55.0, "tie_pct": 3.0},
        "volatility": {"final_spread_p10": -20.0,
                       "final_spread_p90": 25.0,
                       "final_spread_sd": 17.5},
        "rotation_available": False, "scoring_runs_available": False,
        "sample_path": [
            {"minute": i*3, "away_minus_home": round(i*.3+(-1)**i*2, 2) if i else 0}
            for i in range(17)],
        "run_proxy": {"method": "neutral_order_two_point_events_v1", "n_sims": 5000,
                      "at_least_6_pct": 81.1, "at_least_8_pct": 52.3,
                      "at_least_10_pct": 29.4},
        "neutral_scoring_window_sd": 6.4,
    }


def fixture(entitled=True):
    date, game_id = "2026-11-23", "401999555"
    base = {"date": date, "game_id": game_id,
            "model_id": "research_form_v74",
            "away": "NYK", "home": "BOS", "n_sims": 5000,
            "away_points": 112.0, "home_points": 114.5,
            "total_points": 226.5, "away_win_pct": 45.0,
            "home_win_pct": 55.0, "distributions": {},
            "model_context": {}, "flow": flow()}
    player = {"date": date, "game_id": game_id,
              "model_id": "research_form_v74", "home": "BOS",
              "players": [
                  {"name": "Synthetic Away", "team": "NYK", "minutes": 32.0,
                   "minutes_sample": 5, "availability": "Unknown",
                   "pts": 20.0, "reb": 3.0, "ast": 6.0,
                   "position": "PG",
                   "history": [{"min": 30.0}, {"min": 35.0}, {"min": 32.0}]},
                  {"name": "Synthetic Home", "team": "BOS", "minutes": 31.0,
                   "minutes_sample": 6, "availability": "Unknown",
                   "pts": 23.0, "reb": 4.0, "ast": 5.0,
                   "position": "SG",
                   "history": [{"min": 31.0}, {"min": 28.0}, {"min": 34.0}]},
              ]}
    return {
        "brand": "", "auth": {"role": "premium" if entitled else "free"},
        "home": {"calendar_today": date, "calendar_requested_day": date,
                 "calendar_games": [
                     {"id": game_id, "day": date, "away": "NYK", "home": "BOS",
                      "state": "scheduled", "start": "2026-11-23T01:00:00Z"}],
                 "calendar_loaded_days": [date]},
        "premium_simulation": {
            "entitled": entitled, "game": base if entitled else None,
            "players": player if entitled else None,
            "scenario": None, "flow_saved": None, "flow_pdf": None},
    }


def check(page):
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.clock.set_fixed_time("2026-11-21T12:00:00Z")
    page.goto(PAGE, wait_until="load")
    nav = page.locator('.nav-btn[data-page="simulations"]')
    mobile = page.locator('#hz-mobile-nav [data-page="simulations"]')
    if mobile.is_visible():
        mobile.click()
    else:
        nav.click()
    data = fixture()
    page.evaluate(
        "payload => window.postMessage({type:'streamlit:render',args:{payload}}, '*')",
        data)
    page.wait_for_function(
        "document.querySelector('#hzm-day-title')?.textContent.includes('23')")
    page.locator("#hzm-lab-tab-flow").scroll_into_view_if_needed()
    page.locator("#hzm-lab-tab-flow").click()
    assert page.locator("#hzm-flow-panel").is_visible()
    # The top hero must refresh on Flow, not exclusively Results.
    assert page.locator("#hzm-hero-away-points").inner_text() == "112,0"
    assert page.locator("#hzm-hero-home-points").inner_text() == "114,5"
    assert page.locator("#hzm-flow-plot svg").count() == 1
    assert page.locator(".hzm-flow-quarter-row").count() == 4
    assert "32,0" in page.locator("#hzm-flow-roster").inner_text()
    assert "Synthetic Away" in page.locator("#hzm-flow-roster").inner_text()
    assert "52,3%" in page.locator("#hzm-flow-runrisk").inner_text()
    assert page.locator("#hzm-flow-run-data .hzm-flow-run-row").count() == 3
    assert page.locator("#hzm-flow-plot svg").get_attribute("aria-label").startswith(
        "Przykładowy scenariusz")
    assert page.locator(".hzm-flow-history-grid .hzm-flow-player-row").count() == 2
    assert page.locator(".hzm-flow-heat-cell").count() == 32
    assert page.locator(".hzm-flow-matchups .hzm-flow-duel").count() == 3
    assert page.locator("#hzm-flow-scenario").is_disabled()

    page.locator('[data-flow-quarter="3"]').click()
    assert page.locator("#hzm-flow-selected-period").inner_text().startswith("Q3")
    page.evaluate("""() => {
      window.__flowActions=[];
      window.addEventListener('message',e=>{
        if(e.data?.type==='streamlit:setComponentValue'&&
           ['premium_sim_flow_save','premium_sim_flow_export'].includes(e.data.value?.type)){
          window.__flowActions.push(e.data.value);
        }
      });
    }""")
    page.locator("#hzm-flow-save").click()
    page.wait_for_function("window.__flowActions.length===1")
    assert page.evaluate("window.__flowActions[0].variant") == "base"
    page.locator("#hzm-flow-export").click()
    page.wait_for_function("window.__flowActions.length===2")
    assert page.evaluate("window.__flowActions[1].type") == "premium_sim_flow_export"

    data["premium_simulation"]["scenario"] = {
        "date": "2026-11-23", "game_id": "401999555",
        "model_id": "research_form_v74", "pace_pct": 0,
        "off_away_pct": 0, "off_home_pct": 0,
        "scenario_flow": flow(),
        "scenario": {"away_points": 116.0, "home_points": 120.0,
                     "total_points": 236.0, "away_win_pct": 43.0,
                     "home_win_pct": 57.0},
    }
    page.evaluate(
        "payload => window.postMessage({type:'streamlit:render',args:{payload}}, '*')",
        data)
    assert page.locator("#hzm-flow-scenario").is_enabled()
    page.locator("#hzm-flow-scenario").click()
    assert page.locator("#hzm-flow-scenario").get_attribute("aria-pressed") == "true"
    page.locator("#hzm-flow-save").click()
    page.wait_for_function("window.__flowActions.length===3")
    assert page.evaluate("window.__flowActions[2].variant") == "scenario"

    data["premium_simulation"]["flow_pdf"] = {
        "date": "2026-11-23", "game_id": "401999555",
        "model_id": "research_form_v74", "variant": "scenario",
        "content_base64": "A" * 120,
    }
    page.evaluate(
        "payload => window.postMessage({type:'streamlit:render',args:{payload}}, '*')",
        data)
    assert page.locator("#hzm-flow-pdf-link").count() == 1
    assert page.locator("#hzm-flow-pdf-link").get_attribute("download").endswith(".pdf")

    data["premium_simulation"] = {
        "entitled": False, "game": None, "players": None,
        "scenario": None, "flow_saved": None, "flow_pdf": None}
    data["auth"] = {"role": "free"}
    page.evaluate(
        "payload => window.postMessage({type:'streamlit:render',args:{payload}}, '*')",
        data)
    assert page.locator("#hzm-flow-save").is_disabled()
    assert page.locator("#hzm-flow-export").is_disabled()
    assert page.locator("#hzm-hero-away-points").inner_text() == "—"
    assert page.locator("#hzm-hero-home-points").inner_text() == "—"
    assert page.locator("#hzm-flow-pdf-link").count() == 0
    assert page.locator("#hzm-flow-plot svg").count() == 0
    assert "Premium" in page.locator("#hzm-flow-feedback").inner_text()
    assert not errors, errors
    panel=page.locator("#hzm-flow-panel")
    panel.scroll_into_view_if_needed()
    assert panel.is_visible()


def main():
    with sync_playwright() as p:
        exe = which("chromium") or which("google-chrome")
        browser = p.chromium.launch(
            headless=True, args=["--no-sandbox"],
            **({"executable_path": exe} if exe else {}))
        for w,h in [(1231,691),(390,844),(844,390)]:
            page = browser.new_page(viewport={"width": w,"height":h})
            try:
                check(page)
            finally:
                page.close()
        browser.close()
    print("Flow: Premium real-data guards, quarter filters, server save/PDF callbacks, responsive OK")


if __name__ == "__main__":
    main()
