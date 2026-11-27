"""Offline browser QA: only the existing Centrum game list may change."""
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

ROOT=Path(__file__).resolve().parent
URL=(ROOT/"bestbets_reference_frontend/index.html").as_uri()
OUT=ROOT/"work/centrum-next-game"
OUT.mkdir(parents=True,exist_ok=True)

def fixture(day,away,home,hour="02"):
    return {"id":day+away,"day":day,"start":day+"T"+hour+":00:00+01:00",
            "away":away,"home":home,"state":"scheduled"}

today="2026-11-27"
tomorrow="2026-11-28"
later="2026-11-29"
first=fixture(tomorrow,"MIA","NYK","01")
second=fixture(tomorrow,"MIL","DET","03")
base={"calendar_today":today,"calendar_loaded_days":[today,tomorrow,later],
      "calendar_games":[second,fixture(later,"BOS","ATL"),first],
      "games":[],"ticker":[],"players":[],"form":[],"finals":[],"error":"","stale":False,
      "source":"LOCAL QA FIXTURE"}

def run():
    with sync_playwright() as p:
        browser=p.chromium.launch()
        for width,height in [(1672,941),(390,844)]:
            page=browser.new_page(viewport={"width":width,"height":height})
            errors=[]
            page.on("pageerror",lambda e:errors.append(str(e)))
            page.goto(URL)
            def push(data):
                page.evaluate("p=>window.BestBetsCentre.render(p)",data)
            host=page.locator("#bc-games-list")
            push(base)
            expect(host.locator(".bc-game")).to_have_count(1)
            expect(host).to_contain_text("Najbliższy")
            expect(host).to_contain_text(tomorrow)
            expect(host.locator(".bc-game")).to_contain_text("MIA")
            expect(host.locator(".bc-game")).not_to_contain_text("MIL")
            page.screenshot(path=str(OUT/f"fallback-{width}.png"),animations="disabled")
            # Exercise the real delegate; use DOM click to avoid unrelated mobile
            # viewport clipping in file-based fixture.
            host.locator(".bc-game").evaluate("e=>e.click()")
            expect(page.locator("#bc-dialog-body")).to_contain_text("MIA vs NYK")
            expect(page.locator("#bc-dialog-body")).to_contain_text(tomorrow)
            page.keyboard.press("Escape")
            push({**base,"calendar_games":[fixture(today,"LAL","SAS"),*base["calendar_games"]]})
            expect(host.locator(".bc-game")).to_have_count(1)
            expect(host).to_contain_text("LAL")
            expect(host).not_to_contain_text("Najbliższy")
            for bad in [
                {**base,"calendar_loaded_days":[tomorrow,later]},
                {**base,"calendar_loaded_days":[today,later]},
                {**base,"stale":True},
                {**base,"error":"Źródło niedostępne"},
                {**base,"calendar_extras":{today:{"games":[],"complete":False}}},
                {**base,"calendar_games":[]},
            ]:
                push(bad)
                expect(host.locator(".bc-game")).to_have_count(0)
                expect(host).not_to_contain_text("Najbliższy")
            push({**base,"calendar_games":[fixture(later,"BOS","ATL")]})
            expect(host).to_contain_text(later)
            expect(host.locator(".bc-game")).to_contain_text("BOS")
            push(base)
            page.locator('[data-centre-day-dir="1"]').first.evaluate("e=>e.click()")
            expect(host.locator(".bc-game")).to_have_count(2)
            expect(host).not_to_contain_text("Najbliższy")
            assert not errors,errors
            page.close()
        browser.close()
    print("Centrum next-game fallback: verified coverage, no false fixtures, correct detail and date navigation OK")
if __name__=="__main__":
    run()
