"""Full Streamlit + component startup regression, not just raw index.html."""
from playwright.sync_api import sync_playwright

URL="http://127.0.0.1:8501/"

def main():
    with sync_playwright() as pw:
        browser=pw.chromium.launch(headless=True)
        page=browser.new_page(viewport={"width":1664,"height":900},screen={"width":1664,"height":900})
        exceptions=[]
        page.on("pageerror",lambda exc:exceptions.append(str(exc)))
        page.goto(URL,wait_until="domcontentloaded",timeout=60000)
        parent='[data-testid="stMain"] iframe'
        page.locator(parent).first.wait_for(state="attached",timeout=60000)
        panel=page.frame_locator(parent)
        panel.locator("#stage").wait_for(state="attached",timeout=30000)
        first=panel.locator("#stage").bounding_box()
        assert first and first["width"]>1450, f"Miniature first paint: {first}"
        steps=[first["width"]]
        for _ in range(18):
            page.wait_for_timeout(150)
            steps.append(panel.locator("#stage").bounding_box()["width"])
        assert max(steps)-min(steps)<70, f"Startup zoom seen: {steps}"
        assert panel.locator("#player-name").inner_text()=="Wyszukaj zawodnika"
        assert panel.locator(".preview").count()==6
        assert panel.locator("#app-shell").evaluate("(el)=>getComputedStyle(el).visibility")=="visible"
        page.screenshot(path="bestbets_firstpaint_v105.png",full_page=True)
        assert not exceptions,exceptions
        browser.close()
        print("Live Streamlit first-render scale stable:",steps,flush=True)

if __name__=="__main__":
    main()
