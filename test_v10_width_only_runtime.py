"""Regression QA: public V10 UI fills width but its iframe still boots.

We intentionally DO NOT change CSS on the Streamlit iframe or remove
streamlit:setFrameHeight; doing that caused an actual blank production page.

    python test_v10_width_only_runtime.py --url http://127.0.0.1:8501
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parent


def source_safety():
    html=(ROOT / "bestbets_reference_frontend" / "index.html").read_text(encoding="utf-8")
    py=(ROOT / "bestbets_custom_screen.py").read_text(encoding="utf-8")
    assert "const scale=viewportWidth/1231;" in html
    assert 'notify("streamlit:setFrameHeight",{height:Math.ceil(691*scale)+2});' in html
    assert "height:calc(100dvh - 4px)!important;" in py
    assert "aspect-ratio:1231 / 691!important" not in py
    assert "componentReady" in html


def smoke(browser, url, width, height, out):
    context=browser.new_context(viewport={"width":width,"height":height},
                                device_scale_factor=1, reduced_motion="reduce")
    page=context.new_page()
    errors=[]
    page.on("pageerror", lambda exc:errors.append(str(exc)))
    page.goto(url, wait_until="domcontentloaded", timeout=50000)
    iframe=page.locator('[data-testid="stMain"] iframe').first
    expect(iframe).to_be_visible(timeout=40000)
    frame=page.frame_locator('[data-testid="stMain"] iframe')
    stage=frame.locator("#stage")
    expect(stage).to_be_visible(timeout=40000)
    expect(frame.locator("#player-name")).to_have_text("Wyszukaj zawodnika", timeout=8000)
    rect=stage.bounding_box()
    fb=iframe.bounding_box()
    assert rect and fb, "Blank iframe or absent stage"
    assert abs(rect["width"]-fb["width"])<4, (
        "Black gutters remain: stage is not as wide as actual iframe",width,height,rect,fb)
    assert abs(rect["height"] - rect["width"]*691/1231)<5, (
        "Approved design aspect ratio changed",rect)
    # Ensure 3 seconds without progressive zoom after the screen appears.
    size=[]
    for _ in range(35):
        r=stage.bounding_box()
        size.append((r["width"],r["height"],r["x"]))
        page.wait_for_timeout(85)
    for axis in range(3):
        values=[v[axis] for v in size]
        assert max(values)-min(values)<1.5,("Unstable startup scale",axis,values[:5],values[-5:])
    assert frame.locator(".preview").count()==6
    # Homepage is the new landing page; navigate back to the unchanged
    # Player Props screen to test the original footer and card reachability.
    expect(frame.locator("#bestbets-centre")).to_be_visible()
    frame.locator('.nav-btn[data-page="props"]').click()
    expect(frame.locator("#footer")).to_be_visible()
    assert not errors,errors
    shot=out / f"v10-full-width-{width}x{height}.png"
    page.screenshot(path=str(shot))
    # Ensure all six footer tiles are reachable by scrolling within iframe.
    # iframe scrolling is intentionally untouched; browser may use its own
    # scroll container, not window, so inspect whether footer actually
    # intersects the frame after scroll_into_view.
    foot=frame.locator("#footer")
    foot.scroll_into_view_if_needed(timeout=10000)
    footbox=foot.bounding_box()
    fb=iframe.bounding_box()
    assert footbox and fb,("Footer not in the DOM",footbox,fb)
    assert footbox["y"] < fb["y"]+fb["height"]+5, (
        "Footer unreachable within the fixed-height iframe",footbox,fb)
    page.screenshot(path=str(out / f"v10-footer-reachable-{width}x{height}.png"))
    stage.locator('.nav-btn[data-page="games"]').click()
    expect(frame.locator('#blank-title')).to_have_text("Terminarz")
    context.close()
    return dict(viewport=[width,height],stage=rect,iframe=fb,stable_frames=len(size))


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--url",default="http://127.0.0.1:8501")
    parser.add_argument("--out",type=Path,default=Path("work/v10-width-only"))
    args=parser.parse_args()
    args.out.mkdir(parents=True,exist_ok=True)
    source_safety()
    with sync_playwright() as play:
        browser=play.chromium.launch(headless=True,args=["--disable-dev-shm-usage"])
        samples=[smoke(browser,args.url,w,h,args.out)
                 for w,h in [(1664,900),(1366,768),(1920,1080)]]
        browser.close()
    (args.out/"evidence.json").write_text(json.dumps(samples,indent=2),encoding="utf-8")
    print("PASS: original look, full-width, stable iframe, scrollable footer; 3 viewports")


if __name__=="__main__":
    main()
