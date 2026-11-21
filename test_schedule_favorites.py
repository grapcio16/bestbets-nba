"""Chromium checks for free schedule favorites, dates and browser persistence."""
from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from playwright.sync_api import sync_playwright

DOC=(Path(__file__).resolve().parent/"bestbets_reference_frontend"/"index.html").as_uri()
FAV_KEY="hoopzaro.schedule.favoriteTeams.v1"


def fixture(day):
    return {"calendar_today":day,"calendar_loaded_days":[day],
        "calendar_games":[
            {"id":"4018000001","day":day,"away":"NYK","home":"MIN","state":"scheduled","start":day+"T01:00:00Z"},
            {"id":"4018000002","day":day,"away":"DEN","home":"NOP","state":"scheduled","start":day+"T02:00:00Z"},
            {"id":"4018000003","day":day,"away":"LAL","home":"BOS","state":"scheduled","start":day+"T03:00:00Z"},
            {"id":"4018000004","day":day,"away":"PHX","home":"UTA","state":"scheduled","start":day+"T04:00:00Z"}
        ],
        "form_options":[]}


def inject(page,day):
    page.evaluate("home=>window.postMessage({type:'streamlit:render',args:{payload:{home}}},'*')",fixture(day))
    page.wait_for_function("document.querySelectorAll('#hzs-board .hzs-game').length===4")


def exercise(page,mobile=False):
    page.goto(DOC,wait_until="load")
    nav="#hz-mobile-nav" if mobile else "aside"
    page.locator(nav+' [data-page="games"]').click()
    day=page.locator(".hzs-date.selected").get_attribute("data-hzs-day")
    assert day and date.fromisoformat(day)
    inject(page,day)
    assert page.locator(".hzs-favorite-star").count()==8
    assert page.locator("#hzs-board .hzs-favorite-game").count()==0
    assert page.locator("#hzv-calendar-toggle").get_attribute("aria-expanded")=="false"
    assert page.locator("#hzs-today").is_disabled()
    assert page.locator("#hzs-board .hzs-game").count()==4
    # Mark DEN as favorite without opening game details or hiding other cards.
    page.locator('[data-hzs-shell-id="4018000002"] [data-hzs-star="DEN"]').click()
    assert page.locator("#hzs-board .hzs-game").count()==4
    assert page.locator("#hzs-board .hzs-favorite-game").count()==1
    assert page.locator("#hzv-game-page").is_hidden()
    assert page.locator('.hzs-rows').first.locator('[data-hzs-shell-id]').first.get_attribute("data-hzs-shell-id")=="4018000002"
    assert "★ ULUBIONE" in page.locator("#hzs-board").inner_text()
    assert page.locator('[data-hzs-shell-id="4018000002"] [data-hzs-star="DEN"]').get_attribute("aria-pressed")=="true"
    assert "★" in page.locator('[data-hzs-shell-id="4018000002"] [data-hzs-star="DEN"]').inner_text()
    assert "PREMIUM" not in page.locator("#schedule-pane").inner_text()
    persistence=page.evaluate("""key=>{
      try { return JSON.parse(window.localStorage.getItem(key)||'[]').includes('DEN'); }
      catch (_) {return false}
    }""",FAV_KEY)
    # Explicit opt-in filter must show only favorite games; ALL retains all games.
    page.locator('[data-hzs-filter="favorites"]').click()
    assert page.locator("#hzs-board .hzs-game").count()==1
    page.locator('[data-hzs-filter="all"]').click()
    assert page.locator("#hzs-board .hzs-game").count()==4
    # Choosing a date does not require Premium or an extra tab.
    future=(date.fromisoformat(day)+timedelta(days=5)).isoformat()
    page.locator("#hzv-calendar-toggle").click()
    assert page.locator("#hzv-calendar-popup").is_visible()
    if future[:7]!=day[:7]:
        page.locator('[data-hzv-month="1"]').click()
    page.locator(f'[data-hzv-calendar-day="{future}"]').click()
    assert page.locator("#hzv-calendar-popup").is_hidden()
    assert page.locator(".hzs-date.selected").get_attribute("data-hzs-day")==future
    assert page.locator("#hzs-today").is_enabled()
    page.locator("#hzs-today").click()
    assert page.locator(".hzs-date.selected").get_attribute("data-hzs-day")==day
    assert page.locator("#hzs-board .hzs-game").count()==4
    if mobile:
        assert page.locator("#app-shell").evaluate("el=>el.classList.contains('hz-mobile-schedule')")
        assert page.locator(".hzs-rows").first.evaluate("e=>getComputedStyle(e).gridTemplateColumns.split(' ').length")==2
        assert page.locator("#hzs-board .hzs-favorite-game").count()==1
    if persistence:
        page.reload(wait_until="load")
        page.locator(nav+' [data-page="games"]').click()
        inject(page,day)
        assert page.locator('[data-hzs-shell-id="4018000002"] [data-hzs-star="DEN"]').get_attribute("aria-pressed")=="true"
    # Toggling a star off restores the ordinary chronological list.
    page.locator('[data-hzs-shell-id="4018000002"] [data-hzs-star="DEN"]').click()
    assert page.locator("#hzs-board .hzs-favorite-game").count()==0
    assert page.locator("#hzs-board .hzs-game").count()==4
    return persistence


def main():
    with sync_playwright() as playwright:
        browser=playwright.chromium.launch(headless=True)
        desktop=browser.new_page(viewport={"width":1231,"height":691})
        desktop_errors=[]
        desktop.on("pageerror",lambda e:desktop_errors.append(str(e)))
        persistent_desktop=exercise(desktop)
        assert not desktop_errors,desktop_errors
        mobile=browser.new_page(viewport={"width":390,"height":844},device_scale_factor=1,
                                has_touch=True,is_mobile=True)
        mobile_errors=[]
        mobile.on("pageerror",lambda e:mobile_errors.append(str(e)))
        persistent_mobile=exercise(mobile,mobile=True)
        assert not mobile_errors,mobile_errors
        browser.close()
        print("Free schedule favorites/date shortcuts passed; localStorage:",persistent_desktop,persistent_mobile)


if __name__=="__main__":
    main()
