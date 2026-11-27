"""Focused visual polish QA. Synthetic payload only; no production data."""
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

ROOT=Path(__file__).resolve().parent
URL=(ROOT/"bestbets_reference_frontend/index.html").as_uri()
OUT=ROOT/"work/directory-polish"
OUT.mkdir(parents=True,exist_ok=True)
def run():
    with sync_playwright() as p:
        browser=p.chromium.launch()
        for width,height in [(1672,941),(1231,691),(390,844),(844,390)]:
            page=browser.new_page(viewport={"width":width,"height":height},reduced_motion="reduce")
            errors=[]
            page.on("pageerror",lambda e:errors.append(str(e)))
            page.goto(URL,wait_until="load")
            def navigate(section):
                desktop=page.locator(f'.nav-btn[data-page="{section}"]')
                if desktop.is_visible():
                    desktop.click()
                else:
                    direct=page.locator(f'#hz-mobile-nav [data-page="{section}"]')
                    if direct.is_visible():
                        direct.click()
                    else:
                        page.locator("#hz-mobile-more-trigger").click()
                        page.locator(f'#hz-mobile-more-panel [data-page="{section}"]').click()
            navigate("players")
            rows=[{"id":"1","name":"Shai Gilgeous-Alexander","team":"OKC","position":"G"},
                  {"id":"2","name":"Giannis Antetokounmpo","team":"MIL","position":"F"}]
            payload={"auth":{"role":"premium","logged_in":True},"player_catalog":{"players":rows},
                     "premium_player_averages":{"id_rows":{"1":{"pts":30.0,"reb":5.0,"ast":6.0,"games":10},"2":{"pts":28.0,"reb":10.0,"ast":5.0,"games":10}}}}
            page.evaluate("d=>window.postMessage({type:'streamlit:render',args:{payload:d}},'*')",payload)
            expect(page.locator(".hzp-player-row")).to_have_count(2)
            expect(page.locator("#hzp-team option").first).to_have_text("Wszystkie")
            name=page.locator(".hzp-player-identity strong").first
            expect(name).to_have_attribute("title","Shai Gilgeous-Alexander")
            assert name.evaluate("e=>getComputedStyle(e).whiteSpace")=="normal"
            assert "tabular-nums" in page.locator(".hzp-stat-primary").first.evaluate("e=>getComputedStyle(e).fontVariantNumeric")
            page.locator(".hzp-player-row").first.click()
            expect(page.locator(".hzp-spotlight-identity h2")).to_have_text("Shai Gilgeous-Alexander")
            mobile=width<768 or height<=500
            if mobile:
                assert page.locator("#app-shell").evaluate("e=>e.classList.contains('hz-mobile-directory')")
                assert page.locator("#stage").evaluate("e=>getComputedStyle(e).transform")=="none"
                assert page.locator(".hzp-player-identity strong").first.evaluate("e=>e.getBoundingClientRect().height>=12")
                assert page.locator("#hzp-next").evaluate("e=>e.getBoundingClientRect().width>=44")
                assert page.locator(".hzp-table-header").evaluate("e=>parseFloat(getComputedStyle(e).fontSize)")>=10
                assert page.evaluate("()=>document.documentElement.scrollWidth<=innerWidth+2")
                page.screenshot(path=str(OUT/f"players-spotlight-{width}.png"),animations="disabled")
                page.evaluate("window.scrollTo(0,0);document.documentElement.scrollTop=0;document.body.scrollTop=0")
            page.screenshot(path=str(OUT/f"players-{width}.png"),animations="disabled")
            expect(page.locator("#hzp-cta-text")).to_contain_text("Historia występów")
            if not mobile:
                spotlight=page.locator(".hzp-spotlight").bounding_box()
                listing=page.locator(".hzp-table-card").bounding_box()
                assert spotlight["y"]+spotlight["height"]<=listing["y"]
                assert abs(spotlight["width"]-listing["width"])<2
            navigate("teams")
            expect(page.locator(".hzt-team-card")).to_have_count(9)
            payload["home"]={"form_available":True,"form_period":"2026/27","form_options":[{"team":"MIN","record_verified":True,"wins":14,"losses":5},{"team":"BOS","record_verified":False,"wins":12,"losses":6}]}
            page.evaluate("d=>window.postMessage({type:'streamlit:render',args:{payload:d}},'*')",payload)
            expect(page.locator("#hzt-feature-win-pct")).to_have_text("—")
            page.locator("#hzt-search").fill("Minnesota")
            card=page.locator('[data-hzt-team="MIN"]')
            expect(card).to_have_count(1)
            expect(card.locator(".hzt-card-body strong")).to_have_attribute("title","Minnesota Timberwolves")
            card.click()
            expect(page.locator("#hzt-modal-name")).to_have_text("Minnesota Timberwolves")
            page.locator("#hzt-modal-close").click()
            expect(page.locator("#hzt-feature-name")).to_have_text("Minnesota Timberwolves")
            expect(page.locator("#hzt-feature-name")).to_have_class("hzt-long-name")
            expect(page.locator("#hzt-feature-games")).to_have_text("19")
            expect(page.locator("#hzt-feature-record")).to_have_text("14–5")
            expect(page.locator("#hzt-feature-win-pct")).to_have_text("73,7%")
            page.locator("#hzt-feature-open").click()
            expect(page.locator("#hzt-modal-name")).to_have_text("Minnesota Timberwolves")
            page.locator("#hzt-modal-close").click()
            if not mobile:
                spot=page.locator(".hzt-spotlight").bounding_box()
                grid=page.locator(".hzt-team-grid").bounding_box()
                assert abs(spot["width"]-grid["width"])<2
                assert spot["y"]+spot["height"]<=grid["y"]
            assert page.locator(".hzt-spotlight").evaluate("e=>getComputedStyle(e).getPropertyValue('--hzt-spotlight-accent').trim()")=="#66a6eb"
            assert page.locator("#hzt-feature-conference").evaluate("e=>getComputedStyle(e).color")=="rgb(102, 166, 235)"
            page.locator("#hzt-search").fill("")
            expect(page.locator(".hzt-team-card")).to_have_count(9)
            if mobile:
                assert page.locator("#stage").evaluate("e=>getComputedStyle(e).transform")=="none"
                assert page.locator(".hzt-team-card").first.evaluate("e=>e.getBoundingClientRect().height>=100")
                assert page.locator("#hzt-next").evaluate("e=>e.getBoundingClientRect().width>=44")
                assert page.evaluate("()=>document.documentElement.scrollWidth<=innerWidth+2")
                page.evaluate("window.scrollTo(0,0);document.documentElement.scrollTop=0;document.body.scrollTop=0")
            page.screenshot(path=str(OUT/f"teams-{width}.png"),animations="disabled")
            assert "tabular-nums" in page.locator(".hzt-record").first.evaluate("e=>getComputedStyle(e).fontVariantNumeric")
            assert not errors,errors
            page.close()
        browser.close()
    print("Directory polish: names, filters, spotlight, unchanged grid count and team modal OK")
if __name__=="__main__":
    run()
