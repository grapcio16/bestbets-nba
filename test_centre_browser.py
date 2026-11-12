"""Chromium smoke and visual evidence for the new free Centrum start screen.

Run: python test_centre_browser.py --url http://127.0.0.1:8501
Requires running: streamlit run app.py --server.port 8501
"""
from __future__ import annotations
import argparse
import json
import re
from pathlib import Path

from playwright.sync_api import sync_playwright,expect

ROOT=Path(__file__).resolve().parent


def check_static(page,out):
    # Collect component messages as if we were Streamlit. The initial
    # standalone paint MUST NOT dispatch home_data before the first
    # streamlit:render acknowledgement: Streamlit can silently drop it.
    page.add_init_script("""window.__homeEvents=[];
      window.addEventListener('message',e=>{
        if(e.data && e.data.type==='streamlit:setComponentValue' &&
           e.data.value && e.data.value.type==='home_data'){
          window.__homeEvents.push(e.data.value);
        }
      });""")
    doc=(ROOT/"bestbets_reference_frontend"/"index.html").as_uri()
    page.goto(doc,wait_until="load")
    page.wait_for_timeout(200)
    assert page.evaluate("window.__homeEvents.length")==0, "Premature component message before Streamlit handshake"
    page.evaluate("""()=>window.postMessage({
       type:'streamlit:render',args:{payload:{player:null,error:'',brand:'',home:null}}
    },'*')""")
    page.wait_for_function("window.__homeEvents.length===1",timeout=5000)
    home=page.locator("#bestbets-centre")
    expect(home).to_be_visible(timeout=15000)
    expect(page.locator('.nav-btn[data-page="home"]')).to_have_class("nav-btn selected")
    expect(page.locator(".bc-hero-title h1")).to_contain_text("Centrum")
    assert page.locator(".bc-panel").count()==6
    assert page.locator(".bc-pick").count()==0
    assert "Brak potwierdzonych liderów" in page.locator(".bc-pick-list").inner_text()
    assert page.locator(".bc-bottom-item").count()==6
    assert page.locator("#footer").is_hidden()
    assert page.locator("#props-pane").is_hidden()
    assert home.evaluate("el => getComputedStyle(el).display")=="grid"
    assert home.bounding_box()["width"]>=1030
    assert page.locator(".bc-hero").evaluate(
        "el => getComputedStyle(el).borderTopColor")!="rgb(0, 0, 0)"
    page.screenshot(path=str(out/"centrum-design-1231x691.png"),animations="disabled")
    # All sample scores below are LOCAL TO TESTS ONLY; the production app
    # receives schedule rows from confirmed NBA/ESPN sources, never these.
    fixture={"as_of":"2026-11-12 20:00 CET","source":"Fixture test (nie publikować)",
       "error":"","day_label":"Dziś",
       "games":[{"away":"BOS","home":"PHI","away_logo":"","home_logo":"",
                 "start":"2026-11-12T19:00:00+00:00","state":"live",
                 "away_score":78,"home_score":76,"status":"Q3 06:24"}],
       "ticker":[{"away":"BOS","home":"PHI","away_logo":"","home_logo":"",
                  "start":"2026-11-12T19:00:00+00:00","state":"live",
                  "away_score":78,"home_score":76,"status":"Q3 06:24"}],
       "finals":[{"away":"NYK","home":"MIL","away_logo":"","home_logo":"",
                  "start":"2026-11-11T19:00:00+00:00","state":"final",
                  "away_score":106,"home_score":104,"status":"Final"}],
       "form":[{"team":"NYK","logo":"","wins":3,"losses":1,"sample":4}],
       "players":[
         {"name":"Jayson Tatum","team":"BOS","market":"PTS","value":26,"date":"2026-11-11"},
         {"name":"Luka Doncic","team":"LAL","market":"AST","value":8,"date":"2026-11-11"},
         {"name":"Nikola Jokic","team":"DEN","market":"REB","value":15,"date":"2026-11-11"}
       ]}
    page.evaluate("(home) => window.postMessage({type:'streamlit:render',args:{payload:{player:null,error:'',brand:'',home:home}}},'*')",fixture)
    expect(page.locator(".bc-game")).to_have_count(1)
    assert page.evaluate("window.__homeEvents.length")==1, "Must stop re-requesting after receiving the snapshot"
    assert page.locator(".bc-game").first.inner_text().find("NA ŻYWO")>=0
    assert page.locator(".bc-ticker-card.live").count()==1
    assert page.locator(".bc-result").count()==1
    assert page.locator(".bc-team-form").count()==1
    assert page.locator(".bc-pick").count()==3
    assert page.locator(".bc-watch button").count()==3
    assert page.locator(".bc-hot button").count()==3
    page.screenshot(path=str(out/"centrum-with-verified-schema-test-fixture.png"),animations="disabled")
    page.locator(".bc-game").first.click()
    expect(page.locator("#bc-dialog-title")).to_have_text("Mecz NBA")
    assert "78" in page.locator("#bc-dialog-body").inner_text()
    page.locator("[data-centre-close]").first.click()
    page.locator(".bc-premium-top").click()
    expect(page.locator("#bc-dialog")).to_be_visible()
    expect(page.locator("#bc-dialog-title")).to_have_text("BestBets Premium — wkrótce")
    assert "NIE" in page.locator("#bc-dialog-body").inner_text()
    page.locator("[data-centre-close]").last.click()
    expect(page.locator("#bc-dialog")).to_be_hidden()
    page.locator(".bc-pick").first.click()
    # Props wrapper has zero intrinsic height (children are absolute);
    # test the actual visible hero instead of wrapper geometry.
    expect(page.locator("#hero")).to_be_visible()
    assert page.locator("#props-pane").evaluate("el => getComputedStyle(el).display")=="block"
    expect(page.locator("#bestbets-centre")).to_be_hidden()
    expect(page.locator("#footer")).to_be_visible()
    expect(page.locator(".topsearch")).to_be_visible()
    page.mouse.move(5,5)
    page.screenshot(path=str(out/"player-props-after-centrum.png"),animations="disabled")
    page.locator('.nav-btn[data-page="home"]').click()
    expect(home).to_be_visible()
    assert page.locator("#bestbets-centre").evaluate("el => el.scrollWidth <= el.clientWidth+3")


def check_streamlit(browser,url,out):
    for width,height in [(1664,900),(1366,768),(1920,1080)]:
        context=browser.new_context(viewport={"width":width,"height":height},
                                    device_scale_factor=1,reduced_motion="reduce")
        page=context.new_page()
        errors=[]
        page.on("pageerror",lambda e: errors.append(str(e)))
        page.goto(url,wait_until="domcontentloaded",timeout=50000)
        iframe=page.locator('[data-testid="stMain"] iframe').first
        expect(iframe).to_be_visible(timeout=45000)
        frame=page.frame_locator('[data-testid="stMain"] iframe')
        centre=frame.locator("#bestbets-centre")
        expect(centre).to_be_visible(timeout=45000)
        expect(frame.locator(".bc-hero-title")).to_contain_text("Centrum NBA")
        expect(frame.locator('.nav-btn[data-page="home"]')).to_have_class("nav-btn selected")
        assert frame.locator("#props-pane").is_hidden()
        assert frame.locator(".bc-bottom-item").count()==6
        # During load there are no invented player picks. Once the
        # verified game feed arrives the section can contain up to 3.
        assert frame.locator(".bc-pick").count()<=3
        # A previous production build remained stuck on "Wczytywanie...".
        # Require the real Streamlit component event to return either verified
        # data OR an explicit provider error; never an endless spinner.
        expect(frame.locator("#bc-data-meta")).to_contain_text(
            re.compile(r"^(Dane:|Aktualne dane chwilowo niedostępne:)"),
            timeout=45000,
        )
        stage=frame.locator("#stage")
        stage_box=stage.bounding_box()
        frame_box=iframe.bounding_box()
        assert stage_box and frame_box
        assert abs(stage_box["width"]-frame_box["width"])<4,(stage_box,frame_box)
        assert not errors,errors
        page.screenshot(path=str(out/f"centrum-streamlit-{width}x{height}.png"))
        # Homepage is accessible before the ESPN schedule returns.
        frame.locator('.nav-btn[data-page="props"]').click()
        expect(frame.locator("#hero")).to_be_visible()
        assert frame.locator("#props-pane").evaluate("el => getComputedStyle(el).display")=="block"
        expect(frame.locator("#bestbets-centre")).to_be_hidden()
        assert frame.locator("#hero").is_visible()
        assert frame.locator("#chart-panel").is_visible()
        frame.locator('.nav-btn[data-page="home"]').click()
        expect(centre).to_be_visible()
        context.close()


def main():
    arg=argparse.ArgumentParser()
    arg.add_argument("--url",default="http://127.0.0.1:8501")
    arg.add_argument("--out",type=Path,default=Path("work/centrum-qa"))
    args=arg.parse_args()
    args.out.mkdir(parents=True,exist_ok=True)
    with sync_playwright() as pw:
        browser=pw.chromium.launch(headless=True,args=["--disable-dev-shm-usage"])
        context=browser.new_context(viewport={"width":1231,"height":691},
                                    device_scale_factor=1,reduced_motion="reduce")
        page=context.new_page()
        check_static(page,args.out)
        context.close()
        check_streamlit(browser,args.url,args.out)
        browser.close()
    print("PASS: new Centrum neon layout, free links, Player Props routing and full-width Streamlit")


if __name__=="__main__":
    main()
