import os
from pathlib import Path
from playwright.sync_api import expect
from .conftest import register


def screenshot(page, name):
    folder = os.getenv('DEMO_SCREENSHOT_DIR')
    if folder:
        Path(folder).mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(Path(folder)/(name+'.png')), full_page=True)


def test_registration_purchase_cancel_expire_logout_and_login(page, site):
    origin, app, provider = site
    register(page, origin)
    expect(page.get_by_test_id('plan')).to_have_text('Free')
    uid = page.get_by_test_id('user-id').inner_text()
    screenshot(page, '01-free')
    # The return URL and local browser flags have no authority.
    page.goto(origin+'/?checkout=success&premium=true')
    page.evaluate("localStorage.setItem('premium','true')")
    expect(page.get_by_test_id('plan')).to_have_text('Free')
    assert page.request.get(origin+'/premium/demo?premium=true&plan=Premium').status == 403
    page.get_by_label('Akceptuję testowe warunki', exact=False).check()
    page.get_by_label('Rozumiem testową cenę', exact=False).check()
    page.get_by_role('button', name='Przejdź do testowego Checkout').click()
    expect(page.get_by_role('heading', name='SYMULATOR: Checkout')).to_be_visible()
    screenshot(page, '02-simulated-checkout')
    page.get_by_role('button', name='Potwierdź symulowaną płatność').click()
    expect(page.get_by_test_id('plan')).to_have_text('Premium')
    assert page.get_by_test_id('user-id').inner_text() == uid
    screenshot(page, '03-premium')
    page.get_by_role('link', name='Sprawdź chronioną funkcję Premium').click()
    expect(page.get_by_test_id('premium-result')).to_be_visible()
    page.goto(origin+'/account')
    page.get_by_role('button', name='Zarządzaj subskrypcją').click()
    page.get_by_role('button', name='Anuluj na koniec okresu', exact=True).click()
    expect(page.get_by_test_id('cancellation')).to_have_text('Tak')
    expect(page.get_by_test_id('plan')).to_have_text('Premium')
    screenshot(page, '04-cancellation-pending')
    page.get_by_role('button', name='Zarządzaj subskrypcją').click()
    page.get_by_role('button', name='Symuluj koniec opłaconego okresu').click()
    expect(page.get_by_test_id('plan')).to_have_text('Free')
    assert page.request.get(origin+'/premium/demo').status == 403
    screenshot(page, '05-expired')
    cookie = page.context.cookies()[0]['value']
    page.get_by_role('button', name='Wyloguj się', exact=True).click()
    page.wait_for_url(origin+'/')
    assert page.request.get(origin+'/account').status == 401
    # A stolen old session cookie stays revoked after logout.
    assert page.request.get(origin+'/premium/demo', headers={'Cookie':'bestbets_demo_local='+cookie}).status == 401
    page.get_by_role('button', name='Zaloguj się', exact=True).click()
    page.locator('input[name=alias]').fill('alice')
    page.get_by_role('button', name='Zaloguj syntetyczne konto').click()
    expect(page.get_by_test_id('user-id')).to_have_text(uid)
    expect(page.get_by_test_id('plan')).to_have_text('Free')


def test_recovery_is_delegated_to_provider(page, site):
    origin, *_ = site
    page.goto(origin)
    page.get_by_role('button', name='Odzyskaj dostęp').click()
    page.get_by_role('link', name='Forgot password?').click()
    expect(page.get_by_test_id('recovery')).to_be_visible()


def test_free_request_tampering_csrf_and_cookie_fixation(page, site):
    origin, app, *_ = site
    page.goto(origin)
    anonymous = page.context.cookies()[0]['value']
    register(page, origin, 'free-user')
    cookie = page.context.cookies()[0]
    assert cookie['value'] != anonymous
    assert cookie['httpOnly'] and cookie['sameSite'] == 'Lax'
    csrf = page.locator('input[name=csrf]').first.input_value()
    data = {'csrf':csrf, 'accept_terms':'yes', 'acknowledge_recurring':'yes',
        'terms_version':'sandbox-draft-v1'}
    for extra in ({'user_id':'victim'}, {'customer_id':'cus_victim'}, {'premium':'true'},
                  {'price_id':'price_Cheap'}, {'subscription_id':'sub_victim'}):
        r = page.request.post(origin+'/billing/checkout', form={**data, **extra}, headers={'Origin':origin})
        assert r.status == 400
    assert page.request.post(origin+'/billing/checkout', form=data).status == 403
    assert page.request.post(origin+'/billing/checkout', form=data, headers={'Origin':'https://evil.invalid'}).status == 403
    assert page.request.post(origin+'/billing/portal', form={'csrf':'wrong'}, headers={'Origin':origin}).status == 403
    assert page.request.get(origin+'/api/v1/premium/check/player_props').status == 401
    assert page.request.get(origin+'/premium/demo', headers={'Cookie':'bestbets_demo_local='+anonymous}).status == 401
    assert page.request.get(origin+'/premium/demo?user_id=victim&premium=true').status == 403
    assert page.request.post(origin+'/api/webhooks/stripe', data='{}',
        headers={'Stripe-Signature':'t=0,v1=bad'}).status == 400
    expect(page.get_by_test_id('plan')).to_have_text('Free')
    html = page.content()
    for secret in ('access_token', 'id_token', 'client_secret', 'sk_test_', 'whsec_'):
        assert secret not in html


def test_callback_wrong_state_cross_browser_replay_and_session_expiry(page, browser, site):
    from urllib.parse import parse_qs, urlparse
    from sqlalchemy import update
    from billing_demo.models import WebSession
    origin, app, *_ = site
    page.goto(origin)
    assert page.request.get(origin+'/auth/callback?state=wrong&code=evil').status == 400
    page.get_by_role('button', name='Załóż konto', exact=True).click()
    state = parse_qs(urlparse(page.url).query)['state'][0]
    other = browser.new_context()
    assert other.request.get(origin+'/auth/callback?state='+state+'&code=attacker').status == 400
    other.close()
    page.locator('input[name=alias]').fill('replay-user')
    callbacks = []
    page.on('request', lambda request: callbacks.append(request.url)
        if '/auth/callback?' in request.url else None)
    page.get_by_role('button', name='Utwórz syntetyczne konto').click()
    page.wait_for_url(origin+'/account')
    assert len(callbacks) == 1
    expect(page.get_by_test_id('plan')).to_have_text('Free')
    assert page.request.get(callbacks[0]).status == 400
    with app.state.billing.db.transaction() as s:
        s.execute(update(WebSession).values(expires_at=0))
    assert page.request.get(origin+'/premium/demo').status == 401
    assert page.request.get(origin+'/account').status == 401


def test_mobile_and_security_headers(page, site):
    origin, *_ = site
    page.set_viewport_size({'width':390, 'height':844})
    register(page, origin, 'mobile-user')
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    expect(page.get_by_test_id('plan')).to_be_visible()
    response = page.request.get(origin+'/account')
    assert response.headers['cache-control'] == 'no-store'
    assert response.headers['referrer-policy'] == 'strict-origin'
    assert "frame-ancestors 'none'" in response.headers['content-security-policy']
    assert page.request.get(origin+'/', headers={'Host':'evil.invalid'}).status == 400
    screenshot(page, '06-mobile')


def test_free_cannot_impersonate_another_premium_account(page, browser, site):
    origin, *_ = site
    register(page, origin, 'premium-owner')
    owner = page.get_by_test_id('user-id').inner_text()
    page.get_by_label('Akceptuję testowe warunki', exact=False).check()
    page.get_by_label('Rozumiem testową cenę', exact=False).check()
    page.get_by_role('button', name='Przejdź do testowego Checkout').click()
    page.get_by_role('button', name='Potwierdź symulowaną płatność').click()
    expect(page.get_by_test_id('plan')).to_have_text('Premium')
    context = browser.new_context()
    free = context.new_page()
    try:
        register(free, origin, 'free-attacker')
        assert free.get_by_test_id('user-id').inner_text() != owner
        for query in ('?user_id='+owner, '?sub='+owner+'&premium=true', '?plan=Premium'):
            assert free.request.get(origin+'/premium/demo'+query).status == 403
        csrf = free.locator('input[name=csrf]').first.input_value()
        assert free.request.post(origin+'/billing/portal', form={'csrf':csrf,'user_id':owner},
            headers={'Origin':origin}).status == 400
        expect(free.get_by_test_id('plan')).to_have_text('Free')
    finally:
        context.close()
