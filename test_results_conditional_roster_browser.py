"""Regression for Results conditional banner never hiding populated player rows.

Synthetic fixtures are test-only, not actual NBA injury or model forecasts.
"""
from pathlib import Path
from shutil import which
from playwright.sync_api import sync_playwright

from test_results_distributions_premium_browser import fixture

ROOT=Path(__file__).parent
URL=(ROOT/"bestbets_reference_frontend"/"index.html").as_uri()
OUT=ROOT/"test-results"/"results-conditional-rows"
OUT.mkdir(parents=True, exist_ok=True)


def run():
    with sync_playwright() as p:
        exe=which("chromium") or which("google-chrome")
        browser=p.chromium.launch(headless=True,args=["--no-sandbox"],
                                   **({"executable_path":exe} if exe else {}))
        for width,height,label in ((1672,941,"desktop"),(390,844,"iphone")):
            phone=width<600
            page=browser.new_page(viewport={"width":width,"height":height},
                                  device_scale_factor=1,is_mobile=phone,
                                  has_touch=phone)
            page.clock.set_fixed_time("2026-11-23T12:00:00Z")
            errors=[]
            page.on("pageerror",lambda e:errors.append(str(e)))
            page.goto(URL,wait_until="load")
            nav=page.locator('#hz-mobile-nav [data-page="simulations"]')
            if nav.is_visible():
                nav.click()
            else:
                page.locator('.nav-btn[data-page="simulations"]').click()
            data=fixture()
            pack=data["premium_simulation"]["players"]
            pack["players"]=[
                {"name":f"QA Player {i:02d}","team":"NYK" if i%2 else "IND",
                 "availability":"Niezweryfikowany",
                 "pts":round(11.4+i*.59,1),"reb":round(2.2+i*.17,1),
                 "ast":round(1.3+i*.23,1)} for i in range(1,25)
            ]
            pack["injury_watch"]={"fresh":False,"rows":[],
                                  "reason":"ESPN feed unavailable"}
            pack["availability_conditional"]=True
            pack["availability_policy"]="Jeśli zawodnik wystąpi"
            def push():
                page.evaluate(
                    "d => window.postMessage({type:'streamlit:render',args:{payload:d}},'*')",
                    data)
            push()
            page.wait_for_function(
                "() => document.querySelector('#hzm-score')?.textContent.includes('115 : 116')")
            page.wait_for_function(
                "() => document.querySelectorAll('#hzm-player-rows .hzm-player-row').length===5")
            banner=page.locator("#hzm-player-rows .hzm-conditional-warning")
            assert banner.count()==1,(label,"missing conditional warning")
            assert "warunkowe" in banner.inner_text().lower()
            assert page.locator("#hzm-player-rows .hzm-no-players").count()==0
            assert page.locator("#hzm-players-panel #hzm-expand-players").inner_text().find("(24)")>=0
            assert page.locator("#hzm-player-rows .hzm-player-row").count()==5
            layout=page.evaluate("""() => {
              const rect=s=>{const r=document.querySelector(s).getBoundingClientRect();
                return {top:r.top,bottom:r.bottom,height:r.height,width:r.width}};
              return {list:rect('#hzm-player-rows'),
                banner:rect('#hzm-player-rows .hzm-conditional-warning'),
                first:rect('#hzm-player-rows .hzm-player-row'),
                second:rect('#hzm-player-rows .hzm-player-row:nth-of-type(3)'),
                listCount:document.querySelectorAll('#hzm-player-rows .hzm-player-row').length};
            }""")
            assert layout["banner"]["height"]<=48,(label,layout)
            assert layout["banner"]["bottom"]<=layout["first"]["top"]+1,(label,layout)
            assert layout["first"]["top"]>=layout["list"]["top"]-1,(label,layout)
            assert layout["first"]["bottom"]<=layout["list"]["bottom"]+2,(label,layout)
            assert layout["second"]["bottom"]<=layout["list"]["bottom"]+2,(label,layout)
            # Results sorts predicted PTS descending: highest five players
            # are visible, not the oldest in the synthetic source list.
            assert "QA Player 24" in page.locator("#hzm-player-rows").inner_text()
            assert "QA Player 22" in page.locator("#hzm-player-rows").inner_text()
            row=page.locator("#hzm-player-rows .hzm-player-row").first
            assert row.locator(".hzm-player-stats span").count()==4
            assert all(x.strip() not in ("","—") for x in row.locator(".hzm-player-stats span").all_inner_texts())
            page.screenshot(path=str(OUT/f"{label}-conditional-visible.png"),
                            full_page=True)
            page.locator("#hzm-expand-players").click()
            assert page.locator("#hzm-player-rows .hzm-player-row").count()==24
            last=page.locator("#hzm-player-rows .hzm-player-row").last
            last.scroll_into_view_if_needed()
            assert last.is_visible()
            page.screenshot(path=str(OUT/f"{label}-expanded-24.png"),
                            full_page=True)
            # Fresh report removes warning, while still rendering all rows.
            pack["availability_conditional"]=False
            pack["injury_watch"]={
                "fresh":True,"checked_at":"2026-11-23T11:40:00Z",
                "valid_until":"2026-11-23T13:00:00Z","rows":[]}
            push()
            assert banner.count()==0
            assert page.locator("#hzm-player-rows .hzm-player-row").count()==24
            assert not errors,(label,errors)
            page.close()
        browser.close()
    print("Results Premium conditional warning preserves 24 player rows, "
          "visible PTS/REB/AST/PRA, compact warning and expanded view.")


if __name__=="__main__":
    run()
