"""Deterministic Game Center QA; all example scores stay in this test only."""
from __future__ import annotations
import argparse
import copy
import json
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parent
DOC = (ROOT / "bestbets_reference_frontend/index.html").as_uri()
PERIODS = [{"period":f"Q{i+1}","away":a,"home":h}
           for i,(a,h) in enumerate([(31,23),(26,33),(19,31),(21,24)])]
HISTORY = [
    {"id":str(401999100+i),"start":date+"T00:00:00Z","away":a,"home":h,
     "away_score":av,"home_score":hv,"state":"final"}
    for i,(date,a,h,av,hv) in enumerate([
        ("2026-10-24","ATL","CHA",128,81), ("2026-02-12","ATL","CHA",107,110),
        ("2026-02-08","CHA","ATL",126,119), ("2025-12-19","ATL","CHA",126,133),
        ("2025-11-24","CHA","ATL",110,113)])]


def payload(day, *, away_score=97, home_score=111, state="final", quarters=None):
    game={"id":"401999001","day":day,"start":day+"T00:00:00Z","away":"CHA","home":"ATL",
          "away_score":away_score,"home_score":home_score,"state":state}
    home={"calendar_today":day,"calendar_loaded_days":[day],"calendar_games":[game],
          "source":"SYNTHETIC LOCAL QA FIXTURE — NOT PUBLIC NBA DATA", "form_options":[
              {"team":"CHA","name":"Charlotte Hornets"},
              {"team":"ATL","name":"Atlanta Hawks"}]}
    other={"id":"401999999","start":"2026-11-10T00:00:00Z","away":"CHA","home":"ORL",
           "away_score":100,"home_score":115,"state":"final"}
    details={"id":game["id"],"day":day,"data":{"away":"CHA","home":"ATL",
        "quarters":copy.deepcopy(PERIODS if quarters is None else quarters),
        "team_stats":[{"label":"Celne z gry %","away":"40.0%","home":"51.0%"}],
        "leaders":{"away":[],"home":[{"name":"Test Scoring Leader","pts":26,"reb":6,"ast":6}]},
        "history":{"h2h":HISTORY,"recent":{"CHA":[other],"ATL":[HISTORY[0]]}}}}
    return {"home":home,"schedule_game_details":details,"auth":{"role":"guest"}}


def render(page, data):
    page.evaluate("p=>window.postMessage({type:'streamlit:render',args:{payload:p}},'*')",data)
    expect(page.locator(".hzv-gc-xfactor")).to_be_visible()


def geometry(page):
    return page.evaluate("""() => {
      const overflow=[...document.querySelectorAll('.hzv-history-row,.hzv-history-date,.hzv-history-participant,.hzv-history-score,.hzv-gc-team small')]
        .filter(e=>e.clientWidth>0&&e.scrollWidth>e.clientWidth+1).map(e=>e.textContent);
      const boxes=[...document.querySelectorAll('.hzv-quarter-endpoint rect')].map(e=>e.getBoundingClientRect());
      const labelsOverlap=boxes.length===2 && Math.min(boxes[0].bottom,boxes[1].bottom)>
        Math.max(boxes[0].top,boxes[1].top)+.5;
      const svg=document.querySelector('.hzv-xfactor-chart svg')?.getBoundingClientRect();
      const card=document.querySelector('.hzv-gc-xfactor').getBoundingClientRect();
      return {viewport:innerWidth,document:document.documentElement.scrollWidth,overflow,
        labelsOverlap,chartInside:!svg||(svg.left>=card.left&&svg.right<=card.right+1&&svg.bottom<=card.bottom)};
    }""")


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out",type=Path,default=ROOT/"work/game-center-premium")
    args=parser.parse_args();args.out.mkdir(parents=True,exist_ok=True)
    report=[]
    with sync_playwright() as pw:
        browser=pw.chromium.launch()
        for w,h in [(1920,1080),(1710,998),(1600,900),(1366,768),(768,1024),
                    (430,932),(390,844),(360,800),(320,720),(844,390)]:
            context=browser.new_context(viewport={"width":w,"height":h},reduced_motion="reduce")
            page=context.new_page();errors=[];page.on("pageerror",lambda e:errors.append(str(e)))
            page.goto(DOC,wait_until="load")
            mobile=w<768 or (w<=1200 and h<=500)
            page.locator('#hz-mobile-nav [data-page="games"]' if mobile else '.nav-btn[data-page="games"]').click()
            day=page.locator(".hzs-date.selected").get_attribute("data-hzs-day")
            data=payload(day)
            page.evaluate("p=>window.postMessage({type:'streamlit:render',args:{payload:p}},'*')",data)
            page.locator('[data-hzs-game="401999001"]').first.click()
            expect(page.locator('.hzv-gc-team.is-winner')).to_have_attribute("data-hzv-team","ATL")
            expect(page.locator('.hzv-winner-badge')).to_have_text("ZWYCIĘZCA")
            expect(page.locator('.hzv-quarter-total.is-winner')).to_have_text("111")
            expect(page.locator('.hzv-quarter-endpoint[data-hzv-team="ATL"]')).to_have_attribute("data-hzv-points","111")
            expect(page.locator('.hzv-quarter-endpoint[data-hzv-team="CHA"]')).to_have_attribute("data-hzv-points","97")
            expect(page.locator('.hzv-gc-callout')).to_contain_text("12 pkt (Q3)")
            for row, fixture in zip(page.locator('.hzv-history-row').all(),HISTORY):
                winner=fixture['away'] if fixture['away_score']>fixture['home_score'] else fixture['home']
                expect(row).to_have_attribute('data-hzv-winner',winner)
                expect(row.locator('.hzv-history-participant.is-winner')).to_have_attribute('data-hzv-team',winner)
                color="rgb(32, 233, 244)" if winner=="CHA" else "rgb(223, 131, 255)"
                assert row.locator('.hzv-score-value.is-winner').evaluate('e=>getComputedStyle(e).color')==color
            dims=geometry(page);assert not dims['overflow'],dims
            assert dims['document']<=w+1 and dims['chartInside'] and not dims['labelsOverlap'],dims
            page.screenshot(path=str(args.out/f'home-winner-{w}x{h}.png'),full_page=mobile,animations="disabled")
            page.locator('[data-hzv-history="recent"]').click()
            other=page.locator('.hzv-history-participant.is-winner[data-hzv-team="ORL"]')
            assert other.evaluate('e=>getComputedStyle(e).borderColor')=='rgb(255, 220, 134)'
            assert not geometry(page)['overflow']
            # Away winner, and close endpoint values, still use the club's cyan.
            away=payload(day,away_score=117,quarters=PERIODS[:-1]+[{"period":"Q4","away":41,"home":24}])
            render(page,away)
            expect(page.locator('.hzv-gc-team.is-winner')).to_have_attribute('data-hzv-team','CHA')
            expect(page.locator('.hzv-quarter-total.is-winner')).to_have_text('117')
            assert not geometry(page)['labelsOverlap']
            # Verified overtime totals are displayed as OT1, never as invented quarters.
            ot=payload(day,away_score=111,home_score=114,quarters=PERIODS+[{"period":"OT1","away":14,"home":3}])
            render(page,ot);expect(page.locator('.hzv-period-label').last).to_have_text('OT1')
            assert not geometry(page)['labelsOverlap']
            for broken in [[],PERIODS[:2],PERIODS[:-1]+[{"period":"Q4","away":99,"home":99}]]:
                render(page,payload(day,quarters=broken))
                expect(page.locator('.hzv-xfactor-final')).to_be_visible()
                assert page.locator('.hzv-quarter-endpoint').count()==0
            render(page,payload(day,state='live'))
            assert page.locator('.hzv-winner-badge').count()==0
            render(page,payload(day,away_score=None,quarters=[]))
            assert page.locator('.hzv-winner-badge').count()==0
            assert 'NaN' not in page.locator('#hzv-game-content').inner_text()
            page.locator('#hzv-game-back').click();expect(page.locator('#hzv-game-page')).to_be_hidden()
            assert not errors,errors
            report.append({'viewport':[w,h],'winner_home_and_away':True,'club_colors':True,
                'overtime':True,'safe_fallbacks':True,'geometry':dims,'js_errors':errors})
            context.close()
        browser.close()
    (args.out/'results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
    print(f"PASS: Game Center Premium, {len(report)} viewports, home/away winners, OT, missing data and history colors")


if __name__=='__main__':
    main()
