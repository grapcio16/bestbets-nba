"""Mobile FREE schedule smoke: native scrolling and readable single-column games."""
from __future__ import annotations
from pathlib import Path

from playwright.sync_api import sync_playwright

DOC = (Path(__file__).resolve().parent / "bestbets_reference_frontend" / "index.html").as_uri()


def main():
    with sync_playwright() as engine:
        browser = engine.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width":390,"height":844},device_scale_factor=1,has_touch=True,is_mobile=True)
        errors=[]
        page.on("pageerror",lambda exc: errors.append(str(exc)))
        page.goto(DOC,wait_until="load")
        page.locator('#hz-mobile-nav [data-page="games"]').click()
        page.wait_for_function("document.querySelector('#app-shell').classList.contains('hz-mobile-schedule')")
        selected=page.locator(".hzs-date.selected").get_attribute("data-hzs-day")
        games=[
            {"id":str(4018101000+i),"day":selected,"away":"DEN","home":"NOP",
             "state":"final","start":selected+"T02:00:00Z",
             "away_score":112+i,"home_score":107+i}
            for i in range(10)
        ]
        page.evaluate(
            "home => window.postMessage({type:'streamlit:render',args:{payload:{home}}}, '*')",
            {"calendar_today":selected,"calendar_loaded_days":[selected],
             "calendar_games":games,"form_options":[
                {"team":"DEN","name":"Denver Nuggets","wins":7,"losses":3,"ppg":114.1,"record_verified":True},
                {"team":"NOP","name":"New Orleans Pelicans","wins":5,"losses":5,"ppg":111.3,"record_verified":True}]}
        )
        page.wait_for_function("document.querySelectorAll('#hzs-board .hzs-game').length===10")
        pane=page.locator("#schedule-pane").bounding_box()
        assert pane and pane["width"] <= 390 and pane["x"] >= 0, pane
        assert page.locator("#stage").evaluate("el=>getComputedStyle(el).transform") == "none"
        assert page.locator("#hzs-board .hzs-game").count() == 10
        assert len(page.locator("#hzs-board .hzs-rows").evaluate(
            "el=>getComputedStyle(el).gridTemplateColumns.split(' ').filter(Boolean)")) == 1
        assert page.locator(".hz-mobile-nav").is_visible()
        assert page.locator("#hzs-board").evaluate("el=>getComputedStyle(el).overflowY") == "visible"
        assert page.evaluate("document.documentElement.scrollHeight") > 844
        assert page.evaluate("document.documentElement.scrollWidth") <= 394
        page.locator("#hzs-board .hzs-game").first.click()
        assert page.locator("#hzs-game-details").is_visible()
        assert "Pobieranie" in page.locator("#hzs-game-details").inner_text()
        page.mouse.wheel(0,850)
        page.wait_for_timeout(120)
        assert page.evaluate("window.scrollY") > 0
        assert not errors, errors
        browser.close()


if __name__=="__main__":
    main()
