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
            page.locator(".hzp-player-row").first.click()
            expect(page.locator(".hzp-spotlight-identity h2")).to_have_text("Shai Gilgeous-Alexander")
            page.screenshot(path=str(OUT/f"players-{width}.png"),animations="disabled")
            expect(page.locator("#hzp-cta-text")).to_contain_text("Historia występów")
            navigate("teams")
            expect(page.locator(".hzt-team-card")).to_have_count(9)
            page.locator("#hzt-search").fill("Minnesota")
            card=page.locator('[data-hzt-team="MIN"]')
            expect(card).to_have_count(1)
            expect(card.locator(".hzt-card-body strong")).to_have_attribute("title","Minnesota Timberwolves")
            card.click()
            expect(page.locator("#hzt-modal-name")).to_have_text("Minnesota Timberwolves")
            page.locator("#hzt-modal-close").click()
            expect(page.locator("#hzt-feature-name")).to_have_text("Minnesota Timberwolves")
            expect(page.locator("#hzt-feature-name")).to_have_class("hzt-long-name")
            assert page.locator(".hzt-spotlight").evaluate("e=>getComputedStyle(e).getPropertyValue('--hzt-spotlight-accent').trim()")=="#66a6eb"
            assert page.locator("#hzt-feature-conference").evaluate("e=>getComputedStyle(e).color")=="rgb(102, 166, 235)"
            page.locator("#hzt-search").fill("")
            expect(page.locator(".hzt-team-card")).to_have_count(9)
            page.screenshot(path=str(OUT/f"teams-{width}.png"),animations="disabled")
            assert not errors,errors
            page.close()
        browser.close()
    print("Directory polish: names, filters, spotlight, unchanged grid count and team modal OK")
if __name__=="__main__":
    run()
