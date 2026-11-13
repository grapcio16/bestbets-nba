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
from teams import TEAM_FULL

ROOT=Path(__file__).resolve().parent


def check_static(page,out):
    doc=(ROOT/"bestbets_reference_frontend"/"index.html").as_uri()
    page.goto(doc,wait_until="load")
    home=page.locator("#bestbets-centre")
    expect(home).to_be_visible(timeout=15000)
    expect(page.locator('.nav-btn[data-page="home"]')).to_have_class("nav-btn selected")
    expect(page.locator(".bc-hero-title h1")).to_contain_text("Centrum")
    assert page.locator(".bc-panel").count()==6
    assert page.locator(".bc-pick").count()==0
    assert page.locator(".bc-hot").count()==0
    assert page.locator(".topsearch").is_hidden()
    assert page.locator(".suggestions").is_hidden()
    assert page.locator(".utility").is_hidden()
    assert page.locator(".bc-hero").bounding_box()["y"] < 35
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
       "calendar_today":"2026-11-12",
       "calendar_loaded_days":["2026-11-11","2026-11-12","2026-11-13"],
       "calendar_games":[
         {"away":"NYK","home":"MIL","away_logo":"","home_logo":"","day":"2026-11-11",
          "start":"2026-11-11T19:00:00+00:00","state":"final","away_score":106,"home_score":104,"status":"Final"},
         {"away":"BOS","home":"PHI","away_logo":"","home_logo":"","day":"2026-11-12",
          "start":"2026-11-12T19:00:00+00:00","state":"live","away_score":78,"home_score":76,"status":"Q3 06:24"},
         {"away":"DAL","home":"LAL","away_logo":"","home_logo":"","day":"2026-11-13",
          "start":"2026-11-13T21:00:00+00:00","state":"scheduled","away_score":None,"home_score":None,"status":"Scheduled"}],
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
       "form_options":[
          {"team":code,"name":name,"logo":"","wins":0,"losses":0,"sample":0}
          for code,name in TEAM_FULL.items()
       ],
       "players":[
         {"name":"Jayson Tatum","team":"BOS","opponent":"NYK","home_away":"home","market":"PTS","value":26,"date":"2026-11-11","game_id":"401234567","athlete_id":"10"},
         {"name":"Luka Doncic","team":"LAL","opponent":"GSW","market":"AST","value":8,"date":"2026-11-11","game_id":"401234568","athlete_id":"11"},
         {"name":"Nikola Jokic","team":"DEN","opponent":"UTA","market":"REB","value":15,"date":"2026-11-11","game_id":"401234569","athlete_id":"12"}
       ]}
    page.evaluate("(home) => window.postMessage({type:'streamlit:render',args:{payload:{player:null,error:'',brand:'',home:home}}},'*')",fixture)
    expect(page.locator(".bc-game")).to_have_count(1)
    assert page.locator(".bc-game").first.inner_text().find("NA ŻYWO")>=0
    assert page.locator(".bc-ticker-card.live").count()==1
    assert page.locator(".bc-result").count()==1
    assert page.locator(".bc-team-form").count()==1
    # A single dropdown lists all 30 NBA teams; stars are toggleable.
    page.locator("#bc-form-toggle").click()
    expect(page.locator(".bc-form-option")).to_have_count(30)
    expect(page.locator('#bc-form-picker')).to_be_visible()
    page.locator('.bc-form-option [data-centre-favorite="BOS"]').click()
    expect(page.locator(".bc-team-form").first).to_contain_text("BOS")
    expect(page.locator('.bc-team-form [data-centre-favorite="BOS"]')).to_have_text("★")
    page.locator('.bc-form-option [data-centre-favorite="LAL"]').click()
    expect(page.locator(".bc-team-form")).to_have_count(2)
    assert [x.inner_text() for x in page.locator(".bc-team-form strong").all()]==["BOS","LAL"]
    page.locator('.bc-form-option [data-centre-favorite="NYK"]').click()
    expect(page.locator("#bc-form-picker-hint")).to_contain_text("maksymalnie 2")
    assert [x.inner_text() for x in page.locator(".bc-team-form strong").all()]==["BOS","LAL"]
    page.locator('.bc-form-option [data-centre-favorite="BOS"]').click()
    expect(page.locator('.bc-form-option [data-centre-favorite="BOS"]')).to_have_text("☆")
    page.locator("#bc-form-toggle").click()
    expect(page.locator("#bc-form-picker")).to_be_hidden()
    expect(page.locator("#bc-refresh")).to_be_visible()
    assert page.locator("#bc-source-state").inner_text().startswith("●")
    assert page.locator(".bc-pick").count()==3
    assert page.locator(".bc-watch button").count()==3
    # Full player catalog opens only on demand. The browser fixture below is
    # synthetic, never a claim about real ESPN rosters.
    page.locator("#bc-players-toggle").click()
    expect(page.locator("#bc-players-picker")).to_be_visible()
    test_catalog={"players":[
      {"id":"101","name":"Jayson Tatum","team":"BOS"},
      {"id":"102","name":"Stephen Curry","team":"GSW"},
      {"id":"103","name":"Nikola Jokic","team":"DEN"},
      {"id":"104","name":"Victor Wembanyama","team":"SAS"},
    ],"coverage":{"teams_loaded":30,"missing_teams":[],"sparse_teams":[]}}
    page.evaluate("(data) => window.postMessage({type:'streamlit:render',args:{payload:data}},'*')",
        {"player":None,"error":"","brand":"","home":fixture,"player_catalog":test_catalog})
    expect(page.locator(".bc-catalog-athlete")).to_have_count(4)
    page.locator("#bc-players-search").fill("Curry")
    expect(page.locator(".bc-catalog-athlete")).to_have_count(1)
    page.locator("#bc-players-search").fill("")
    for pid in ("102","103","104"):
        page.locator(f'[data-bb-watch-id="{pid}"]').click()
    expect(page.locator(".bc-watch button")).to_have_count(3)
    page.locator('[data-bb-watch-id="101"]').click()
    expect(page.locator("#bc-catalog-help")).to_contain_text("Maksymalnie 3")
    expect(page.locator(".bc-catalog-head")).to_contain_text("3/3")
    page.locator("#bc-players-toggle").click()
    expect(page.locator("#bc-players-picker")).to_be_hidden()
    assert page.locator(".bc-hot").count()==0
    page.screenshot(path=str(out/"centrum-with-verified-schema-test-fixture.png"),animations="disabled")
    page.locator(".bc-game").first.click()
    expect(page.locator("#bc-dialog-title")).to_have_text("Mecz NBA")
    assert "78" in page.locator("#bc-dialog-body").inner_text()
    page.locator("[data-centre-close]").first.click()
    # Date navigation is client-side for prefetched data, scores are visible
    # directly in the scheduled-games row without opening a modal.
    page.locator('[data-centre-day-dir="-1"]').click()
    expect(page.locator("#bc-selected-day")).to_contain_text("11")
    expect(page.locator(".bc-row-score")).to_contain_text("106 : 104")
    assert "Podgląd" not in page.locator(".bc-game-list").inner_text()
    page.locator('[data-centre-day-dir="1"]').click()
    expect(page.locator(".bc-row-score.live")).to_contain_text("78 : 76")
    page.locator('[data-centre-day-dir="1"]').click()
    assert page.locator(".bc-game-list").inner_text().find("Podgląd")>=0
    assert page.locator(".bc-row-score").count()==0
    page.screenshot(path=str(out/"centrum-date-nav-final-scores.png"),animations="disabled")
    # Return to today before other expected fixture interactions.
    page.locator('[data-centre-day-dir="-1"]').click()
    page.locator(".bc-premium-top").click()
    expect(page.locator("#bc-dialog")).to_be_visible()
    expect(page.locator("#bc-dialog-title")).to_have_text("BestBets Premium — wkrótce")
    assert "NIE" in page.locator("#bc-dialog-body").inner_text()
    page.locator("[data-centre-close]").last.click()
    expect(page.locator("#bc-dialog")).to_be_hidden()
    # Free analysis MUST remain inside Centrum and must not run Player Props.
    assert [v.strip() for v in page.locator(".bc-pick-tag").all_inner_texts()] == [
        "PTS","AST","REB"]
    page.locator(".bc-pick").first.click()
    expect(page.locator("#bc-dialog")).to_be_visible()
    expect(page.locator("#bc-dialog-title")).to_contain_text("Jayson Tatum")
    expect(page.locator("#bestbets-centre")).to_be_visible()
    assert page.locator("#props-pane").is_hidden()
    page.evaluate("(home) => window.postMessage({type:'streamlit:render',args:{payload:{player:null,error:'',brand:'',home:home,free_details:{key:'401234567|10|PTS',error:'',data:{verified:true,name:'Jayson Tatum',team:'BOS',opponent:'NYK',date:'2026-11-11',PTS:26,REB:7,AST:5,'3PM':3}}}}},'*')",fixture)
    expect(page.locator(".bc-free-stat")).to_have_count(4)
    assert [v.strip() for v in page.locator(".bc-free-stat strong").all_inner_texts()] == [
       "26","7","5","3"]
    assert page.locator("#props-pane").is_hidden()
    page.locator(".bc-free-premium [data-centre-premium]").click()
    expect(page.locator("#bc-dialog-title")).to_contain_text("Premium")
    page.locator("[data-centre-close]").first.click()
    page.locator('.nav-btn[data-page="props"]').click()
    # Props wrapper has zero intrinsic height (children are absolute);
    # test the actual visible hero instead of wrapper geometry.
    expect(page.locator("#hero")).to_be_visible()
    assert page.locator("#props-pane").evaluate("el => getComputedStyle(el).display")=="block"
    expect(page.locator(".topsearch")).to_be_visible()
    expect(page.locator(".suggestions")).to_be_visible()
    expect(page.locator(".utility")).to_be_visible()
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
        assert frame.locator(".topsearch").is_hidden()
        assert frame.locator(".suggestions").is_hidden()
        assert frame.locator(".bc-hot").count()==0
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
        expect(frame.locator("#bc-refresh")).to_be_visible()
        expect(frame.locator('[data-centre-day-dir="-1"]')).to_be_visible()
        expect(frame.locator('[data-centre-day-dir="1"]')).to_be_visible()
        first=frame.locator("#bc-selected-day").inner_text()
        frame.locator('[data-centre-day-dir="-1"]').click()
        expect(frame.locator("#bc-selected-day")).not_to_have_text(first)
        frame.locator('[data-centre-day-dir="1"]').click()
        expect(frame.locator("#bc-selected-day")).to_have_text(first)
        # Previously CI accepted a backend success while the visible NBA
        # ticker and results remained stuck at their initial placeholders.
        # Requiring all 3 sections to leave loading covers that exact bug.
        for selector in ("#bc-ticker-games","#bc-games-list","#bc-finals"):
            content=frame.locator(selector).inner_text()
            assert "Wczytywanie" not in content and "Pobieranie" not in content, (
                "Dashboard is still loading after first real Streamlit paint",selector,content
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
