"""Settings v2: browser-only fixture, no external auth or billing actions."""
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).parent
URL = (ROOT / "bestbets_reference_frontend/index.html").as_uri()
OUT = ROOT / "test-results/settings-account-v2"
OUT.mkdir(parents=True, exist_ok=True)
KEYS = ("profile","plan","preferences","notifications","privacy","security","support")

def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        for width,height in ((1672,941),(1231,691),(390,844),(844,390)):
            page = browser.new_page(viewport={"width":width,"height":height})
            errors = []
            page.on("pageerror", lambda exc: errors.append(str(exc)))
            page.add_init_script("""window.qaEvents=[];window.addEventListener('message',e=>{
                if(e.data?.type==='streamlit:setComponentValue')window.qaEvents.push(e.data.value);
            });""")
            page.goto(URL, wait_until="load")
            def push(role,epoch,consent=False):
                data={"auth":{"role":role,"logged_in":role!="guest","configured":True,
                              "name":"QA Example" if role!="guest" else "",
                              "email":"qa@example.invalid" if role!="guest" else "",
                              "provider":"google" if role!="guest" else "",
                              "session_epoch":epoch},
                      "usage_consent_available":consent,
                      "usage_consent_granted":False,
                      "usage_consent_status":"off",
                      "usage_notice_url":"https://hoopzaro.com/privacy",
                      "usage_notice_version":"qa-notice"}
                page.evaluate("d=>window.postMessage({type:'streamlit:render',args:{payload:d}},'*')",data)
                page.wait_for_function("r=>document.querySelector('#hz-account-role').textContent===r",
                    arg={"guest":"GOŚĆ","free":"KONTO FREE","premium":"PREMIUM","admin":"ADMINISTRATOR · PREMIUM"}[role]) if page.locator("#hz-account").is_visible() else None
            push("free",1,True)
            if width<768 or height<=500:
                page.locator("#hz-mobile-more-trigger").click()
                page.locator('#hz-mobile-more-panel [data-page="settings"]').click()
            else:
                page.locator('.nav-btn[data-page="settings"]').click()
            page.wait_for_function("()=>document.querySelector('#hz-account-role').textContent==='KONTO FREE'")
            assert page.locator(".hza-tile").count()==7
            assert page.locator(".hza-page-head").is_visible()
            assert page.locator(".hza-preview-row").count()==14
            assert page.locator(".hza-ball-art").is_visible()
            assert page.locator("#hza-hero-ball-gradient").count()==1
            assert page.locator("#hza-ball-gradient").count()==1
            assert page.locator("#hz-admin-nav").is_hidden()
            assert page.locator("#hz-mobile-admin").is_hidden()
            assert "ADMINISTRATOR" not in page.locator("#hz-account").inner_text()
            page.screenshot(path=str(OUT/f"free-{width}.png"),full_page=True,animations="disabled")
            for key in KEYS:
                tile=page.locator(f'.hza-tile[data-hza-open="{key}"]')
                tile.click()
                dialog=page.locator("#hza-dialog")
                assert dialog.is_visible()
                panel=dialog.locator(f'[data-hza-panel="{key}"]')
                assert panel.is_visible()
                assert dialog.locator("[data-hza-panel]:visible").count()==1
                if key=="profile":
                    assert page.locator("#hza-profile-email").inner_text()=="qa@example.invalid"
                if key=="notifications":
                    assert panel.locator("input,button").count()==0
                if key=="privacy":
                    assert page.locator("#hz-usage-allow").is_enabled()
                if key=="security":
                    assert page.locator("#hza-google-security").is_visible()
                assert dialog.get_attribute("data-panel")==key
                assert dialog.locator(".hza-dialog-body").evaluate("e=>e.scrollTop===0"), key
                assert page.locator("#hza-dialog-icon svg").count()==1
                assert panel.locator(".hza-feature-card, .hza-plan-banner, .hza-notification-list").count()>0
                assert dialog.evaluate("e=>e.getBoundingClientRect().width<=innerWidth")
                assert dialog.evaluate("e=>e.scrollWidth<=e.clientWidth+2"), key
                assert dialog.locator("#hza-done").is_visible()
                assert dialog.locator("#hza-done").evaluate("e=>{const r=e.getBoundingClientRect(); return r.top>=0 && r.bottom<=innerHeight+1}"), key
                assert dialog.locator(".hza-dialog-body").evaluate("e=>e.clientHeight>60"), key
                assert dialog.locator(".hza-dialog-body").evaluate("e=>e.scrollWidth<=e.clientWidth+2"), key
                assert dialog.locator(".hza-dialog-body").evaluate("e=>e.getBoundingClientRect().bottom<=e.parentElement.getBoundingClientRect().bottom+2"), key
                if width==1672:
                    assert dialog.bounding_box()["width"]>=1100
                    assert dialog.bounding_box()["height"]>=500
                if key in ("notifications","privacy"):
                    assert dialog.locator(".hza-dialog-nav").is_hidden()
                else:
                    assert dialog.locator(".hza-dialog-nav").is_visible()
                page.screenshot(path=str(OUT/f"{key}-{width}.png"),animations="disabled")
                if key in ("preferences","privacy"):
                    dialog.locator(".hza-dialog-body").evaluate("e=>{e.scrollTop=e.scrollHeight}")
                    page.screenshot(path=str(OUT/f"{key}-bottom-{width}.png"),animations="disabled")
                    assert dialog.locator("#hza-done").evaluate("e=>{const r=e.getBoundingClientRect();return r.bottom<=innerHeight+1}"), key
                page.keyboard.press("Escape")
                assert dialog.is_hidden()
            page.locator('.hza-tile[data-hza-open="preferences"]').click()
            page.locator("#hza-pref-period").select_option("L5")
            page.locator("#hza-pref-venue").select_option("HOME")
            assert "Zastosowano" in page.locator("#hza-pref-status").inner_text()
            page.keyboard.press("Escape")
            if width<768 or height<=500:
                page.locator('#hz-mobile-nav [data-page="props"]').click()
            else:
                page.locator('.nav-btn[data-page="props"]').click()
            assert "Last 5 Games (Home)" in page.locator("#chart-heading").inner_text()
            if width<768 or height<=500:
                page.locator("#hz-mobile-more-trigger").click()
                page.locator('#hz-mobile-more-panel [data-page="settings"]').click()
            else:
                page.locator('.nav-btn[data-page="settings"]').click()
            page.locator('.hza-tile[data-hza-open="preferences"]').click()
            assert page.locator("#hza-pref-period").input_value()=="L5"
            assert page.locator("#hza-pref-venue").input_value()=="HOME"
            page.locator(".hza-dialog-body").evaluate("e=>e.scrollTop=e.scrollHeight")
            page.locator('.hza-dialog-nav [data-hza-open="security"]').click()
            assert page.locator(".hza-dialog-body").evaluate("e=>e.scrollTop===0")
            page.keyboard.press("Escape")
            page.locator('.hza-tile[data-hza-open="privacy"]').click()
            page.locator("#hz-usage-allow").click()
            page.wait_for_function("()=>qaEvents.some(e=>e.type==='usage_consent'&&e.accepted===true&&e.consent_epoch===1)")
            page.keyboard.press("Escape")
            page.locator('.hza-tile[data-hza-open="profile"]').click()
            push("guest",2)
            assert page.locator("#hza-dialog").is_hidden()
            assert page.locator("#hza-profile-email").inner_text()=="—"
            assert page.locator("#hza-pref-period").input_value()=="L10"
            assert page.locator("#hza-pref-venue").input_value()=="ALL"
            assert page.locator("#hz-account-login").is_visible()
            assert page.locator("#hz-account-logout").is_hidden()
            push("premium",3)
            assert page.locator("#hz-admin-nav").is_hidden()
            page.locator('.hza-tile[data-hza-open="plan"]').click()
            assert "ADMINISTRATOR" not in page.locator("#hza-dialog").inner_text()
            page.screenshot(path=str(OUT/f"premium-plan-{width}.png"),animations="disabled")
            page.keyboard.press("Escape")
            assert "ADMINISTRATOR" not in page.locator("#hz-account").inner_text()
            push("admin",4)
            assert "ADMINISTRATOR" in page.locator("#hz-account").inner_text()
            assert page.locator("#hz-account-role .hza-premium-word").inner_text()=="PREMIUM"
            assert page.locator("#hz-account-role .hza-premium-word").evaluate("e=>getComputedStyle(e).color")=="rgb(255, 220, 128)"
            page.screenshot(path=str(OUT/f"admin-{width}.png"),full_page=True,animations="disabled")
            push("free",5)
            assert page.locator("#hz-admin-nav").is_hidden()
            assert "ADMINISTRATOR" not in page.locator("#hz-account").inner_text()
            assert not errors, errors
            page.close()
        browser.close()
    print("Settings v2: seven panels, role isolation, consent, identity change and responsive layout OK")

if __name__=="__main__":
    run()
