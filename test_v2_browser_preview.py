"""BestBets iframe-free preview browser smoke with zero NBA network calls."""
from pathlib import Path
from playwright.sync_api import sync_playwright

def main():
    with sync_playwright() as browserkit:
        browser=browserkit.chromium.launch(headless=True)
        p=browser.new_page(viewport={"width":1664,"height":900})
        errors=[]
        p.on("pageerror",lambda e:errors.append(str(e)))
        p.goto("http://127.0.0.1:8501/",wait_until="domcontentloaded",timeout=60000)
        canvas=p.locator("#bb-v2-viewport")
        canvas.wait_for(state="visible",timeout=45000)
        hero=p.locator("#hero")
        hero.wait_for(state="visible",timeout=15000)
        initial=canvas.bounding_box()
        assert initial and initial["width"]>=1580,initial
        assert initial["height"]<=899,initial
        assert p.locator("#player-name").inner_text()=="Wyszukaj zawodnika"
        assert p.locator(".preview").count()==6
        assert p.locator('[data-testid="stMain"] iframe').count()==0,"V2 must not mount an iframe"
        checkpoints=[hero.bounding_box()["width"]]
        for _ in range(12):
            p.wait_for_timeout(180)
            checkpoints.append(hero.bounding_box()["width"])
        assert max(checkpoints)-min(checkpoints)<1,checkpoints
        p.locator("#card-games").click()
        assert p.locator("#blank-title").inner_text()=="Terminarz"
        p.locator('.nav-btn[data-page="props"]').click()
        assert p.locator("#hero").is_visible()
        p.locator("#query").fill(" ")
        p.locator("#search-btn").click()
        assert "Wpisz" in p.locator("#notice").inner_text()
        assert not errors,errors
        p.screenshot(path="bestbets_v2_preview_browser.png",full_page=True)
        print(f"Iframe-free layout stable across 12 checks; width={initial['width']:.1f}",flush=True)
        browser.close()

if __name__=="__main__":
    main()
