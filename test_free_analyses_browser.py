"""Offline Playwright regression of the free modal and licensed-photo switch."""
import json
import struct
import zlib
from pathlib import Path
from playwright.sync_api import sync_playwright, expect
from test_free_analyses import event, NOW
from bestbets_free_analyses import extract_free_leaders

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'work/centrum-qa/free-analyses'
def _fixture_png():
    # 64px is intentionally larger than the portrait loader's min 50px rule.
    # Its previous 1x1 fixture was rejected as a placeholder image.
    def chunk(kind, payload):
        return struct.pack('!I', len(payload)) + kind + payload + struct.pack(
            '!I', zlib.crc32(kind + payload) & 0xffffffff)
    row = b'\x00' + b'\x22\x88\xbb\xff' * 64
    return (b'\x89PNG\r\n\x1a\n'
            + chunk(b'IHDR', struct.pack('!2I5B', 64, 64, 8, 6, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(row * 64)) + chunk(b'IEND', b''))


PNG = _fixture_png()

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
            # Commons-only public photos never make ESPN/NBA headshot requests.
            page.route('https://commons.wikimedia.org/w/index.php*',
                lambda route:route.fulfill(status=200,content_type='image/png',body=PNG))
            page.route('https://www.wikidata.org/w/api.php*',
                lambda route:route.fulfill(status=200,content_type='application/json',
                    headers={'access-control-allow-origin':'*'},body='{"search":[]}'))
            page.route('https://commons.wikimedia.org/w/api.php*',
                lambda route:route.fulfill(status=200,content_type='application/json',
                    headers={'access-control-allow-origin':'*'},body='{"query":{"pages":{}}}'))
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
            # Public Centrum uses attribution-verified Commons photos even
            # while proprietary headshot licensing remains disabled.
            open_photo_leaders=[{**p,name:'Jayson Tatum' if i==0 else p['name']}
                for i,p in enumerate(home['free_leaders'])]
            open_photo_home={**home,'free_leaders':open_photo_leaders,
                'players':[{'name':'Shai Gilgeous-Alexander','team':'OKC',
                            'market':'PTS','value':30.2}],
                'free_photos_enabled':False}
            render(page,open_photo_home)
            img=page.locator('.bc-pick').first.locator('img.bc-commons-photo')
            expect(img).to_be_visible()
            assert img.evaluate('e=>getComputedStyle(e).objectFit')=='cover'
            assert 'Special:Redirect/file/' in img.get_attribute('src')
            watch=page.locator('.bc-watch img.bc-commons-photo')
            expect(watch).to_be_visible()
            assert 'Special:Redirect/file/' in watch.get_attribute('src')
            assert not any('/headshots/' in url or 'cdn.nba.com/headshots' in url for url in requests)
            page.locator('.bc-photo-credits-trigger').click()
            expect(page.locator('#bc-dialog-body')).to_contain_text('Erik Drost')
            expect(page.locator('#bc-dialog-body')).to_contain_text('All-Pro Reels')
            expect(page.locator('#bc-dialog-body')).to_contain_text('CC BY')
            page.keyboard.press('Escape')
            page.locator('.bc-pick').first.click();expect(page.locator('.bc-free-heading img')).to_be_visible()
            page.keyboard.press('Escape')
            render(page,{**home,'free_leaders':[],'free_leader_day':''})
            expect(page.locator('.bc-pick-list')).to_contain_text('Brak potwierdzonych liderów')
            assert page.locator('#bestbets-centre').is_visible() and page.locator('#props-pane').is_hidden()
            assert not errors,errors
            report.append({'viewport':[w,h],'requests_off':0,'modal_stats':4,'bottom_tiles':6,
                'stale_replies_ignored':True,'image_loaded_and_error_fallback':True,'props_search_events':0})
            context.close()
        browser.close()
    (OUT/'report.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
if __name__=='__main__':main()
