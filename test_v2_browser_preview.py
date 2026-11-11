"""Playwright QA against real Streamlit, with frame-by-frame startup evidence.

Start preview_v2.py on port 8501. Run this file; --live additionally exercises
the real NBA/ESPN pipeline. The default suite makes no NBA calls or fixtures.
"""
from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
import numpy as np
from playwright.sync_api import expect, sync_playwright

VIEWPORTS = [(1664, 900), (1366, 768), (1920, 1080),
             (1231, 691), (390, 844), (844, 390)]

# A wait_for(visible) followed by measurements can miss the startup defect.
# Install this in every document BEFORE Streamlit mounts its shadow root.
RECORDER = """(() => {
  window.__bbFrames = [];
  function find(root) {
    const stage = root.querySelector('#stage');
    if (stage) return stage;
    for (const el of root.querySelectorAll('*')) {
      if (el.shadowRoot) { const found = find(el.shadowRoot); if(found) return found; }
    }
  }
  function tick() {
    const stage = find(document);
    if (stage) {
      const r = stage.getBoundingClientRect(), css = getComputedStyle(stage);
      if (r.width > 0 && r.height > 0 && css.visibility === 'visible')
        window.__bbFrames.push({t:performance.now(),x:r.x,y:r.y,width:r.width,height:r.height,
          color:css.color,font:css.fontFamily,lineHeight:css.lineHeight});
    }
    requestAnimationFrame(tick);
  }
  requestAnimationFrame(tick);
})();"""


def assert_canvas(page, width, height):
    stage = page.locator('#stage').bounding_box()
    assert stage, 'Dashboard missing (black-screen regression)'
    scale = min(width / 1231, (height - 4) / 691)
    assert abs(stage['width'] - 1231 * scale) < 1, stage
    assert abs(stage['height'] - 691 * scale) < 1, stage
    assert abs(stage['x'] - (width - stage['width']) / 2) < 1, stage
    for selector in ('#hero', '.topsearch', '#chart-panel', '#side-stats',
                     '#take', '.footer-links', '.preview'):
        for node in page.locator(selector).all():
            r = node.bounding_box()
            assert r and r['width'] > 0 and r['height'] > 0, selector
            assert r['x'] >= -1 and r['y'] >= -1, (selector, r)
            assert r['x'] + r['width'] <= width + 1, (selector, r)
            assert r['y'] + r['height'] <= height + 1, (selector, r)
    assert page.locator('.preview').count() == 6
    assert page.locator('[data-testid="stMain"] iframe').count() == 0
    assert page.locator('[data-testid="stException"]').count() == 0
    return stage


def capture_startup(page, out, width, height, label, navigate):
    navigate()
    expect(page.locator('#player-name')).to_have_text('Wyszukaj zawodnika', timeout=45000)
    captures = []
    for second in (0, 1, 3, 6):
        page.wait_for_function('''second => window.__bbFrames.length &&
          performance.now() - window.__bbFrames[0].t >= second * 1000''', arg=second)
        path = out / f'{label}-{second}s.png'
        page.screenshot(path=str(path))
        (out / f'{label}-frames.json').write_text(json.dumps(page.evaluate('window.__bbFrames')))
        captures.append({'second':second, 'box':assert_canvas(page, width, height), 'file':path.name})
        # Bounding boxes also pass for an all-black rendered surface.
        from PIL import Image
        pixels = np.asarray(Image.open(path).convert('RGB'))
        bright = float((pixels.max(axis=2) > 120).mean())
        assert bright > .01, (path, bright)
    frames = page.evaluate('window.__bbFrames')
    for field in ('x', 'y', 'width', 'height'):
        values = [frame[field] for frame in frames]
        assert max(values) - min(values) < 1, (label, field, values[:8], values[-8:])
    scale = min(width / 1231, (height - 4) / 691)
    assert math.isclose(frames[0]['width'], 1231 * scale, abs_tol=1), frames[0]
    first = frames[0]
    assert first['font'] == 'Inter, Arial, Helvetica, sans-serif', first
    assert first['color'] == 'rgb(244, 248, 255)', first
    assert first['lineHeight'] == 'normal', first
    assert page.locator('.topsearch').evaluate(
        'el => getComputedStyle(el).animationName') == 'search-glow'
    return {'label':label, 'viewport':[width, height], 'frames':frames, 'captures':captures}


def check_interactions(page):
    for route, title in (('home', 'Centrum'), ('simulations', 'Symulacje'),
                         ('games', 'Terminarz'), ('players', 'Zawodnicy'),
                         ('teams', 'Drużyny'), ('shortcuts', 'Skrót wpisywania')):
        page.locator('#card-' + route).click()
        expect(page.locator('#blank-title')).to_have_text(title)
        expect(page.locator('#blank-pane')).to_be_visible()
        page.locator('.nav-btn[data-page="props"]').click()
        expect(page.locator('#hero')).to_be_visible()
    for market in ('PTS', 'REB', 'AST', 'FG3M', 'PRA'):
        page.locator(f'[data-market="{market}"]').click()
        expect(page.locator('#market')).to_have_value(market)
    for period in ('L5', 'L10', 'L15', 'Season'):
        page.locator(f'[data-period="{period}"]').click()
        expect(page.locator(f'[data-period="{period}"]')).to_have_class('on')
    page.locator('#query').fill(' ')
    page.locator('#search-btn').click()
    expect(page.locator('#notice')).to_contain_text('Wpisz')
    # Identical server errors must each clear loading. Rebinding retained DOM
    # on each data update would make one click increment the line twice.
    for i in range(3):
        page.locator('#query').fill('x' * 281 + str(i))
        page.locator('#search-btn').click()
        expect(page.locator('#notice')).to_contain_text('Zapytanie jest zbyt długie.', timeout=15000)
        expect(page.locator('#loader')).to_be_hidden()
        old = float(page.locator('#line').input_value())
        page.locator('#line-plus').click()
        expect(page.locator('#line')).to_have_value(str(old + .5).removesuffix('.0'))


def check_live(page, out):
    page.locator('#query').fill('Nikola Jokic over 25.5 points')
    page.locator('#search-btn').click()
    expect(page.locator('#player-name')).to_have_text('Nikola Jokic', timeout=180000)
    expect(page.locator('#loader')).to_be_hidden()
    expect(page.locator('#notice')).to_be_hidden()
    markets, periods = {}, {}
    for market in ('PTS', 'REB', 'AST', 'FG3M', 'PRA'):
        page.locator(f'[data-market="{market}"]').click()
        markets[market] = page.locator('#chart-svg rect.bb-plot-bar').count()
        assert markets[market] > 0
        for selector in ('#season-avg', '#home-avg', '#away-avg'):
            assert page.locator(selector).inner_text() != '—'
    for period in ('L5', 'L10', 'L15', 'Season'):
        page.locator(f'[data-period="{period}"]').click()
        periods[period] = page.locator('#chart-svg rect.bb-plot-bar').count()
        assert periods[period] > 0
        if period.startswith('L'): assert periods[period] <= int(period[1:])
    assert page.locator('.bb-plot-bar').first.evaluate(
        'el => getComputedStyle(el).animationName') == 'bb-bars-rise'
    page.emulate_media(reduced_motion='reduce')
    assert page.locator('.bb-plot-bar').first.evaluate(
        'el => getComputedStyle(el).animationName') == 'none'
    page.emulate_media(reduced_motion='no-preference')
    page.wait_for_timeout(850)
    page.screenshot(path=str(out / 'live-player-props.png'))
    return {'player':page.locator('#player-name').inner_text(),
            'coverage':page.locator('#hero-sub').inner_text(), 'markets':markets, 'periods':periods}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', default='http://127.0.0.1:8501/')
    parser.add_argument('--out', type=Path, default=Path('work/v2-browser'))
    parser.add_argument('--browser', choices=['chromium', 'firefox', 'webkit'], default='chromium')
    parser.add_argument('--executable', default=os.environ.get('BESTBETS_BROWSER_EXECUTABLE'))
    parser.add_argument('--live', action='store_true')
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    report = {'browser':args.browser, 'runs':[], 'page_errors':[], 'console_errors':[],
              'failed_requests':[], 'http_errors':[], 'live':None}
    with sync_playwright() as kit:
        options = {'headless':True}
        if args.executable: options['executable_path'] = args.executable
        browser = getattr(kit, args.browser).launch(**options)
        report['browser_version'] = browser.version
        try:
            for width, height in VIEWPORTS:
                context = browser.new_context(viewport={'width':width, 'height':height}, device_scale_factor=1)
                context.add_init_script(RECORDER)
                page = context.new_page()
                page.on('pageerror', lambda e: report['page_errors'].append(str(e)))
                page.on('console', lambda m: report['console_errors'].append(m.text) if m.type == 'error' else None)
                page.on('requestfailed', lambda r: report['failed_requests'].append(
                    {'url':r.url.split('?')[0], 'error':r.failure}))
                page.on('response', lambda r: report['http_errors'].append(
                    {'url':r.url.split('?')[0], 'status':r.status}) if r.status >= 400 else None)
                label = f'{width}x{height}'
                report['runs'].append(capture_startup(page, args.out, width, height, label,
                    lambda: page.goto(args.url, wait_until='domcontentloaded', timeout=60000)))
                if width in (1664, 1366, 1920):
                    if args.browser == 'chromium':
                        cdp = context.new_cdp_session(page)
                        cdp.send('Network.enable')
                        cdp.send('Network.setCacheDisabled', {'cacheDisabled':True})
                    report['runs'].append(capture_startup(page, args.out, width, height,
                        label + '-reload', lambda: page.reload(wait_until='domcontentloaded')))
                if width == 1664:
                    check_interactions(page)
                    if args.live: report['live'] = check_live(page, args.out)
                    for w, h in VIEWPORTS:
                        page.set_viewport_size({'width':w, 'height':h})
                        page.wait_for_timeout(100)
                        assert_canvas(page, w, h)
                context.close()
                print(f'{args.browser}: {label} startup and geometry passed', flush=True)
            assert not report['page_errors'], report['page_errors']
            assert not report['console_errors'], report['console_errors']
            if not args.live:
                assert not report['failed_requests'], report['failed_requests']
                assert not report['http_errors'], report['http_errors']
            report['passed'] = True
        finally:
            (args.out / 'results.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
            browser.close()


if __name__ == '__main__':
    main()
