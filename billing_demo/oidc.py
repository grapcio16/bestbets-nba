"""Auth0 authorization-code + S256 PKCE. Tokens never reach browser storage."""
import base64
import hashlib
import hmac
import time
from urllib.parse import urlencode
import jwt
from authlib.integrations.httpx_client import OAuth2Client
from billing_backend.auth import OIDCVerifier, Identity, AuthenticationFailed


class Auth0OIDC:
    def __init__(self, settings, config, key_resolver=None):
        self.settings, self.config = settings, config
        self.api = OIDCVerifier(settings, key_resolver)
        self.key = self.api.key_resolver
        self.base = settings.oidc_issuer.rstrip('/')

    def authorize(self, state, nonce, verifier, signup=False):
        # Static configured issuer, never a URL/redirect supplied by a browser.
        with OAuth2Client(self.config.client_id, self.config.client_secret,
                code_challenge_method='S256', redirect_uri=self.config.origin+'/auth/callback',
                scope='openid email bestbets:api') as client:
            url, _ = client.create_authorization_url(self.base+'/authorize', state=state,
                nonce=nonce, code_verifier=verifier, audience=self.settings.oidc_audience,
                screen_hint='signup' if signup else 'login')
            return url

    def exchange(self, code, verifier):
        # No refresh/offline tokens; short sessions re-enter Universal Login SSO.
        with OAuth2Client(self.config.client_id, self.config.client_secret,
                token_endpoint_auth_method='client_secret_post', timeout=10,
                follow_redirects=False) as client:
            return client.fetch_token(self.base+'/oauth/token', code=code,
                redirect_uri=self.config.origin+'/auth/callback', code_verifier=verifier)

    def identity(self, tokens, nonce):
        try:
            access, raw = tokens['access_token'], tokens['id_token']
            if tokens.get('token_type', '').lower() != 'bearer' or len(raw) > 8192:
                raise ValueError()
            header = jwt.get_unverified_header(raw)
            if (header.get('alg') != 'RS256' or header.get('typ') != 'JWT'
                    or not isinstance(header.get('kid'), str) or not 1 <= len(header['kid']) <= 256
                    or 'jku' in header or 'x5u' in header):
                raise ValueError()
            claims = jwt.decode(raw, self.key(raw), algorithms=['RS256'],
                issuer=self.settings.oidc_issuer, audience=self.config.client_id, leeway=15,
                options={'require':['iss','sub','aud','iat','exp','nonce']})
            if not hmac.compare_digest(str(claims['nonce']), nonce):
                raise ValueError()
            if (claims.get('email_verified') is not True or claims['iat'] > time.time()+15
                    or claims['exp']-claims['iat'] > 3600):
                raise ValueError()
            aud = claims['aud']
            if (isinstance(aud, list) and len(aud) > 1 and claims.get('azp') != self.config.client_id
                    or 'azp' in claims and claims['azp'] != self.config.client_id):
                raise ValueError()
            if 'at_hash' in claims:
                digest = hashlib.sha256(access.encode('ascii')).digest()[:16]
                expected = base64.urlsafe_b64encode(digest).rstrip(b'=').decode()
                if not hmac.compare_digest(claims['at_hash'], expected):
                    raise ValueError()
            identity = self.api.verify(access)
            if identity != Identity(claims['iss'], claims['sub']):
                raise ValueError()
            # Decode only AFTER signature/policy validation; never trust client exp.
            exp = jwt.decode(access, options={'verify_signature':False})['exp']
            return identity, min(int(exp), int(claims['exp']), int(time.time())+900)
        except (jwt.PyJWTError, KeyError, ValueError, TypeError, OSError) as exc:
            raise AuthenticationFailed('Login verification failed') from exc

    def logout(self):
        # Without token hints Auth0 may show its logout confirmation. The local
        # session is already revoked even if the user declines that confirmation.
        return self.base+'/oidc/logout?'+urlencode({'client_id':self.config.client_id,
            'post_logout_redirect_uri':self.config.origin+'/'})
