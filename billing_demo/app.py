"""Separate test-only account site. Public Streamlit entry point is untouched."""
from pathlib import Path
from datetime import datetime, timezone
import logging
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.concurrency import run_in_threadpool
from billing_backend.api import create_app as backend_app
from billing_backend.settings import Settings
from .config import DemoConfig
from .oidc import Auth0OIDC
from .sessions import Sessions

ROOT = Path(__file__).parent
log = logging.getLogger(__name__)


def create_app(settings=None, config=None, provider=None, oidc=None, db=None):
    settings, config = settings or Settings.from_env(), config or DemoConfig.from_env()
    settings.validate()
    config.validate(settings)
    oidc = oidc or Auth0OIDC(settings, config)
    api = backend_app(settings=settings, provider=provider, db=db, verifier=oidc.api)
    service = api.state.billing
    sessions = Sessions(service.db, config)
    app = FastAPI(title='BestBets account sandbox', docs_url=None, redoc_url=None, openapi_url=None)
    app.state.billing, app.state.sessions, app.state.oidc = service, sessions, oidc
    app.state.simulated = False
    # Injection is for the separate controlled-test runner, never request data.
    app.state.hosted_redirect = lambda url: url
    app.exception_handlers.update(api.exception_handlers)
    app.mount('/api', api)
    app.mount('/static', StaticFiles(directory=ROOT/'static'), name='static')
    templates = Jinja2Templates(directory=ROOT/'templates')

    @app.middleware('http')
    async def security(request, call_next):
        # No trust in forwarded host/proto; all links use configured origin.
        if request.url.netloc != config.origin.split('://', 1)[1]:
            return HTMLResponse('Invalid host', status_code=400)
        if not request.url.path.startswith('/api/'):
            body = bytearray()
            async for chunk in request.stream():
                body.extend(chunk)
                if len(body) > 16384:
                    return HTMLResponse('Request too large', status_code=413)
            request._body = bytes(body)
            request.state.session = await run_in_threadpool(sessions.get, request)
            if request.method == 'POST':
                if request.headers.get('content-type', '').split(';')[0] != 'application/x-www-form-urlencoded':
                    return HTMLResponse('Form required', status_code=415)
                form = await request.form(max_fields=10, max_files=0)
                try:
                    sessions.check_csrf(request, request.state.session, form)
                except HTTPException:
                    return HTMLResponse('Invalid session or CSRF', status_code=403)
                request.state.form = form
        response = await call_next(request)
        # no-referrer makes Chromium form Origin null. strict-origin keeps the
        # same-origin CSRF check working without leaking callback query strings.
        response.headers.update({'Cache-Control':'no-store', 'X-Content-Type-Options':'nosniff',
            'Referrer-Policy':'strict-origin', 'Content-Security-Policy':
            "default-src 'none'; style-src 'self'; img-src 'self'; form-action 'self' "
            + oidc.base + " https://checkout.stripe.com https://billing.stripe.com; base-uri 'none'; frame-ancestors 'none'"})
        if config.secure:
            response.headers['Strict-Transport-Security'] = 'max-age=31536000'
        return response

    def current(request):
        row = request.state.session
        if row is None or row.user_id is None:
            raise HTTPException(401, 'Login required')
        return row

    def form_fields(request, allowed):
        form = request.state.form
        if any(k not in allowed | {'csrf'} or len(form.getlist(k)) != 1 for k in form):
            raise HTTPException(400, 'Unexpected or repeated form field')
        return form

    def page(request, template, row, **values):
        return templates.TemplateResponse(request=request, name=template,
            context={'csrf':row.csrf, 'simulated':app.state.simulated,
                     'terms':settings.terms_version, **values})

    @app.get('/healthz')
    def health():
        return {'environment':'sandbox', 'simulated':app.state.simulated}

    @app.get('/')
    def home(request: Request):
        service.rate_limit('demo-home:'+(request.client.host if request.client else 'unknown'), 120, 60)
        row = request.state.session
        if row and row.user_id:
            return RedirectResponse('/account', status_code=303)
        token = None
        if row is None:
            token, row = sessions.create()
        response = page(request, 'login.html', row)
        if token:
            sessions.set_cookie(response, token, row)
        return response

    @app.post('/auth/{action}')
    def start(action: str, request: Request):
        if action not in ('login', 'register', 'recover'):
            raise HTTPException(404)
        form_fields(request, set())
        service.rate_limit('demo-login:'+(request.client.host if request.client else 'unknown'), 30, 600)
        row = request.state.session
        state, nonce, verifier = sessions.begin(row)
        return RedirectResponse(oidc.authorize(state, nonce, verifier,
            signup=action == 'register', recover=action == 'recover'), status_code=303)

    @app.get('/auth/callback')
    def callback(request: Request):
        service.rate_limit('demo-callback:'+(request.client.host if request.client else 'unknown'), 60, 600)
        params = request.query_params
        if any(len(params.getlist(k)) != 1 for k in params) or len(str(params)) > 8192:
            raise HTTPException(400, 'Invalid callback')
        row = request.state.session
        nonce, verifier = sessions.consume(row, params.get('state'))
        code = params.get('code')
        if params.get('error') or not code or len(code) > 4096:
            raise HTTPException(400, 'Login not completed; verify email or try again')
        try:
            identity, expires = oidc.identity(oidc.exchange(code, verifier), nonce)
        except Exception as exc:
            # Do not expose provider errors, codes, query strings or tokens.
            log.warning('OIDC callback rejected: %s', type(exc).__name__)
            raise HTTPException(401, 'Login verification failed; verify email or try again')
        account = service.account(identity)
        sessions.revoke(row)
        token, new_row = sessions.create(account.id, expires)
        response = RedirectResponse('/account', status_code=303)
        sessions.set_cookie(response, token, new_row)
        return response

    @app.get('/account')
    def account_page(request: Request):
        row = current(request)
        grant = service.entitlement(row.user_id)
        until = (datetime.fromtimestamp(grant['paid_until'], timezone.utc).strftime('%Y-%m-%d %H:%M UTC')
            if grant['paid_until'] else '—')
        return page(request, 'account.html', row, user_id=row.user_id,
            grant=grant, paid_until_label=until)

    @app.get('/sandbox-notice')
    def notice(request: Request):
        return templates.TemplateResponse(request=request, name='notice.html',
            context={'simulated':app.state.simulated, 'terms':settings.terms_version})

    @app.post('/account/refresh')
    def refresh(request: Request):
        form_fields(request, set())
        row = current(request)
        service.rate_limit('demo-refresh:'+row.user_id, 20, 600)
        service.entitlement(row.user_id, force=True)
        return RedirectResponse('/account', status_code=303)

    @app.post('/billing/checkout')
    def checkout(request: Request):
        row = current(request)
        form = form_fields(request, {'accept_terms', 'acknowledge_recurring', 'terms_version'})
        url = service.checkout(row.user_id, accept_terms=form.get('accept_terms') == 'yes',
            acknowledge_recurring=form.get('acknowledge_recurring') == 'yes',
            terms_version=form.get('terms_version'))
        return RedirectResponse(app.state.hosted_redirect(url), status_code=303)

    @app.post('/billing/portal')
    def portal(request: Request):
        form_fields(request, set())
        url = service.portal(current(request).user_id)
        return RedirectResponse(app.state.hosted_redirect(url), status_code=303)

    @app.get('/premium/demo')
    def premium(request: Request):
        row = current(request)
        service.require_premium(row.user_id)
        return page(request, 'premium.html', row)

    @app.post('/logout')
    def logout(request: Request):
        form_fields(request, set())
        sessions.revoke(request.state.session)
        response = RedirectResponse(oidc.logout(), status_code=303)
        response.delete_cookie(config.cookie_name, path='/', secure=config.secure,
            httponly=True, samesite='lax')
        return response

    return app
