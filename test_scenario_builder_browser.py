"""Scenario Builder browser smoke; fixtures are synthetic, never published as NBA data."""
from pathlib import Path
from shutil import which
import math

from playwright.sync_api import sync_playwright

PAGE = (Path(__file__).parent / "bestbets_reference_frontend" / "index.html").as_uri()
OUT = Path("test-results/hoopzaro-scenario-v2")
OUT.mkdir(parents=True,exist_ok=True)


def illustrative_dist(center):
    """Synthetic QA-only distribution: never publish as real prediction."""
    pts=list(range(180,286,5))
    values=[math.exp(-.5*((x+2.5-center)/18)**2) for x in pts]
    total=sum(values)
    return {"average":center,"p10":center-23,"p90":center+23,
            "bins":[{"x":x,"p":round(100*v/total,4)} for x,v in zip(pts,values)]}



def main():
    with sync_playwright() as p:
        executable = which("chromium") or which("google-chrome")
        opts = {"executable_path": executable} if executable else {}
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"], **opts)
        page = browser.new_page(viewport={"width": 1231, "height": 691})
        page.clock.set_fixed_time("2026-11-21T12:00:00Z")
        errors = []
        page.on("pageerror", lambda exc: errors.append(str(exc)))
        page.goto(PAGE, wait_until="load")
        page.locator('.nav-btn[data-page="simulations"]').click()
        day = "2026-11-23"
        game_id = "401999444"
        home = {
            "calendar_today": day,
            "calendar_loaded_days": [day],
            "calendar_games": [{
                "id": game_id, "day": day, "away": "NYK", "home": "BOS",
                "state": "scheduled", "start": "2026-11-23T01:00:00Z"
            }]
        }
        base = {
            "date": day, "game_id": game_id, "model_id": "research_form_v74",
            "away_points": 113.0, "home_points": 117.0,
            "total_points": 230.0, "away_win_pct": 49, "home_win_pct": 51,
            "distributions": {"match": illustrative_dist(230)}, "n_sims": 5000
        }
        payload = {
            "auth": {"role": "premium"}, "home": home, "brand": "",
            "premium_simulation": {
                "entitled": True, "game": base, "players": None, "scenario": None
            }
        }
        page.evaluate(
            "data => window.postMessage({type:'streamlit:render',args:{payload:data}}, '*')",
            payload,
        )
        # The fixture day may differ from the app's local current day.
        # Select it explicitly, as a user would in the date control.
        page.locator("#hzm-day-input").evaluate(
            """(el, day) => {el.value=day;el.dispatchEvent(new Event('change',{bubbles:true}));}""",day)
        page.locator("#hzm-lab-tab-scenario").click()
        assert page.locator("#hzm-scenario-panel").is_visible()
        assert page.locator(".hzm-hero").is_hidden()
        assert page.locator(".hzm-scenario-v2-heading").is_visible()
        assert "EKSPERYMENTALNE" in page.locator(".hzm-scenario-v2-experimental").inner_text()
        overview=page.locator("#hzm-scenario-panel").evaluate("""el=>{
          const x=selector=>el.querySelector(selector).getBoundingClientRect();
          const left=x('.hzm-scenario-control'),centre=x('.hzm-scenario-output'),
              right=x('.hzm-scenario-insights');
          const cardCSS=getComputedStyle(el.querySelector('.hzm-scenario-output'));
          return {left:left.left,centre:centre.left,right:right.left,
                  tops:[left.top,centre.top,right.top],height:centre.height,
                  overflow:cardCSS.overflow,gradient:cardCSS.backgroundImage}
        }""")
        assert overview["left"]<overview["centre"]<overview["right"],overview
        assert max(overview["tops"])-min(overview["tops"])<4,overview
        assert overview["height"]>490 and overview["overflow"]!="hidden",overview
        assert "gradient" in overview["gradient"],overview

        assert page.locator("#hzm-scenario-base").inner_text() == "230,0 pkt"
        assert page.locator("#hzm-scenario-whatif").inner_text() == "—"
        assert page.locator("#hzm-scenario-run").is_enabled()
        assert page.locator("#hzm-scenario-off-away-code").inner_text() == "NYK"
        assert page.locator("#hzm-scenario-off-home-code").inner_text() == "BOS"
        assert page.locator("#hzm-scenario-off-away-display").inner_text() == "0%"
        assert page.locator("#hzm-scenario-off-home-display").inner_text() == "0%"

        page.evaluate("""() => {
          window.__scenarioRequests = [];
          window.addEventListener('message', event => {
            if(event.data?.type === 'streamlit:setComponentValue' &&
               event.data.value?.type === 'premium_sim_scenario')
              window.__scenarioRequests.push(event.data.value);
          });
        }""")
        page.locator("#hzm-scenario-pace").evaluate(
            """el => {el.value='3';el.dispatchEvent(new Event('input',{bubbles:true}))}"""
        )
        assert page.locator("#hzm-scenario-pace-display").inner_text() == "+3%"
        page.locator("#hzm-scenario-run").click()
        page.wait_for_function("window.__scenarioRequests.length===1")
        req = page.evaluate("window.__scenarioRequests[0]")
        assert req["pace_pct"] == 3 and req["game_id"] == game_id
        assert req["model_id"] == "research_form_v74"
        assert req["off_away_pct"] == 0 and req["off_home_pct"] == 0

        payload["premium_simulation"]["scenario"] = {
            "date": day, "game_id": game_id, "model_id": "research_form_v74",
            "pace_pct": 3, "off_away_pct": 0, "off_home_pct": 0,
            "baseline": {
                "total_points": 230.0, "away_points": 113.0,
                "home_points": 117.0, "away_win_pct": 49.0, "home_win_pct": 51.0},
            "scenario": {
                "total_points": 236.0, "away_points": 116.0,
                "home_points": 120.0, "away_win_pct": 48.6, "home_win_pct": 51.4},
            "baseline_distribution": illustrative_dist(230),
            "scenario_distribution": illustrative_dist(236),
        }
        page.evaluate(
            "data => window.postMessage({type:'streamlit:render',args:{payload:data}}, '*')",
            payload,
        )
        assert page.locator("#hzm-scenario-whatif").inner_text() == "236,0 pkt"
        assert page.locator("#hzm-scenario-delta").inner_text() == "+6,0 pkt"
        assert page.locator("#hzm-scenario-away-code").inner_text() == "NYK"
        assert page.locator("#hzm-scenario-home-code").inner_text() == "BOS"
        assert "113,0 pkt → 116,0 pkt" in page.locator("#hzm-scenario-away-points").inner_text()
        assert "117,0 pkt → 120,0 pkt" in page.locator("#hzm-scenario-home-points").inner_text()
        assert "-0,4 pp" in page.locator("#hzm-scenario-away-win").inner_text()
        assert "+0,4 pp" in page.locator("#hzm-scenario-home-win").inner_text()
        assert len(page.locator("#hzm-scenario-curve path").all())>=4
        assert "80%" in page.locator("#hzm-scenario-insight-risk").inner_text()
        assert "what-if" in page.locator("#hzm-scenario-insight-total").inner_text()
        assert page.locator("#hzm-scenario-status").is_visible()
        # The app owns a scrolling #work container on desktop. Reset it after
        # clicking the Run button: screenshots must show the real first fold.
        page.evaluate("""() => {
          if(document.activeElement?.blur)document.activeElement.blur();
          for(const sel of ['#work','#simulations-pane','.hzm-content','.hzm-analysis']){
            const el=document.querySelector(sel);if(el)el.scrollTop=0;
          }
          window.scrollTo(0,0);
          document.body.scrollTop=0;
          document.documentElement.scrollTop=0;
        }""")
        page.wait_for_timeout(100)
        desktop_top=page.evaluate("""() => ({
          work:document.querySelector('#work').scrollTop,
          pane:document.querySelector('#simulations-pane').scrollTop,
          content:document.querySelector('.hzm-content').scrollTop,
          window:window.scrollY,
          titleY:document.querySelector('.hzm-scenario-v2-heading').getBoundingClientRect().top,
          leftY:document.querySelector('.hzm-scenario-control').getBoundingClientRect().top,
          active:document.activeElement?.id||''
        })""")
        print("DESKTOP TOP FOLD:",desktop_top,flush=True)
        assert 0<=desktop_top["titleY"]<300,desktop_top
        page.screenshot(path=str(OUT / "scenario-v2-desktop-first-fold.png"))
        page.locator("#hzm-scenario-insight-risk").scroll_into_view_if_needed()
        page.screenshot(path=str(OUT / "scenario-v2-desktop-scrolled.png"))
        page.locator("#work").evaluate("el=>el.scrollTop=0")


        # Independent team adjustments must invalidate previous cached results
        # and be transmitted explicitly to the server.
        page.locator("#hzm-scenario-off-away").evaluate(
            """el => {el.value='4';el.dispatchEvent(new Event('input',{bubbles:true}))}"""
        )
        page.locator("#hzm-scenario-off-home").evaluate(
            """el => {el.value='-2';el.dispatchEvent(new Event('input',{bubbles:true}))}"""
        )
        assert page.locator("#hzm-scenario-off-away-display").inner_text() == "+4%"
        assert page.locator("#hzm-scenario-off-home-display").inner_text() == "-2%"
        assert page.locator("#hzm-scenario-whatif").inner_text() == "—"
        page.locator("#hzm-scenario-run").click()
        page.wait_for_function("window.__scenarioRequests.length===2")
        req2 = page.evaluate("window.__scenarioRequests[1]")
        assert req2["off_away_pct"] == 4 and req2["off_home_pct"] == -2
        assert req2["pace_pct"] == 3
        payload["premium_simulation"]["scenario"].update({
            "off_away_pct": 4, "off_home_pct": -2,
            "scenario": {"total_points": 234.0,
                         "away_points": 120.0, "home_points": 114.0,
                         "away_win_pct": 57.0, "home_win_pct": 43.0}
        })
        page.evaluate(
            "data => window.postMessage({type:'streamlit:render',args:{payload:data}}, '*')",
            payload,
        )
        assert page.locator("#hzm-scenario-whatif").inner_text() == "234,0 pkt"
        assert "113,0 pkt → 120,0 pkt" in page.locator("#hzm-scenario-away-points").inner_text()
        assert "117,0 pkt → 114,0 pkt" in page.locator("#hzm-scenario-home-points").inner_text()

        # A cached scenario for a different pace value must not appear.
        payload["premium_simulation"]["scenario"]["pace_pct"] = 2
        page.evaluate(
            "data => window.postMessage({type:'streamlit:render',args:{payload:data}}, '*')",
            payload,
        )
        assert page.locator("#hzm-scenario-whatif").inner_text() == "—"
        assert "→ —" in page.locator("#hzm-scenario-away-points").inner_text()

        payload["auth"] = {"role": "free"}
        payload["premium_simulation"] = {
            "entitled": False, "game": None, "players": None, "scenario": None
        }
        page.evaluate(
            "data => window.postMessage({type:'streamlit:render',args:{payload:data}}, '*')",
            payload,
        )
        assert page.locator("#hzm-scenario-whatif").inner_text() == "—"
        assert page.locator("#hzm-scenario-base").inner_text() == "—"
        assert page.locator("#hzm-scenario-run").is_disabled()
        assert page.locator("#hzm-scenario-away-points").inner_text() == "—"
        assert page.locator("#hzm-scenario-home-win").inner_text() == "—"
        assert "Wymagane" in page.locator("#hzm-scenario-status").inner_text()
        # Restore an authorized, matched scenario to test native mobile view.
        payload["auth"] = {"role":"premium"}
        payload["premium_simulation"]={"entitled":True,"game":base,
            "players":None,"scenario":{
                "date":day,"game_id":game_id,"model_id":"research_form_v74",
                "pace_pct":3,"off_away_pct":4,"off_home_pct":-2,
                "baseline":{"total_points":230.0,"away_points":113.0,
                    "home_points":117.0,"away_win_pct":49,"home_win_pct":51},
                "scenario":{"total_points":234.0,"away_points":120.0,
                    "home_points":114.0,"away_win_pct":57,"home_win_pct":43},
                "baseline_distribution":illustrative_dist(230),
                "scenario_distribution":illustrative_dist(234)
            }}
        page.evaluate("data=>window.postMessage({type:'streamlit:render',args:{payload:data}},'*')",payload)
        page.set_viewport_size({"width":390,"height":844})
        assert page.locator("#hzm-scenario-panel").is_visible()
        mobile=page.evaluate("""()=>{
          const shell=document.querySelector('#app-shell'),
                stage=document.querySelector('#stage'),
                panel=document.querySelector('#hzm-scenario-panel'),
                left=document.querySelector('.hzm-scenario-control'),
                center=document.querySelector('.hzm-scenario-output');
          return {native:shell.classList.contains('hz-mobile-intelligence'),
             transform:getComputedStyle(stage).transform,
             width:stage.getBoundingClientRect().width,
             panelWidth:panel.getBoundingClientRect().width,
             leftTop:left.getBoundingClientRect().top,
             centerTop:center.getBoundingClientRect().top,
             bodyHeight:document.body.scrollHeight,winHeight:window.innerHeight,
             overflow:panel.scrollWidth-panel.clientWidth,
             fontSize:parseFloat(getComputedStyle(document.querySelector('.hzm-scenario-lead')).fontSize)
           }
        }""")
        assert mobile["native"] and mobile["transform"]=="none",mobile
        assert 350<=mobile["width"]<=400 and mobile["panelWidth"]>=350,mobile
        assert mobile["centerTop"]>mobile["leftTop"]+200,mobile
        assert mobile["overflow"]<=2 and mobile["fontSize"]>=10,mobile
        assert mobile["bodyHeight"]>mobile["winHeight"]+450,mobile
        page.locator("#hzm-scenario-insight-risk").scroll_into_view_if_needed()
        visible = page.locator("#hzm-scenario-insight-risk").evaluate("""el=>{
          const r=el.getBoundingClientRect();
          return {top:r.top,bottom:r.bottom,windowHeight:window.innerHeight,
           htmlScroll:document.documentElement.scrollTop,
           bodyScroll:document.body.scrollTop,
           panelScroll:document.querySelector('#simulations-pane').scrollTop,
           rectWidth:r.width};
        }""")
        print("MOBILE RISK SCROLLED INTO VIEW:",visible,flush=True)
        assert visible["top"]>=-2 and visible["top"]<visible["windowHeight"]-70,visible
        assert visible["rectWidth"]>190,visible
        page.screenshot(path=str(OUT / "scenario-v2-mobile-scrolled.png"))
        page.evaluate("window.scrollTo(0,0);document.body.scrollTop=0")
        page.screenshot(path=str(OUT / "scenario-v2-mobile-first-fold.png"))
        # Full-page snapshots can have blank padding when body and html are
        # independently scrollable; viewport snapshots above are authoritative.

        page.locator("#hzm-lab-tab-results").click()
        assert not page.locator("#app-shell").evaluate(
            "el=>el.classList.contains('hz-mobile-intelligence')")
        assert not errors, errors
        browser.close()
        print("Scenario Builder browser: model switch isolation, render and free gate OK")


if __name__ == "__main__":
    main()
