"""Explicit Sandbox-only configuration. Secret values are never represented."""
from dataclasses import dataclass, field
import os
from urllib.parse import urlparse
from sqlalchemy.engine import make_url
from stripe_test_billing import TestBillingConfig


def validate_database_url(url, allow_sqlite=False):
    if url.startswith('postgresql+psycopg://'):
        database = make_url(url)
        if database.host not in (None, 'localhost', '127.0.0.1', '::1') and database.query.get('sslmode') != 'verify-full':
            raise ValueError('Remote PostgreSQL requires sslmode=verify-full')
    elif not (allow_sqlite and url.startswith('sqlite:///')):
        raise ValueError('Use PostgreSQL; SQLite requires explicit local-test opt-in')


@dataclass(frozen=True)
class Settings:
    billing: TestBillingConfig = field(repr=False)
    database_url: str = field(repr=False)
    oidc_issuer: str
    oidc_audience: str
    oidc_jwks_url: str
    stripe_account_id: str
    product_id: str
    portal_configuration_id: str
    terms_version: str = 'sandbox-draft-v1'
    freshness_seconds: int = 60
    allow_sqlite: bool = False
    email_verified_claim: str = 'email_verified'

    def validate(self):
        self.billing.validate()
        for url in (self.oidc_issuer, self.oidc_jwks_url):
            p = urlparse(url)
            if p.scheme != 'https' or not p.hostname or p.username or p.password or p.fragment or p.query:
                raise ValueError('OIDC issuer and static JWKS URL must use HTTPS')
        if not self.oidc_audience or not self.stripe_account_id.startswith('acct_'):
            raise ValueError('API audience and test Stripe account are required')
        if not self.product_id.startswith('prod_') or not self.portal_configuration_id.startswith('bpc_'):
            raise ValueError('Expected Product and sandbox Portal configuration are required')
        if not 1 <= self.freshness_seconds <= 60:
            raise ValueError('Entitlement freshness must not exceed 60 seconds')
        validate_database_url(self.database_url, self.allow_sqlite)

    @classmethod
    def from_env(cls):
        value = cls(
            billing=TestBillingConfig.from_env(), database_url=os.environ['BILLING_DATABASE_URL'],
            oidc_issuer=os.environ['OIDC_ISSUER'], oidc_audience=os.environ['OIDC_API_AUDIENCE'],
            oidc_jwks_url=os.environ['OIDC_JWKS_URL'], stripe_account_id=os.environ['STRIPE_TEST_ACCOUNT_ID'],
            product_id=os.environ['STRIPE_TEST_PRODUCT_ID'],
            portal_configuration_id=os.environ['STRIPE_TEST_PORTAL_CONFIGURATION_ID'],
            terms_version=os.getenv('BILLING_TERMS_VERSION', 'sandbox-draft-v1'),
            allow_sqlite=os.getenv('BILLING_ALLOW_SQLITE_TEST') == 'true',
            email_verified_claim=os.getenv('OIDC_EMAIL_VERIFIED_CLAIM','email_verified'),
        )
        value.validate()
        return value
