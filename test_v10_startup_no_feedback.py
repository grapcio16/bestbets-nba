"""QA for the ONLY intended v10 change: remove iframe height feedback.

Run using: python test_v10_startup_no_feedback.py --url http://127.0.0.1:8501
The browser is Chromium (Opera still needs a human check on Windows).
"""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from PIL import Image, ImageChops
from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parent
FRONTEND = ROOT / "bestbets_reference_frontend" / "index.html"
ORIGINAL_LINE = '  notify("streamlit:setFrameHeight",{height:Math.ceil(691*scale)+2});'
NEW_COMMENT = """  // Do NOT report scaled content height back to Streamlit: its iframe already
  // has a fixed viewport height from bestbets_custom_screen.py. Reporting
  // height here creates a self-amplifying resize loop during startup."""


def baseline_source() -> str:
    return subprocess.check_output(
        ["git", "show", "origin/main:bestbets_reference_frontend/index.html"],
        cwd=ROOT, text=True, encoding="utf-8"
    )


def check_no_visual_code_edits(original: str, fixed: str) -> None:
    assert fixed.count(NEW_COMMENT) == 1, "Missing expected minimal fix"
    assert ORIGINAL_LINE not in fixed, "The feedback bug still exists"
    assert fixed.replace(NEW_COMMENT, ORIGINAL_LINE) == original, (
        "Unexpected HTML, CSS, colors, layout, animation, or business-logic changes"
    )


RECORDER = """(() => {
  if (self === top) return;
  window.__bbFirstPaintSamples=[];
  function frame(){
    const stage=document.getElementById('stage');
    if(stage){
      const b=stage.getBoundingClientRect();
      if(b.width>0 && b.height>0)
        window.__bbFirstPaintSamples.push({t:performance.now(),w:b.width,h:b.height,x:b.x});
    }
    if(window.__bbFirstPaintSamples.length<550) requestAnimationFrame(frame);
  }
  requestAnimationFrame(frame);
})();"""


def check_actual_streamlit(browser, url: str, out: Path) -> list[dict]:
    results=[]
    for width, height in [(1664, 900), (1366, 768), (1920, 1080)]:
        context=browser.new_context(
            viewport={"width":width,"height":height},
            reduced_motion="reduce", device_scale_factor=1
        )
        context.add_init_script(RECORDER)
        page=context.new_page()
        console=[]
        page.on("pageerror",lambda error: console.append(str(error)))
        page.goto(url, wait_until="domcontentloaded", timeout=45000)
        iframe=page.locator('[data-testid="stMain"] iframe').first
        expect(iframe).to_be_visible(timeout=45000)
        stage=page.frame_locator('[data-testid="stMain"] iframe').locator('#stage')
        expect(stage).to_be_visible(timeout=45000)
        page.wait_for_timeout(2400)
        bounds=stage.bounding_box()
        ib=iframe.bounding_box()
        assert bounds and ib, "Blank iframe or stage"
        assert ib["height"] >= height-30, ("Iframe not viewport-sized",height,ib)
        expected=min(width/1231,(ib["height"])/691)*1231
        assert abs(bounds["width"]-expected)<6,(width,height,bounds,ib,expected)
        samples=stage.evaluate("el => window.__bbFirstPaintSamples")
        assert len(samples)>=12,samples
        for axis in ("w","h","x"):
            values=[x[axis] for x in samples]
            assert max(values)-min(values)<1.5, (
                "Progressive zoom remained on first paint",axis,values[:6],values[-6:]
            )
        assert not console,console
        assert stage.locator('.topsearch').count()==1
        assert stage.locator('.preview').count()==6
        assert stage.locator('.nav-btn').count()>=6
        shot=out / f"public-original-look-{width}x{height}.png"
        page.screenshot(path=str(shot))
        stage.locator('.nav-btn[data-page="games"]').click()
        expect(stage.locator('#blank-title')).to_have_text("Terminarz")
        stage.locator('.nav-btn[data-page="props"]').click()
        expect(stage.locator('#hero')).to_be_visible()
        results.append({"width":width,"height":height,
                        "stage_bounds":bounds,"iframe_bounds":ib,
                        "frames":len(samples),"screenshot":str(shot)})
        context.close()
    return results


def check_reference_pixels(browser, original: str, fixed: str, out: Path) -> None:
    # Controlled same-size iframe. Original and fixed images must be
    # visually identical under reduced motion.
    context=browser.new_context(viewport={"width":1664,"height":900},
                                device_scale_factor=1,reduced_motion="reduce")
    page=context.new_page()
    page.set_content("""<style>
       html,body{margin:0;background:#020713}
       iframe{width:100%;height:calc(100dvh - 4px)!important;
              display:block;border:0;background:#020713}
       </style><iframe title="BestBets pixel reference"></iframe>""")
    screenshots=[]
    for key, source in (("baseline",original),("fixed",fixed)):
        page.locator('iframe').evaluate("(el, html) => el.srcdoc=html",source)
        stage=page.frame_locator('iframe').locator('#stage')
        expect(stage).to_be_visible(timeout=12000)
        page.wait_for_timeout(400)
        path=out / f"same-design-{key}.png"
        stage.screenshot(path=str(path),animations="disabled")
        screenshots.append(path)
    im1=Image.open(screenshots[0]).convert("RGB")
    im2=Image.open(screenshots[1]).convert("RGB")
    assert im1.size==im2.size,("Original dimensions changed",im1.size,im2.size)
    difference=ImageChops.difference(im1,im2)
    assert difference.getbbox() is None, (
        "The user-approved public look changed; inspect saved screenshots"
    )
    context.close()


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--url',default="http://127.0.0.1:8501")
    parser.add_argument('--out',type=Path,default=Path('work/v10-startup'))
    args=parser.parse_args()
    args.out.mkdir(parents=True,exist_ok=True)
    original=baseline_source()
    fixed=FRONTEND.read_text(encoding="utf-8")
    check_no_visual_code_edits(original,fixed)
    with sync_playwright() as pw:
        browser=pw.chromium.launch(headless=True,args=["--disable-dev-shm-usage"])
        check_reference_pixels(browser,original,fixed,args.out)
        results=check_actual_streamlit(browser,args.url,args.out)
        browser.close()
    (args.out / "results.json").write_text(
        json.dumps({"original_visuals_identical":True,
                    "startup_stable":True,"runs":results},indent=2),
        encoding="utf-8")
    print("PASS: pixel-identical reference and no progressive iframe zoom")
    for x in results:
        print(x["width"],x["height"],"frames",x["frames"])


if __name__=="__main__":
    main()
