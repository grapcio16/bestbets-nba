"""Chromium smoke and visual evidence for the new free Centrum start screen.

Run: python test_centre_browser.py --url http://127.0.0.1:8501
Requires running: streamlit run app.py --server.port 8501
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path

from playwright.sync_api import sync_playwright,expect

ROOT=Path(__file__).resolve().parent


def check_static(page,out):
    doc=(ROOT/"bestbets_reference_frontend"/"index.html").as_uri()
    page.goto(doc,wait_until="load")
    home=page.locator("#bestbets-centre")
    expect(home).to_be_visible(timeout=15000)
    expect(page.locator('.nav-btn[data-page="home"]')).to_have_class("nav-btn selected")
    expect(page.locator(".bc-hero-title h1")).to_contain_text("Centrum")
    assert page.locator(".bc-panel").count()==6
    assert page.locator(".bc-pick").count()==3
    assert page.locator(".bc-bottom-item").count()==6
    assert page.locator("#footer").is_hidden()
    assert page.locator("#props-pane").is_hidden()
    assert home.evaluate("el => getComputedStyle(el).display")=="grid"
    assert home.bounding_box()["width"]>=1030
    assert page.locator(".bc-hero").evaluate(
        "el => getComputedStyle(el).borderTopColor")!="rgb(0, 0, 0)"
    page.screenshot(path=str(out/"centrum-design-1231x691.png"),animations="disabled")
    page.locator(".bc-premium-top").click()
    expect(page.locator("#bc-dialog")).to_be_visible()
    expect(page.locator("#bc-dialog-title")).to_have_text("BestBets Premium — wkrótce")
    assert "NIE" in page.locator("#bc-dialog-body").inner_text()
    page.locator("[data-centre-close]").last.click()
    expect(page.locator("#bc-dialog")).to_be_hidden()
    page.locator(".bc-pick").first.click()
    expect(page.locator("#props-pane")).to_be_visible()
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
        assert frame.locator(".bc-pick").count()==3
        stage=frame.locator("#stage")
        stage_box=stage.bounding_box()
        frame_box=iframe.bounding_box()
        assert stage_box and frame_box
        assert abs(stage_box["width"]-frame_box["width"])<4,(stage_box,frame_box)
        assert not errors,errors
        page.screenshot(path=str(out/f"centrum-streamlit-{width}x{height}.png"))
        # Homepage is accessible before the ESPN schedule returns.
        frame.locator('.nav-btn[data-page="props"]').click()
        expect(frame.locator("#props-pane")).to_be_visible()
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
