"""Reproduce v1 feedback and compare v1/V2 style fidelity, without NBA data.

Requires local app.py on 8502 and preview_v2.py on 8501. The feedback case is
a controlled 150px bootstrap host implementing Streamlit's documented height
messages; it is NOT a recording of the public deployment or Opera.
"""
import argparse
import json
from pathlib import Path
import numpy as np
from PIL import Image
from playwright.sync_api import sync_playwright


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=Path('work/scaling-evidence'))
    parser.add_argument('--executable', default=None)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    raw = (Path(__file__).parent / 'bestbets_reference_frontend/index.html').read_text()
    report = {}
    with sync_playwright() as kit:
        options = {'headless':True}
        if args.executable: options['executable_path'] = args.executable
        browser = kit.chromium.launch(**options)
        page = browser.new_page(viewport={'width':1664, 'height':900})
        page.set_content('''<style>body{margin:0;background:#020713}
          iframe{border:0;width:100%;height:150px;display:block}</style><iframe></iframe>''')
        page.evaluate('''html => {
          const frame=document.querySelector('iframe');
          window.__heights=[];
          window.addEventListener('message', e => {
            if(e.source===frame.contentWindow && e.data.type==='streamlit:setFrameHeight'){
              window.__heights.push(e.data.height);
              requestAnimationFrame(()=>frame.style.height=e.data.height+'px');
            }
          });
          frame.srcdoc=html;
        }''', raw)
        stage = page.frame_locator('iframe').locator('#stage')
        stage.wait_for(state='visible')
        boxes = []
        previous = 0
        for second in (0, 1, 3, 6):
            page.wait_for_timeout((second - previous) * 1000)
            boxes.append({'second':second, 'box':stage.bounding_box()})
            page.screenshot(path=str(args.out / f'v1-feedback-{second}s.png'))
            previous = second
        heights = page.evaluate('window.__heights')
        assert boxes[0]['box']['width'] < 600, boxes
        assert boxes[-1]['box']['width'] > boxes[0]['box']['width'] + 100, boxes
        assert len(heights) > 20, heights
        assert all(b - a == 2 for a, b in zip(heights[:20], heights[1:21])), heights[:21]
        report['controlled_v1_feedback'] = {'heights':heights, 'captures':boxes}
        page.close()

        # Compare the two real Streamlit entrypoints at their reference size.
        snapshots = []
        selectors = ['.wordmark', '#hero', '#chart-panel', '#side-stats', '#take',
                     '#card-home', '#card-shortcuts', '#query', '#line']
        for name, port in [('v1', 8502), ('v2', 8501)]:
            page = browser.new_page(viewport={'width':1231, 'height':695})
            page.emulate_media(reduced_motion='reduce')
            page.goto(f'http://127.0.0.1:{port}/')
            root = page.frame_locator('iframe') if name == 'v1' else page
            root.locator('#stage').wait_for(state='visible')
            page.wait_for_timeout(200)
            snapshot = {}
            for selector in selectors:
                snapshot[selector] = root.locator(selector).evaluate('''el => {
                  const c=getComputedStyle(el),r=el.getBoundingClientRect();
                  return {x:r.x,y:r.y,width:r.width,height:r.height,font:c.font,
                    color:c.color,background:c.background,border:c.border,
                    shadow:c.boxShadow,lineHeight:c.lineHeight};
                }''')
            snapshots.append(snapshot)
            root.locator('#stage').screenshot(path=str(args.out / f'{name}-reference.png'))
            page.close()
        assert snapshots[0] == snapshots[1], {
            key:[snapshots[0][key], snapshots[1][key]] for key in selectors
            if snapshots[0][key] != snapshots[1][key]}
        before = np.asarray(Image.open(args.out / 'v1-reference.png').convert('RGB')).astype(int)
        after = np.asarray(Image.open(args.out / 'v2-reference.png').convert('RGB')).astype(int)
        difference = np.max(np.abs(before - after), axis=2)
        report['visual_comparison'] = {'identical_styles':selectors,
            'different_pixels_pct':round(float((difference > 0).mean() * 100), 5),
            'pixels_difference_above_10_pct':round(float((difference > 10).mean() * 100), 5)}
        assert float((difference > 10).mean()) < .01, report['visual_comparison']

        # The static shell must render even before the component JS executes.
        from bestbets_v2_preview import HTML, CSS
        page = browser.new_page(viewport={'width':1664, 'height':900})
        page.set_content('<style>body{margin:0}</style><div id="host"></div>')
        page.evaluate('''assets => {
          const shadow=document.querySelector('#host').attachShadow({mode:'open'});
          shadow.innerHTML='<style>'+assets.css+'</style>'+assets.html;
        }''', {'css':CSS, 'html':HTML})
        assert page.locator('#stage').is_visible()
        assert page.locator('#stage').bounding_box()['width'] > 1500
        page.screenshot(path=str(args.out / 'v2-without-component-js.png'))
        report['static_shell_without_component_js'] = True
        browser.close()
    (args.out / 'results.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(json.dumps({k:v if k != 'controlled_v1_feedback' else {'height_messages':len(v['heights'])}
                      for k,v in report.items()}, ensure_ascii=False))


if __name__ == '__main__':
    main()
