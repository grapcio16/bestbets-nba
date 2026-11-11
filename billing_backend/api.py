"""Sandbox API factory. No routes or code are imported by app.py."""
import logging
from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, StrictBool, field_validator
from sqlalchemy.exc import SQLAlchemyError
import stripe
from stripe_test_billing import BillingNotConfigured
from .settings import Settings
from .db import Database
from .auth import OIDCVerifier, AuthenticationFailed
from .service import BillingService, AccessDenied, Conflict, RateLimited
from .stripe_provider import StripeProvider, ProviderUnavailable
from .policy import FREE_FEATURES, PREMIUM_FEATURES

log = logging.getLogger(__name__)


class CheckoutConsent(BaseModel):
    model_config = ConfigDict(extra='forbid')
    accept_terms: StrictBool
    acknowledge_recurring: StrictBool
    terms_version: str

    @field_validator('accept_terms', 'acknowledge_recurring')
    @classmethod
    def affirmative(cls, value):
        if value is not True:
            raise ValueError('Explicit acceptance required')
        return value


class EmptyRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')


def create_app(settings=None, provider=None, verifier=None, db=None):
    settings = settings or Settings.from_env()
    settings.validate()
    db = db or Database(settings.database_url)
    service = BillingService(db, provider or StripeProvider(settings), settings)
    verifier = verifier or OIDCVerifier(settings)
    app = FastAPI(title='BestBets Billing Sandbox', docs_url=None, redoc_url=None, openapi_url=None)
    app.state.billing = service
    app.add_middleware(CORSMiddleware, allow_origins=[settings.billing.app_url.rstrip('/')],
        allow_credentials=False, allow_methods=['GET','POST'],
        allow_headers=['Authorization','Content-Type'])

    @app.middleware('http')
    async def security(request, call_next):
        origin = request.headers.get('origin')
        if request.url.path.startswith('/v1/') and origin and origin != settings.billing.app_url.rstrip('/'):
            return JSONResponse({'error':'origin_not_allowed'}, status_code=403)
        # Bound actual streamed bytes, not just a caller-controlled length.
        limit = 1024*1024 if request.url.path == '/webhooks/stripe' else 16384
        body = bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body) > limit:
                return JSONResponse({'error':'body_too_large'}, status_code=413)
        request._body = bytes(body)
        request.state.raw_body = bytes(body)
        response = await call_next(request)
        response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Content-Security-Policy'] = "default-src 'none'; frame-ancestors 'none'"
        return response

    @app.exception_handler(AccessDenied)
    async def denied(_, exc):
        return JSONResponse({'error':'premium_or_account_required'}, status_code=403)

    @app.exception_handler(Conflict)
    async def conflict(_, exc):
        return JSONResponse({'error':'billing_state_conflict'}, status_code=409)

    @app.exception_handler(RateLimited)
    async def rate_limited(_, exc):
        return JSONResponse({'error':'rate_limited'}, status_code=429, headers={'Retry-After':str(exc.retry_after)})

    async def unavailable(_, exc):
        # Never reflect Stripe exception strings, headers or request bodies.
        log.warning('Billing dependency unavailable: %s', type(exc).__name__)
        return JSONResponse({'error':'verification_unavailable'}, status_code=503)
    for exc in (ProviderUnavailable, stripe.StripeError, SQLAlchemyError, BillingNotConfigured):
        app.add_exception_handler(exc, unavailable)

    def account(request: Request):
        # Ignore X-Forwarded-For unless a separately reviewed trusted proxy
        # configuration is installed. DB-backed limits work across workers.
        service.rate_limit('auth:'+(request.client.host if request.client else 'unknown'), 120, 60)
        values = request.headers.getlist('authorization')
        scheme, _, token = (values[0] if len(values) == 1 else '').partition(' ')
        if scheme.lower() != 'bearer' or not token:
            raise HTTPException(401, detail='API access token required', headers={'WWW-Authenticate':'Bearer'})
        try:
            identity = verifier.verify(token)
        except AuthenticationFailed:
            raise HTTPException(401, detail='Invalid API access token', headers={'WWW-Authenticate':'Bearer'})
        return service.account(identity)

    @app.get('/healthz')
    def health():
        return {'service':'BestBets billing', 'environment':'sandbox'}

    @app.get('/v1/me')
    def me(user=Depends(account)):
        return {'user_id':user.id, **service.entitlement(user.id)}

    @app.post('/v1/billing/checkout')
    def checkout(consent: CheckoutConsent, user=Depends(account)):
        if consent.terms_version != settings.terms_version:
            raise HTTPException(409, detail='Current subscription notice must be accepted')
        return {'url':service.checkout(user.id, accept_terms=consent.accept_terms,
            acknowledge_recurring=consent.acknowledge_recurring, terms_version=consent.terms_version)}

    @app.post('/v1/billing/portal')
    def portal(body: EmptyRequest, user=Depends(account)):
        return {'url':service.portal(user.id)}

    @app.get('/v1/features/{feature}')
    def feature_policy(feature: str):
        if feature not in FREE_FEATURES | PREMIUM_FEATURES:
            raise HTTPException(404)
        return {'feature':feature,'requires_premium':feature in PREMIUM_FEATURES}

    @app.get('/v1/premium/check/{feature}')
    def premium_check(feature: str, user=Depends(account)):
        if feature not in PREMIUM_FEATURES:
            raise HTTPException(404)
        service.require_premium(user.id)
        return {'authorized':True,'feature':feature}

    @app.post('/webhooks/stripe')
    def webhook(request: Request):
        # Raw bytes cached by the bounded middleware; sync handler executes
        # DB/Stripe work in FastAPI's thread pool, not the async event loop.
        signatures = request.headers.getlist('stripe-signature')
        if len(signatures) != 1:
            raise HTTPException(400, detail='One Stripe-Signature header required')
        try:
            outcome = service.webhook(request.state.raw_body, signatures[0])
        except (ValueError, stripe.SignatureVerificationError, BillingNotConfigured):
            raise HTTPException(400, detail='Invalid signed Sandbox event')
        return {'received':True,'outcome':outcome}

    return app
