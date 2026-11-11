"""Only external Stripe/OIDC transport is replaced; SQL and signatures are real."""
import os
import time
from types import SimpleNamespace
import pytest
import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from stripe_test_billing import TestBillingConfig as BillingConfig
from billing_backend.settings import Settings
from billing_backend.db import Database, Base
from billing_demo import models  # include migrated session FKs in isolated DB resets
from billing_backend.auth import OIDCVerifier, Identity
from billing_backend.api import create_app
from billing_backend.stripe_provider import StripeProvider


from billing_demo.testing.stripe_world import World


@pytest.fixture(scope='session')
def signing_key():
    return rsa.generate_private_key(public_exponent=65537,key_size=2048)


@pytest.fixture
def env(tmp_path, signing_key):
    url = os.getenv('TEST_BILLING_DATABASE_URL') or 'sqlite:///'+str(tmp_path/'billing.sqlite3')
    if not url.startswith('sqlite:///') and not url.endswith('/bestbets_billing_test'):
        raise RuntimeError('Tests require the isolated bestbets_billing_test database')
    settings = Settings(billing=BillingConfig(secret_key='sk_test_SYNTHETIC_UNIT_FIXTURE_NOT_A_KEY',
        price_id='price_TestMonthly',webhook_secret='whsec_SYNTHETIC_UNIT_FIXTURE_NOT_A_SECRET',
        app_url='https://sandbox.example.invalid'),database_url=url,
        oidc_issuer='https://identity.example.invalid/',oidc_audience='https://api.example.invalid',
        oidc_jwks_url='https://identity.example.invalid/jwks',stripe_account_id='acct_TestOnly',
        product_id='prod_TestOnly',portal_configuration_id='bpc_TestOnly',allow_sqlite=url.startswith('sqlite'))
    db = Database(url)
    Base.metadata.drop_all(db.engine)
    Base.metadata.create_all(db.engine)
    world = World(settings)
    provider = StripeProvider(settings,client=world.client)
    verifier = OIDCVerifier(settings,key_resolver=lambda _:signing_key.public_key())
    app = create_app(settings,provider,verifier,db)
    service = app.state.billing
    service.clock = lambda:world.now
    def token(subject='user-one', **changes):
        now = int(time.time())
        claims = dict(iss=settings.oidc_issuer,aud=settings.oidc_audience,sub=subject,
            iat=now,exp=now+600,email_verified=True,scope='bestbets:api')
        claims.update(changes)
        return jwt.encode(claims,signing_key,algorithm='RS256',headers={'kid':'test-key','typ':'at+jwt'})
    result = SimpleNamespace(settings=settings,db=db,world=world,provider=provider,service=service,
        verifier=verifier,client=TestClient(app),token=token,
        user=service.account(Identity(settings.oidc_issuer,'user-one')))
    yield result
    result.client.close()
    db.engine.dispose()
