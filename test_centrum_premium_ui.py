"""Scoped Centrum redesign: reference geometry, pixel-identical Props, real iframe.

python test_centrum_premium_ui.py --url http://127.0.0.1:8520 --out work/centrum-premium
Without --url, the deterministic browser/visual suite runs without NBA network IO.
Synthetic data is confined to this test and labelled as such in its payload.
"""
from __future__ import annotations

import argparse
import base64
from datetime import datetime, timezone
import io
import json
from pathlib import Path
import subprocess
import tempfile

from PIL import Image, ImageChops
from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parent
FRONTEND = ROOT / 'bestbets_reference_frontend'
SIZES = [(1920, 1080), (1600, 900), (1366, 768), (390, 844)]
REFERENCE_SIZE = (1672, 941)
# Manually measured regions in the user-supplied image (not an invented baseline).
REFERENCE_REGIONS = {
    '.bc-hero': (238, 138, 1409, 129),
    '.bc-ticker': (238, 283, 1409, 65),
    '.bc-main-row': (238, 364, 1409, 199),
    '.bc-four-grid': (238, 586, 1409, 145),
    '.bc-hot': (238, 755, 1409, 59),
    '.bc-bottom': (238, 842, 1409, 64),
}
# Data-refresh branch is allowed to update the home feed and its small event
# bridge, but never the approved artboard CSS, props backend or scaling source.
PROTECTED = ['app.py', 'bestbets_reference_frontend/centrum.css',
    'bestbets_reference_frontend/centrum.html', 'assets/bestbets_brand_icon_64.png',
    'core.py', 'mvp_app.py', 'mvp_prop_ui.py', 'season_props.py', 'prop_search.py',
    'simulation_engine.py', 'simulation_sources.py', 'sources.py', 'espn_player_data.py']
BRAND = 'data:image/png;base64,' + base64.b64encode(
    (ROOT / 'assets/bestbets_brand_icon_64.png').read_bytes()).decode()
PLAYER = {'name':'Test Athlete', 'team':'BOS', 'position':'SF', 'opponent':'NYK',
    'season':'2026-27', 'market':'PTS', 'line':25.5, 'side':'OVER',
    'photo':'', 'logo':'', 'source':'SYNTHETIC TEST FIXTURE — NOT NBA FACTS',
    'games':[{'date':f'2026-10-{day}', 'matchup':'TEST @ TEST', 'PTS':pts,
        'REB':5, 'AST':3, 'FG3M':2, 'PRA':pts+8}
        for day, pts in [(22,19), (25,27), (27,30)]]}


def git_file(ref, name):
    return subprocess.check_output(['git', 'show', f'{ref}:{name}'], cwd=ROOT)


def safety(ref):
    for name in PROTECTED:
        assert (ROOT/name).read_bytes() == git_file(ref, name), f'Protected source changed: {name}'
    css = (FRONTEND/'centrum.css').read_text()
    assert 'zoom:' not in css.replace(' ', '')
    assert 'scale(' not in css.replace(' ', '')
    return {'protected_files':PROTECTED, 'unchanged':True, 'new_dashboard_scale':False}


def render(page, player=None, home=None):
    page.evaluate('payload => window.postMessage({type:"streamlit:render",args:{payload}}, "*")',
        {'player':player, 'home':home, 'brand':BRAND, 'error':''})
    expect(page.locator('#brand-img')).to_be_visible()
    page.wait_for_function('document.querySelector("#brand-img").naturalWidth > 0')


def open_home(page, path):
    page.goto(path.as_uri(), wait_until='load')
    expect(page.locator('#bestbets-centre')).to_be_visible()
    render(page)
    page.mouse.move(0, 0)


def rects(page, selector):
    return page.locator(selector).evaluate_all('els => els.map(el => {const b=el.getBoundingClientRect();'
        'return {x:b.x,y:b.y,width:b.width,height:b.height}})')


def non_overlapping(boxes):
    for i, a in enumerate(boxes):
        for b in boxes[i+1:]:
            x = min(a['x']+a['width'], b['x']+b['width'])-max(a['x'], b['x'])
            y = min(a['y']+a['height'], b['y']+b['height'])-max(a['y'], b['y'])
            assert x <= .5 or y <= .5, ('Panels overlap', a, b)


def geometry(page, size):
    major = rects(page, '#bestbets-centre > :not(.bc-dialog-backdrop)')
    non_overlapping(major)
    stage = page.locator('#stage').bounding_box()
    assert stage and stage['width'] >= size[0]-1, ('Blank screen / side gutters', stage)
    for selector, count in [('.bc-main-row>.bc-panel',2), ('.bc-four-grid>.bc-panel',4),
            ('.bc-bottom-item',6)]:
        boxes = rects(page, selector)
        assert len(boxes) == count
        non_overlapping(boxes)
        for box in boxes:
            assert box['width'] > 10 and box['height'] > 10
            assert box['x'] >= -1 and box['x']+box['width'] <= size[0]+1
            assert box['y'] >= -1 and box['y']+box['height'] <= size[1]+1
    # Full names and controls must fit, including BestBets Premium (no ellipsis).
    for selector in ('.bc-bottom-item strong', '.bc-small-head', '.bc-hot-title'):
        overflowing = page.locator(selector).evaluate_all(
            'els => els.filter(e => e.scrollWidth > e.clientWidth+1).map(e=>e.textContent)')
        assert not overflowing, ('Clipped text', selector, overflowing)
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth+1')
    return major


def reference_geometry(page):
    errors = {}
    for selector, expected in REFERENCE_REGIONS.items():
        box = page.locator(selector).bounding_box()
        delta = [abs(box[key]-want) for key, want in zip(('x','y','width','height'), expected)]
        assert max(delta) <= 3, ('Reference proportions drifted', selector, delta)
        errors[selector] = dict(box=box, reference=list(expected), max_delta_px=max(delta))
    return errors


def screenshot(page, path):
    page.mouse.move(0, 0)
    # Flush the route change and its raster repaint before comparing pixels.
    # Fractional mobile canvas transforms otherwise retain a previous cached
    # shadow for one frame even when computed styles are already identical.
    page.evaluate('()=>new Promise(done=>requestAnimationFrame(()=>requestAnimationFrame(done)))')
    return page.screenshot(path=str(path), animations='disabled', caret='hide')


def pixel_identity(browser, baseline, size, out):
    results = []
    for name, player in [('empty',None), ('test-fixture',PLAYER)]:
        images = []
        for label, path in [('before',baseline), ('after',FRONTEND/'index.html')]:
            context = browser.new_context(viewport=dict(zip(('width','height'),size)),
                device_scale_factor=1, reduced_motion='reduce')
            page = context.new_page()
            open_home(page, path)
            render(page, player=player)
            page.locator('.nav-btn[data-page="props"]').click()
            expect(page.locator('#hero')).to_be_visible()
            expect(page.locator('#bestbets-centre')).to_be_hidden()
            if player:
                expect(page.locator('#player-name')).to_have_text('Test Athlete')
                assert page.locator('#chart-svg .bb-plot-bar').count() == 3
            shot = screenshot(page, out/f'props-{name}-{label}-{size[0]}x{size[1]}.png')
            images.append(Image.open(io.BytesIO(shot)).convert('RGB'))
            context.close()
        diff = ImageChops.difference(*images)
        assert diff.getbbox() is None, ('Player Props changed pixels', size, name, diff.getbbox())
        results.append({'viewport':size, 'state':name, 'different_pixels':0})
    return results


def interactions(page, out):
    # Max allowed content: the existing JS renders five games and two results.
    game = {'away':'TEST A', 'home':'TEST B', 'start':'2026-11-12T19:00:00+00:00',
        'state':'scheduled', 'away_logo':'', 'home_logo':'', 'status':'TEST FIXTURE'}
    home = {'source':'SYNTHETIC TEST FIXTURE — NOT REAL NBA', 'as_of':'test-only',
        'day_label':'Dziś', 'games':[game]*5, 'ticker':[game]*5,
        'finals':[], 'form':[], 'players':[
          {'name':'Jayson Tatum','team':'BOS','market':'PTS','value':26,'date':'2026-11-11'},
          {'name':'Luka Doncic','team':'LAL','market':'AST','value':8,'date':'2026-11-11'},
          {'name':'Nikola Jokic','team':'DEN','market':'REB','value':15,'date':'2026-11-11'}]}
    render(page, home=home)
    expect(page.locator('.bc-game')).to_have_count(5)
    expect(page.locator('.bc-ticker-card')).to_have_count(5)
    assert page.locator('.bc-game-list').evaluate(
        'e=>e.getBoundingClientRect().bottom <= e.closest(".bc-panel").getBoundingClientRect().bottom')
    page.locator('.bc-game').first.click()
    expect(page.locator('#bc-dialog-title')).to_have_text('Mecz NBA')
    page.keyboard.press('Escape')
    page.locator('[data-centre-all-games]').click()
    expect(page.locator('#bc-dialog-title')).to_have_text('Terminarz NBA — pobrane spotkania')
    page.locator('[data-centre-close]').last.click()
    page.locator('.bc-premium-top').click()
    expect(page.locator('#bc-dialog-title')).to_have_text('BestBets Premium — wkrótce')
    assert 'NIE' in page.locator('#bc-dialog-body').inner_text()
    page.keyboard.press('Escape')
    for nav, title in [('simulations','Symulacje'), ('games','Terminarz'),
            ('players','Zawodnicy'), ('teams','Drużyny')]:
        page.locator(f'.bc-bottom-item[data-centre-nav="{nav}"]').click()
        expect(page.locator('#blank-title')).to_have_text(title)
        page.locator('.nav-btn[data-page="home"]').click()
    page.locator('.bc-premium-item').click()
    expect(page.locator('#bc-dialog')).to_be_visible()
    page.keyboard.press('Escape')
    page.locator('.bc-watch button').first.click()
    expect(page.locator('#hero')).to_be_visible()
    expect(page.locator('#query')).to_have_value('Jayson Tatum over 25.5 points')
    page.locator('.nav-btn[data-page="home"]').click()
    page.locator('.bc-pick').nth(2).click()
    expect(page.locator('#query')).to_have_value('Nikola Jokic over 14.5 rebounds')


STARTUP_PROBE = """(() => {
  window.__centrePaints = [];
  function sample() {
    const stage=document.getElementById('stage'), centre=document.getElementById('bestbets-centre');
    if(stage && centre && !centre.hidden && getComputedStyle(centre).display === 'grid') {
      const b=stage.getBoundingClientRect();
      if(b.width>0 && window.__centrePaints.length<240)
        window.__centrePaints.push({width:b.width,height:b.height,x:b.x,viewport:innerWidth});
    }
  }
  // Component bootstrap may replace the initial document and cancel its first
  // rAF callback. Observe DOM visibility changes for the first visible layout,
  // then sample independently of the iframe's initial animation-frame queue.
  new MutationObserver(sample).observe(document, {childList:true,subtree:true,attributes:true});
  setInterval(sample, 50);
})();"""


def streamlit(browser, url, size, out):
    context = browser.new_context(viewport=dict(zip(('width','height'),size)),
        device_scale_factor=1, reduced_motion='reduce')
    context.add_init_script(STARTUP_PROBE)
    page = context.new_page()
    errors = []
    page.on('pageerror', lambda error:errors.append(str(error)))
    page.goto(url, wait_until='domcontentloaded', timeout=60000)
    iframe = page.locator('[data-testid="stMain"] iframe').first
    expect(iframe).to_be_visible(timeout=45000)
    frame = page.frame_locator('[data-testid="stMain"] iframe')
    expect(frame.locator('#bestbets-centre')).to_be_visible(timeout=45000)
    stage = frame.locator('#stage')
    stage_box, frame_box = stage.bounding_box(), iframe.bounding_box()
    assert abs(stage_box['width']-frame_box['width']) < 2
    # Observe the first visible frame as well as the following three seconds.
    page.wait_for_timeout(3100)
    samples = stage.evaluate('()=>window.__centrePaints')
    assert len(samples) >= 30, ('Startup probe did not observe paint', samples)
    for key in ('width','height','x'):
        values = [s[key] for s in samples]
        assert max(values)-min(values) < 1.5, ('Progressive zoom', key, values[:5], values[-5:])
    assert all(abs(s['width']-s['viewport']) < 2 for s in samples)
    for item in frame.locator('.bc-bottom-item').all():
        item.scroll_into_view_if_needed()
        b = item.bounding_box()
        fb = iframe.bounding_box()
        assert fb['y']-1 <= b['y'] and b['y']+b['height'] <= fb['y']+fb['height']+1
    # Return to the first section before recording the complete live preview.
    frame.locator('.bc-hero').scroll_into_view_if_needed()
    screenshot(page, out/f'centrum-streamlit-{size[0]}x{size[1]}.png')
    frame.locator('.nav-btn[data-page="props"]').click()
    expect(frame.locator('#hero')).to_be_visible()
    expect(frame.locator('#chart-panel')).to_be_visible()
    expect(frame.locator('#bestbets-centre')).to_be_hidden()
    frame.locator('.nav-btn[data-page="home"]').click()
    expect(frame.locator('#bestbets-centre')).to_be_visible()
    assert not errors, errors
    context.close()
    return {'viewport':size, 'first_frame':samples[0], 'stable_paints':len(samples),
        'no_page_errors':True, 'all_six_tiles_reachable':True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', help='Optional running local Streamlit app')
    parser.add_argument('--out', type=Path, default=Path('work/centrum-premium'))
    parser.add_argument('--baseline-ref', default='origin/main')
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    report = {'recorded_at_utc':datetime.now(timezone.utc).isoformat(),
        'baseline_commit':subprocess.check_output(['git','rev-parse',args.baseline_ref],cwd=ROOT).decode().strip(),
        'safety':safety(args.baseline_ref), 'viewports':[], 'props_pixel_comparisons':[],
        'streamlit':[], 'reference_image':{'width':1672,'height':941,
            'comparison':'measured regions + visual inspection; original supplied inline, no pixel-diff file'}}
    with tempfile.TemporaryDirectory(prefix='bestbets-centre-baseline-') as temp:
        baseline = Path(temp)
        for name in ('index.html','centrum.css','centrum.js','centrum.html'):
            (baseline/name).write_bytes(git_file(args.baseline_ref, 'bestbets_reference_frontend/'+name))
        with sync_playwright() as play:
            browser = play.chromium.launch(headless=True)
            report['chromium_version'] = browser.version
            for size in [REFERENCE_SIZE, *SIZES]:
                context = browser.new_context(viewport=dict(zip(('width','height'),size)),
                    device_scale_factor=1, reduced_motion='reduce')
                page = context.new_page()
                open_home(page, baseline/'index.html')
                screenshot(page, args.out/f'centrum-before-{size[0]}x{size[1]}.png')
                open_home(page, FRONTEND/'index.html')
                boxes = geometry(page, size)
                if size == REFERENCE_SIZE:
                    report['reference_image']['regions'] = reference_geometry(page)
                screenshot(page, args.out/f'centrum-after-{size[0]}x{size[1]}.png')
                report['viewports'].append({'viewport':size, 'sections':boxes,
                    'no_overlap':True, 'all_sections_visible':True})
                if size == (1920,1080):
                    interactions(page, args.out)
                context.close()
                report['props_pixel_comparisons'].extend(pixel_identity(browser, baseline/'index.html', size, args.out))
            if args.url:
                report['streamlit'] = [streamlit(browser, args.url, size, args.out) for size in SIZES]
            browser.close()
    (args.out/'results.json').write_text(json.dumps(report, indent=2)+'\n')
    print(f'PASS: {len(report["viewports"])} Centrum sizes, 10 pixel-identical Props comparisons, '
        f'{len(report["streamlit"])} real Streamlit startup checks')


if __name__ == '__main__':
    main()
