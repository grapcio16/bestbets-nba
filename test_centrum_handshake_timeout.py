"""Check missing Streamlit response doesn't strand the free home at Wczytywanie.

This browser test intentionally does NOT run a backend. It exercises the
network/handshake failure case that was not covered by previous green CI.
"""
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

ROOT=Path(__file__).resolve().parent


def test_unresponsive_host(page):
    page.goto((ROOT/"bestbets_reference_frontend"/"index.html").as_uri())
    expect(page.locator("#bestbets-centre")).to_be_visible()
    # The stage exists at startup. Do not touch global scaling/iframe logic.
    before=page.locator("#stage").bounding_box()
    page.wait_for_timeout(100)
    assert page.evaluate("window.__missing__ === undefined")
    # Host intentionally sends no streamlit:render acknowledgement.
    page.clock.run_for(41000)
    expect(page.locator("#bc-data-meta")).to_contain_text("Ponawiam pobieranie.",timeout=6000)
    assert "Wczytywanie" not in page.locator("#bc-ticker-games").inner_text()
    assert "Pobieranie" not in page.locator("#bc-games-list").inner_text()
    assert "Pobieranie" not in page.locator("#bc-finals").inner_text()
    after=page.locator("#stage").bounding_box()
    assert before and after
    assert abs(after["width"]-before["width"])<2
    page.locator('.nav-btn[data-page="props"]').click()
    expect(page.locator("#hero")).to_be_visible()


def test_delayed_success_response(page):
    page.goto((ROOT/"bestbets_reference_frontend"/"index.html").as_uri())
    page.wait_for_timeout(100)
    page.clock.run_for(41000)
    expect(page.locator("#bc-data-meta")).to_contain_text("Ponawiam pobieranie.",timeout=6000)
    sample={"source":"test-only ESPN fixture","games":[],"ticker":[],"finals":[],
            "form":[],"players":[],"as_of":"test","coverage":"synthetic test only"}
    page.evaluate("(home)=>window.postMessage({type:'streamlit:render',args:{payload:{home:home,player:null,error:'',brand:''}}},'*')",sample)
    expect(page.locator("#bc-data-meta")).to_contain_text("Dane:",timeout=6000)
    assert "Ponawiam pobieranie" not in page.locator("#bc-data-meta").inner_text()


def main():
    with sync_playwright() as play:
        browser=play.chromium.launch(headless=True,args=["--disable-dev-shm-usage"])
        for fn in (test_unresponsive_host,test_delayed_success_response):
            ctx=browser.new_context(viewport={"width":1231,"height":691},reduced_motion="reduce")
            pg=ctx.new_page()
            pg.clock.install()
            fn(pg)
            ctx.close()
        browser.close()
    print("PASS: no endless Centrum loading, stable Props after timeout, and delayed recovery")


if __name__=="__main__":
    main()
