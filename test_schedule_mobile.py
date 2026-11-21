"""Mobile FREE schedule v4 smoke: native scrolling, calendar and separate Game Center."""
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
            "home => {window.__mobileScheduleHome=home; window.postMessage({type:'streamlit:render',args:{payload:{home}}}, '*')}",
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
        assert page.locator("#hzv-day-title").count() == 0
        assert page.locator("#schedule-pane .hzs-footnote").count() == 0
        assert page.locator("#schedule-pane .hzv-sport-nav").count() == 0
        mobile_controls = page.locator(".hzv-controls").bounding_box()
        mobile_hero = page.locator("#hzv-hero").bounding_box()
        assert mobile_controls and mobile_hero
        assert mobile_controls["y"] < mobile_hero["y"]
        assert mobile_hero["height"] <= 115, mobile_hero
        assert len(page.locator("#hzs-board .hzs-rows").evaluate(
            "el=>getComputedStyle(el).gridTemplateColumns.split(' ').filter(Boolean)")) == 2
        assert page.locator("#hzs-board .hzs-mini-bottom").first.evaluate(
            "el => el.scrollHeight <= el.clientHeight + 2")
        first_card = page.locator("#hzs-board .hzs-game").first.bounding_box()
        first_caption = page.locator("#hzs-board .hzs-mini-bottom").first.bounding_box()
        assert first_card and first_caption
        assert first_caption["y"] + first_caption["height"] <= first_card["y"] + first_card["height"] - 3
        assert page.locator(".hz-mobile-nav").is_visible()
        assert page.locator("#hzs-board").evaluate("el=>getComputedStyle(el).overflowY") == "visible"
        heights = page.evaluate("""() => ({
            document: document.documentElement.scrollHeight,
            body: document.body.scrollHeight,
            scrolling: document.scrollingElement?.scrollHeight || 0,
            pane: document.querySelector('#schedule-pane').scrollHeight,
            board: document.querySelector('#hzs-board').scrollHeight,
            viewport: innerHeight
        })""")
        print("Mobile schedule scroll geometry:", heights)
        assert max(heights["document"], heights["body"], heights["scrolling"]) > 844, heights
        widths=page.evaluate("""() => ({
            document:document.documentElement.scrollWidth,body:document.body.scrollWidth,
            pane:document.querySelector('#schedule-pane').scrollWidth, viewport:innerWidth
        })""")
        print("Mobile schedule horizontal geometry:",widths)
        assert max(widths["document"],widths["body"]) <= widths["viewport"]+4, widths
        page.locator("#hzv-calendar-toggle").click()
        assert page.locator("#hzv-calendar-popup").is_visible()
        page.keyboard.press("Escape")
        assert page.locator("#hzv-calendar-popup").is_hidden()
        page.locator("#hzs-board .hzs-game").first.click()
        assert page.locator("#hzv-game-page").is_visible()
        assert "Pobieranie" in page.locator("#hzv-game-content").inner_text()
        assert page.locator("#hzs-board .hzs-game").first.is_hidden()
        # Render real-shaped ESPN metrics and confirm no sideways scroll on a phone.
        page.evaluate(
            "details=>window.postMessage({type:'streamlit:render',args:{payload:{home:window.__mobileScheduleHome,schedule_game_details:details}}},'*')",
            {"id":str(4018101000),"day":selected,"error":"",
             "data":{"id":str(4018101000),"away":"DEN","home":"NOP",
                     "quarters":[],"team_stats":[
                         {"label":"Celne z gry %","away":"44.0%","home":"51.0%"},
                         {"label":"Zbiórki","away":"42","home":"39"},
                         {"label":"Straty","away":"10","home":"17"}
                     ],"leaders":{"away":[],"home":[]},"source":"ESPN"}}
        )
        page.wait_for_function("document.querySelectorAll('.hzv-compare-row').length===3")
        assert page.locator(".hzv-compare-panel").is_visible()
        assert page.locator(".hzv-xfactor-final").is_visible()
        assert "112" in page.locator(".hzv-xfactor-final").inner_text()
        assert page.locator('[data-hzv-metric="Straty"]').get_attribute("data-hzv-advantage") == "away"
        geometry = page.evaluate("""() => ({
            viewport: innerWidth,
            document:document.documentElement.scrollWidth,
            body:document.body.scrollWidth,
            panel:document.querySelector('.hzv-compare-panel').getBoundingClientRect().width,
            card:document.querySelector('.hzv-game-summary').getBoundingClientRect().width,
            tracks:[...document.querySelectorAll('.hzv-compare-bars')].every(
              el=>el.scrollWidth<=el.clientWidth+2)
        })""")
        assert geometry["document"] <= geometry["viewport"] + 4, geometry
        assert geometry["body"] <= geometry["viewport"] + 4, geometry
        assert geometry["panel"] <= geometry["card"], geometry
        assert geometry["tracks"], geometry
        page.locator("#hzv-game-back").click()
        assert page.locator("#hzv-game-page").is_hidden()
        # Same mobile Game Center must keep history available before tipoff.
        page.evaluate("""() => {
            window.__mobileScheduleHome.calendar_games[9].state="scheduled";
            window.postMessage({type:'streamlit:render',
              args:{payload:{home:window.__mobileScheduleHome}}},'*');
        }""")
        page.locator("#hzs-board .hzs-game").last.click()
        assert page.locator("#hzv-game-page").is_visible()
        assert "będą dostępne po meczu" in page.locator("#hzv-game-content").inner_text()
        assert page.locator(".hzv-gc-xfactor").count()==0
        assert page.locator('[data-hzv-history="recent"]').is_visible()
        page.locator("#hzv-game-back").click()
        page.mouse.wheel(0,850)
        page.wait_for_timeout(120)
        scroll = page.evaluate("Math.max(window.scrollY,document.body.scrollTop,document.documentElement.scrollTop)")
        assert scroll > 0, {"scroll":scroll,"heights":heights}
        assert not errors, errors
        browser.close()


if __name__=="__main__":
    main()
