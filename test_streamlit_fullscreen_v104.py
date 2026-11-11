"""Browser smoke against a REAL Streamlit parent iframe.

The standalone HTML smoke cannot detect Streamlit's frame-height feedback
and viewport bug. This test runs app.py in Chromium exactly as served.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

URL = "http://127.0.0.1:8501/"
OUT = Path("reference_streamlit_fullscreen.png")

def main():
    with sync_playwright() as playwright:
        browser=playwright.chromium.launch(headless=True)
        page=browser.new_page(viewport={"width":1664,"height":900},device_scale_factor=1)
        errors=[]
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(URL,wait_until="domcontentloaded",timeout=60000)
        frame_selector='[data-testid="stMain"] iframe'
        page.locator(frame_selector).first.wait_for(state="attached",timeout=60000)
        frame=page.frame_locator(frame_selector)
        frame.locator("#stage").wait_for(state="attached",timeout=30000)
        page.wait_for_timeout(2500)
        def diagnose(tag):
            iframe=page.locator(frame_selector).first
            iframe_box=iframe.bounding_box()
            stage=frame.locator("#stage")
            stage_box=stage.bounding_box()
            dimensions=frame.locator("html").evaluate("""el => ({
              innerWidth:window.innerWidth,innerHeight:window.innerHeight,
              clientWidth:el.clientWidth,clientHeight:el.clientHeight,
              stageTransform:getComputedStyle(document.querySelector('#stage')).transform,
              stageWidth:document.querySelector('#stage').getBoundingClientRect().width,
              stageHeight:document.querySelector('#stage').getBoundingClientRect().height,
              shellVisibility:getComputedStyle(document.querySelector('#app-shell')).visibility
            })""")
            print(json.dumps({"tag":tag,"iframe":iframe_box,"stage":stage_box,"inner":dimensions}),flush=True)
            return iframe_box,stage_box,dimensions
        first=diagnose("first-loaded")
        page.wait_for_timeout(3200)
        last=diagnose("steady")
        page.screenshot(path=str(OUT),full_page=True)
        iframe,stage,inner=last
        assert iframe and stage,"No public BestBets canvas visible"
        assert inner["shellVisibility"]=="visible","Player Props unexpectedly hidden"
        if stage["width"] < 0.90 * page.viewport_size["width"]:
            raise AssertionError(
                f"BestBets canvas is too small on desktop: stage {stage['width']}px / viewport {page.viewport_size['width']}px"
            )
        if abs(first[1]["width"]-last[1]["width"]) > 20:
            raise AssertionError("Startup zoom: dashboard changed width after initial paint")
        assert not errors,errors
        browser.close()
        print("Real Streamlit full-screen and stable-first-paint assertions passed.")

if __name__=="__main__":
    main()
