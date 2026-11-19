"""Offline Playwright regression of the free modal and player identity badges."""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright, expect
from test_free_analyses import event, NOW
from bestbets_free_analyses import extract_free_leaders

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'work/centrum-qa/free-analyses'
def render(page,home,details=None):
    page.evaluate("p=>window.postMessage({type:'streamlit:render',args:{payload:p}},'*')",
        {'home':home,'player':None,'brand':'','error':'','free_details':details})

def main():
    OUT.mkdir(parents=True,exist_ok=True);report=[]
    home={'games':[],'ticker':[],'players':[],'form':[],'finals':[],
          'source':'SYNTHETIC LOCAL TEST ONLY',**extract_free_leaders({'events':[event()]},NOW)}
    with sync_playwright() as pw:
        browser=pw.chromium.launch()
        for w,h in [(1920,1080),(1600,900),(1366,768)]:
            context=browser.new_context(viewport={'width':w,'height':h},reduced_motion='reduce')
            page=context.new_page();errors=[];requests=[]
            page.on('pageerror',lambda error:errors.append(str(error)))
            page.on('request',lambda request:requests.append(request.url))
            page.add_init_script("window.__freeEvents=[];window.addEventListener('message',e=>{if(e.data?.type==='streamlit:setComponentValue')window.__freeEvents.push(e.data.value)});")
            page.goto((ROOT/'bestbets_reference_frontend/index.html').as_uri());render(page,home)
            expect(page.locator('.bc-pick')).to_have_count(3)
            assert page.locator('.bc-free-avatar img').count()==0
            assert not any('/headshots/' in url for url in requests)
            for button in page.locator('.bc-bottom-item').all():
                b=button.bounding_box();assert b['y']+b['height']<=h and b['x']>=0 and b['x']+b['width']<=w
            # Same rows do not recreate avatars on unrelated Streamlit rerenders.
            page.locator('.bc-pick').first.evaluate('e=>e.dataset.testPersistent="true"');render(page,home)
            assert page.locator('.bc-pick').first.get_attribute('data-test-persistent')=='true'
            first,second=home['free_leaders'][:2]
            page.locator('.bc-pick').first.click()
            expect(page.locator('#bc-dialog')).to_be_visible()
            assert page.locator('#props-pane').is_hidden()
            expect(page.locator('#bc-dialog-body')).to_contain_text('Pobieram')
            data={**first,'verified':True,'PTS':26,'REB':7,'AST':5,'3PM':3}
            render(page,home,{'key':second['detail_key'],'data':data})
            expect(page.locator('#bc-dialog-body')).to_contain_text('Pobieram')
            render(page,home,{'key':first['detail_key'],'data':data})
            expect(page.locator('.bc-free-stat strong')).to_have_text(['26','7','5','3'])
            expect(page.locator('.bc-free-premium')).to_contain_text('Odkryj więcej z HOOPZARO Premium')
            page.screenshot(path=str(OUT/f'free-details-{w}x{h}.png'),animations='disabled')
            page.keyboard.press('Escape');assert page.locator('#bc-dialog').is_hidden()
            render(page,home,{'key':first['detail_key'],'data':data})
            assert page.locator('#bc-dialog').is_hidden()  # late reply cannot reopen
            page.locator('.bc-pick').nth(1).click()
            render(page,home,{'key':second['detail_key'],'error':'ESPN chwilowo niedostępne'})
            expect(page.locator('#bc-dialog-body')).to_contain_text('ESPN chwilowo niedostępne')
            assert page.locator('.bc-free-stat strong').all_inner_texts()==['—']*4
            page.keyboard.press('Escape')
            events=page.evaluate('window.__freeEvents')
            assert events and all(e['type']=='free_leader_details' for e in events)
            assert all('query' not in e and 'athlete_id' not in e and len(e['key'])==64 for e in events)
            # Missing category retains an honest labelled row.
            render(page,{**home,'free_leaders':home['free_leaders'][:2]})
            expect(page.locator('.bc-free-missing')).to_contain_text('Brak pełnych danych AST')
            # Public Centrum uses one coherent original avatar style, not
            # mismatched in-game/college portraits or unlicensed headshots.
            identity_leaders=[{**p,'name':'Jayson Tatum' if i==0 else p['name']}
                for i,p in enumerate(home['free_leaders'])]
            identity_home={**home,'free_leaders':identity_leaders,
                'players':[{'name':'Shai Gilgeous-Alexander','team':'OKC',
                            'market':'PTS','value':30.2}],
                'free_photos_enabled':False}
            render(page,identity_home)
            badge=page.locator('.bc-pick').first.locator('.bc-identity-avatar')
            expect(badge).to_be_visible()
            assert badge.evaluate('e=>getComputedStyle(e).borderRadius')=='50%'
            assert 'gradient' in badge.evaluate('e=>getComputedStyle(e).backgroundImage')
            watch=page.locator('.bc-watch .bc-identity-avatar')
            expect(watch).to_be_visible()
            assert watch.locator('span').inner_text()=='SG'
            assert page.locator('.bc-pick img.bc-commons-photo,.bc-watch img.bc-commons-photo').count()==0
            assert not any('commons.wikimedia.org' in url or '/headshots/' in url or
                           'cdn.nba.com/headshots' in url for url in requests)
            # An operator-enabled studio-photo setting elsewhere must not
            # reintroduce these inconsistent photos to free Centrum tiles.
            render(page,{**identity_home,'free_photos_enabled':True})
            expect(page.locator('.bc-watch .bc-identity-avatar')).to_be_visible()
            assert page.locator('.bc-watch .bc-identity-avatar img,.bc-pick .bc-identity-avatar img').count()==0
            render(page,identity_home)
            # Credits link is hidden while there are no licensed photographs.
            assert page.locator('.bc-photo-credits-trigger').is_hidden()
            page.locator('.bc-pick').first.click();expect(page.locator('.bc-free-heading .bc-identity-avatar')).to_be_visible()
            page.keyboard.press('Escape')
            render(page,{**home,'free_leaders':[],'free_leader_day':''})
            expect(page.locator('.bc-pick-list')).to_contain_text('Brak potwierdzonych liderów')
            assert page.locator('#bestbets-centre').is_visible() and page.locator('#props-pane').is_hidden()
            assert not errors,errors
            report.append({'viewport':[w,h],'requests_off':0,'modal_stats':4,'bottom_tiles':6,
                'stale_replies_ignored':True,'consistent_identity_badges':True,'props_search_events':0})
            context.close()
        browser.close()
    (OUT/'report.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
if __name__=='__main__':main()
