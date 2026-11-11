"""Access-token verification only; registration/passwords remain with the IdP."""
from dataclasses import dataclass
import time
import jwt


class AuthenticationFailed(ValueError):
    pass


@dataclass(frozen=True)
class Identity:
    issuer: str
    subject: str


class OIDCVerifier:
    def __init__(self, settings, key_resolver=None):
        self.settings = settings
        # Static, operator-configured URL. Never use token jku/x5u or discovery
        # endpoints supplied by the caller. JWKS network calls are bounded.
        self.jwks = jwt.PyJWKClient(settings.oidc_jwks_url, lifespan=300, timeout=5)
        self.key_resolver = key_resolver or (lambda token: self.jwks.get_signing_key_from_jwt(token).key)

    def verify(self, token):
        try:
            if not isinstance(token, str) or len(token) > 8192:
                raise ValueError()
            header = jwt.get_unverified_header(token)
            if header.get('alg') != 'RS256' or header.get('typ') not in ('JWT', 'at+jwt'):
                raise ValueError()
            kid = header.get('kid')
            if not isinstance(kid, str) or not 1 <= len(kid) <= 256 or 'jku' in header or 'x5u' in header:
                raise ValueError()
            claims = jwt.decode(token, self.key_resolver(token), algorithms=['RS256'],
                issuer=self.settings.oidc_issuer, audience=self.settings.oidc_audience, leeway=15,
                options={'require':['iss','sub','aud','exp','iat']})
            sub = claims['sub']
            now = time.time()
            if not isinstance(sub, str) or not 1 <= len(sub) <= 255 or any(ord(c) < 32 for c in sub):
                raise ValueError()
            if claims.get(self.settings.email_verified_claim) is not True or 'bestbets:api' not in str(claims.get('scope', '')).split():
                raise ValueError()
            if claims['exp'] - claims['iat'] > 3600 or claims['iat'] > now + 15:
                raise ValueError()
            return Identity(claims['iss'], sub)
        except (jwt.PyJWTError, ValueError, TypeError, KeyError, OSError) as exc:
            raise AuthenticationFailed('Invalid API access token') from exc
