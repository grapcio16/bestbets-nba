"""Explicit BFF configuration; no automatic simulator or live mode."""
from dataclasses import dataclass, field
import os
from urllib.parse import urlparse
from cryptography.fernet import Fernet


@dataclass(frozen=True)
class DemoConfig:
    client_id: str
    client_secret: str = field(repr=False)
    encryption_key: str = field(repr=False)
    origin: str
    allow_local_http: bool = False

    def validate(self, settings):
        p = urlparse(self.origin)
        if (p.scheme != 'https' and not (self.allow_local_http and p.scheme == 'http'
                and p.hostname in ('localhost', '127.0.0.1'))):
            raise ValueError('Demo requires HTTPS, or explicit loopback HTTP development mode')
        if p.path or p.query or p.fragment or p.username or p.password or not p.hostname:
            raise ValueError('DEMO_ORIGIN must be an exact origin without a trailing slash')
        if self.origin != settings.billing.app_url.rstrip('/'):
            raise ValueError('Demo and billing must use the same origin')
        if not self.client_id or not self.client_secret:
            raise ValueError('OIDC confidential client configuration required')
        Fernet(self.encryption_key.encode())

    @property
    def secure(self):
        return self.origin.startswith('https://')

    @property
    def cookie_name(self):
        return '__Host-bestbets_demo' if self.secure else 'bestbets_demo_local'

    @classmethod
    def from_env(cls):
        return cls(os.environ['OIDC_CLIENT_ID'], os.environ['OIDC_CLIENT_SECRET'],
            os.environ['DEMO_STATE_ENCRYPTION_KEY'], os.environ['DEMO_ORIGIN'],
            os.getenv('DEMO_ALLOW_LOCAL_HTTP') == 'true')
