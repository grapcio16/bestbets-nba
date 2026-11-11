"""Loopback-only provider emulator. Not an Auth0/Stripe acceptance test.

Run with --controlled-demo. Never uses secrets from the environment. The real
app factory has no simulator switch, fake login route or request-driven override.
"""
import argparse
import base64
import hashlib
import hmac
import html
import json
import secrets
import threading
import time
from dataclasses import replace
from urllib.parse import urlencode, urlparse
from uuid import uuid4
import httpx
import jwt
import uvicorn
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from sqlalchemy.engine import make_url
from stripe_test_billing import TestBillingConfig
from billing_backend.settings import Settings
from billing_backend.db import Database, Base
from billing_backend.stripe_provider import StripeProvider
from billing_demo.app import create_app
from billing_demo.config import DemoConfig
from billing_demo.oidc import Auth0OIDC
from .stripe_world import World


class LocalOIDC(Auth0OIDC):
    def __init__(self, settings, config, key, provider_origin):
        super().__init__(settings, config, lambda _:key.public_key())
        # Claims keep a synthetic HTTPS issuer; only this explicit test adapter
        # uses a loopback transport. Production HTTPS validation stays intact.
        self.base = provider_origin


def build(database_url, port=8810, provider_port=8811):
    url = make_url(database_url)
    if url.drivername == 'postgresql+psycopg':
        if url.host not in ('127.0.0.1', 'localhost') or not url.database.endswith('_demo_test'):
            raise ValueError('Controlled demo requires a loopback *_demo_test PostgreSQL database')
    elif url.drivername != 'sqlite' or not str(url.database).startswith('/tmp/bestbets-demo-'):
        raise ValueError('Controlled demo requires an isolated /tmp/bestbets-demo-* SQLite file')
    origin, remote = f'http://localhost:{port}', f'http://localhost:{provider_port}'
    settings = Settings(billing=TestBillingConfig(
        secret_key='sk_test_SYNTHETIC_BROWSER_NOT_A_KEY', price_id='price_DemoMonthly',
        webhook_secret='whsec_SYNTHETIC_BROWSER_NOT_A_SECRET', app_url=origin),
        database_url=database_url, oidc_issuer='https://auth0.demo.invalid/',
        oidc_audience='https://bestbets.demo.invalid/api', oidc_jwks_url='https://auth0.demo.invalid/jwks',
        stripe_account_id='acct_Demo', product_id='prod_Demo', portal_configuration_id='bpc_Demo',
        allow_sqlite=url.drivername == 'sqlite',
        email_verified_claim='https://bestbets-nba.streamlit.app/claims/email_verified')
    config = DemoConfig('demo-client', 'SYNTHETIC_NOT_A_SECRET', Fernet.generate_key().decode(), origin, True)
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    db = Database(database_url)
    Base.metadata.create_all(db.engine)  # only this restricted, synthetic fixture runner
    world = World(settings)
    provider = StripeProvider(settings, client=world.client)
    oidc = LocalOIDC(settings, config, key, remote)
    app = create_app(settings, config, provider, oidc, db)
    service = app.state.billing
    service.clock = lambda:world.now
    app.state.simulated = True
    hosted = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    interactions, codes, users, portals = {}, {}, {}, {}

    def page(title, body):
        return HTMLResponse('<!doctype html><html lang="pl"><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<title>SYMULATOR — '+title+'</title><body><h1>SYMULATOR: '+title+'</h1>'
            '<p>Brak połączenia z Auth0/Stripe. Nie wpisuj prawdziwych danych ani haseł.</p>'+body+'</body></html>')

    @hosted.middleware('http')
    async def loopback(request, call_next):
        if request.client.host not in ('127.0.0.1', '::1', 'testclient') or request.url.netloc != f'localhost:{provider_port}':
            return HTMLResponse('Loopback only', status_code=403)
        response = await call_next(request)
        response.headers.update({'Cache-Control':'no-store', 'Referrer-Policy':'no-referrer',
            'Content-Security-Policy':"default-src 'none'; form-action 'self' "+origin+"; frame-ancestors 'none'; base-uri 'none'"})
        return response

    @hosted.get('/authorize')
    def authorize(request: Request):
        q = dict(request.query_params)
        if (q.get('client_id') != config.client_id or q.get('response_type') != 'code'
                or q.get('redirect_uri') != origin+'/auth/callback'
                or q.get('code_challenge_method') != 'S256'):
            raise HTTPException(400)
        ticket = secrets.token_urlsafe(32)
        interactions[ticket] = q
        label = 'Utwórz syntetyczne konto' if q.get('screen_hint') == 'signup' else 'Zaloguj syntetyczne konto'
        return page('Dostawca OIDC', '<form method="post" action="/authorize">'
            f'<input type="hidden" name="ticket" value="{ticket}">'
            '<label>Alias testowy <input name="alias" required></label>'
            f'<button>{label}</button></form><a href="/recover">Forgot password?</a>')

    @hosted.post('/authorize')
    async def authorize_submit(request: Request):
        f = await request.form()
        q = interactions.pop(f.get('ticket'), None)
        alias = str(f.get('alias', ''))
        if q is None or not 1 <= len(alias) <= 80:
            raise HTTPException(400)
        if q.get('screen_hint') == 'signup':
            # Registration here simulates an already verified IdP identity. Real
            # Auth0 requires the user's email verification link before login.
            users.setdefault(alias, 'auth0|synthetic-'+uuid4().hex)
        if alias not in users:
            raise HTTPException(401, 'Create a synthetic account first')
        code = secrets.token_urlsafe(32)
        codes[code] = (q, users[alias], int(time.time())+60)
        return RedirectResponse(q['redirect_uri']+'?'+urlencode({'state':q['state'], 'code':code}), 303)

    @hosted.post('/oauth/token')
    async def token(request: Request):
        f = await request.form()
        stored = codes.pop(f.get('code'), None)
        if stored is None:
            return JSONResponse({'error':'invalid_grant'}, 400)
        q, sub, expires = stored
        challenge = base64.urlsafe_b64encode(hashlib.sha256(str(f.get('code_verifier')).encode()).digest()).rstrip(b'=').decode()
        if (expires <= time.time() or not hmac.compare_digest(challenge, q['code_challenge'])
                or f.get('client_id') != config.client_id or f.get('client_secret') != config.client_secret
                or f.get('redirect_uri') != origin+'/auth/callback' or f.get('grant_type') != 'authorization_code'):
            return JSONResponse({'error':'invalid_grant'}, 400)
        now = int(time.time())
        claims = dict(iss=settings.oidc_issuer, sub=sub, iat=now, exp=now+900)
        access = jwt.encode({**claims, settings.email_verified_claim:True,
            'aud':settings.oidc_audience, 'scope':'openid email bestbets:api'}, key,
            algorithm='RS256', headers={'kid':'demo-key', 'typ':'at+jwt'})
        raw = jwt.encode({**claims, 'email_verified':True, 'aud':config.client_id, 'nonce':q['nonce']}, key,
            algorithm='RS256', headers={'kid':'demo-key', 'typ':'JWT'})
        return {'access_token':access, 'id_token':raw, 'token_type':'Bearer', 'expires_in':900}

    @hosted.get('/recover')
    def recover():
        return page('Odzyskiwanie dostępu', '<p data-testid="recovery">Symulowane odzyskiwanie dostępu u dostawcy. Żaden e-mail nie został wysłany.</p><a href="'+origin+'/">Wróć</a>')

    @hosted.get('/oidc/logout')
    def logout(request: Request):
        if request.query_params.get('post_logout_redirect_uri') != origin+'/':
            raise HTTPException(400)
        return RedirectResponse(origin+'/', 303)

    def redirect(url):
        p = urlparse(url)
        if p.hostname == 'checkout.stripe.com':
            return remote+'/checkout/'+p.path.rsplit('/', 1)[-1]
        if p.hostname == 'billing.stripe.com':
            return remote+'/portal/'+p.path.rsplit('/', 1)[-1]
        raise ValueError('Unexpected simulated hosted URL')
    app.state.hosted_redirect = redirect

    def portal_create(params):
        ticket = secrets.token_urlsafe(32)
        portals[ticket] = params['customer']
        return {'url':'https://billing.stripe.com/p/session/'+ticket}
    world.client.v1.billing_portal.sessions.create.side_effect = portal_create

    def emit(sub, kind):
        raw = json.dumps({'id':'evt_'+uuid4().hex, 'type':kind, 'livemode':False,
            'data':{'object':sub}}, separators=(',', ':')).encode()
        stamp = str(int(time.time()))
        sig = hmac.new(settings.billing.webhook_secret.encode(), stamp.encode()+b'.'+raw, hashlib.sha256).hexdigest()
        # Actual HTTP and official Stripe signature verification, not direct grant.
        result = httpx.post(origin+'/api/webhooks/stripe', content=raw,
            headers={'Stripe-Signature':f't={stamp},v1={sig}'}, timeout=10, trust_env=False)
        result.raise_for_status()

    @hosted.get('/checkout/{ticket}')
    def checkout(ticket: str):
        if ticket not in world.sessions:
            raise HTTPException(404)
        return page('Checkout', '<p>Premium 10 USD/miesiąc — symulacja.</p>'
            f'<form method="post" action="/checkout/{html.escape(ticket)}"><button>Potwierdź symulowaną płatność</button></form>')

    @hosted.post('/checkout/{ticket}')
    def purchase(ticket: str):
        session = world.sessions.get(ticket)
        if session is None or session['status'] != 'open':
            raise HTTPException(409)
        sub, *_ = world.paid(service, session['metadata']['internal_user_id'])
        session['status'] = 'complete'
        emit(sub, 'customer.subscription.created')
        return RedirectResponse(origin+'/?checkout=success', 303)

    @hosted.get('/portal/{ticket}')
    def portal(ticket: str):
        if ticket not in portals:
            raise HTTPException(404)
        return page('Customer Portal', f'<form method="post" action="/portal/{ticket}/cancel"><button>Anuluj na koniec okresu</button></form>'
            f'<form method="post" action="/portal/{ticket}/expire"><button>Symuluj koniec opłaconego okresu</button></form><a href="{origin}/account">Wróć do konta</a>')

    @hosted.post('/portal/{ticket}/{action}')
    def cancel(ticket: str, action: str):
        customer = portals.get(ticket)
        subs = [s for s in world.subscriptions.values() if s['customer'] == customer]
        if not customer or not subs or action not in ('cancel', 'expire'):
            raise HTTPException(400)
        sub = subs[-1]
        sub['cancel_at_period_end'] = True
        kind = 'customer.subscription.updated'
        if action == 'expire':
            sub['status'] = 'canceled'
            world.now = sub['current_period_end']+1
            kind = 'customer.subscription.deleted'
        emit(sub, kind)
        return RedirectResponse(origin+'/account', 303)

    return app, hosted


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--controlled-demo', action='store_true', required=True)
    parser.add_argument('--database-url', required=True)
    parser.add_argument('--port', type=int, default=8810)
    parser.add_argument('--provider-port', type=int, default=8811)
    args = parser.parse_args()
    app, hosted = build(args.database_url, args.port, args.provider_port)
    server = uvicorn.Server(uvicorn.Config(hosted, host='127.0.0.1', port=args.provider_port,
        access_log=False, proxy_headers=False))
    threading.Thread(target=server.run, daemon=True).start()
    uvicorn.run(app, host='127.0.0.1', port=args.port, access_log=False, proxy_headers=False)


if __name__ == '__main__':
    main()
