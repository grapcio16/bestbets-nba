"""Real signatures and database sessions, not browser flags or token stubs."""
from dataclasses import replace
import base64
import hashlib
import time
from urllib.parse import parse_qs, urlparse
import jwt
import pytest
from cryptography.fernet import Fernet
from fastapi import HTTPException
from billing_backend.auth import AuthenticationFailed
from billing_backend.tests.conftest import env, signing_key
from billing_demo.config import DemoConfig
from billing_demo.oidc import Auth0OIDC
from billing_demo.sessions import Sessions, digest
from billing_demo.models import LoginFlow, WebSession


def config(env):
    return DemoConfig('regular-web-client', 'SYNTHETIC_SECRET', Fernet.generate_key().decode(),
        env.settings.billing.app_url)


def tokens(env, key, id_changes=None, access_changes=None):
    now = int(time.time())
    access = env.token(**(access_changes or {}))
    claims = dict(iss=env.settings.oidc_issuer, sub='user-one', aud='regular-web-client',
        iat=now, exp=now+600, email_verified=True, nonce='correct-nonce')
    claims.update(id_changes or {})
    raw = jwt.encode(claims, key, algorithm='RS256', headers={'kid':'test-key'})
    return {'access_token':access, 'id_token':raw, 'token_type':'Bearer'}


def test_access_and_id_tokens_agree_before_session_creation(env, signing_key):
    adapter = Auth0OIDC(env.settings, config(env), lambda _:signing_key.public_key())
    identity, expiry = adapter.identity(tokens(env, signing_key), 'correct-nonce')
    assert identity.subject == 'user-one'
    assert time.time() < expiry <= time.time()+900


@pytest.mark.parametrize('id_changes,access_changes', [
    ({'nonce':'attacker'}, {}), ({'aud':'different-client'}, {}),
    ({'iss':'https://evil.invalid/'}, {}), ({'exp':0}, {}),
    ({'iat':int(time.time())+300}, {}), ({'email_verified':False}, {}),
    ({'sub':'other-user'}, {}), ({'azp':'other-client'}, {}),
    ({'aud':['regular-web-client','other']}, {}), ({'at_hash':'incorrect'}, {}),
    ({}, {'aud':'regular-web-client'}), ({}, {'email_verified':False}),
    ({}, {'scope':'openid email'}), ({}, {'exp':0}),
])
def test_rejects_nonce_id_token_confusion_and_unverified_users(env, signing_key, id_changes, access_changes):
    adapter = Auth0OIDC(env.settings, config(env), lambda _:signing_key.public_key())
    with pytest.raises(AuthenticationFailed):
        adapter.identity(tokens(env, signing_key, id_changes, access_changes), 'correct-nonce')


def test_rejects_invalid_signature_and_checks_at_hash(env, signing_key):
    from cryptography.hazmat.primitives.asymmetric import rsa
    adapter = Auth0OIDC(env.settings, config(env), lambda _:signing_key.public_key())
    other = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    with pytest.raises(AuthenticationFailed):
        adapter.identity(tokens(env, other), 'correct-nonce')
    bundle = tokens(env, signing_key)
    expected = base64.urlsafe_b64encode(hashlib.sha256(bundle['access_token'].encode()).digest()[:16]).rstrip(b'=').decode()
    bundle = tokens(env, signing_key, {'at_hash':expected})
    assert adapter.identity(bundle, 'correct-nonce')[0].subject == 'user-one'


def test_pkce_authorize_and_logout_have_only_configured_destinations(env, signing_key):
    adapter = Auth0OIDC(env.settings, config(env), lambda _:signing_key.public_key())
    url = adapter.authorize('state', 'nonce', 'verifier', signup=True)
    q = parse_qs(urlparse(url).query)
    assert q['code_challenge_method'] == ['S256']
    assert q['screen_hint'] == ['signup']
    assert q['prompt'] == ['login']
    recovery = parse_qs(urlparse(adapter.authorize('state', 'nonce', 'verifier', recover=True)).query)
    assert recovery['prompt'] == ['login'] and recovery['screen_hint'] == ['login']
    assert q['redirect_uri'] == [env.settings.billing.app_url+'/auth/callback']
    assert q['response_type'] == ['code']
    assert set(q['scope'][0].split()) == {'openid','email','bestbets:api'}
    assert 'client_secret' not in q and 'code_verifier' not in q
    assert parse_qs(urlparse(adapter.logout()).query)['post_logout_redirect_uri'] == [env.settings.billing.app_url+'/']


def test_db_contains_only_hashes_and_encrypted_login_proofs(env):
    store = Sessions(env.db, config(env))
    raw, row = store.create()
    state, nonce, verifier = store.begin(row)
    with env.db.transaction() as s:
        stored = s.get(WebSession, row.id)
        assert stored.id == digest(raw) and raw not in stored.id
        flow = s.get(LoginFlow, digest(state))
        assert nonce not in flow.encrypted and verifier not in flow.encrypted
    assert store.consume(row, state) == [nonce, verifier]
    with pytest.raises(HTTPException):
        store.consume(row, state)


def test_key_rotation_rejects_inflight_login_and_does_not_replay(env):
    cfg = config(env)
    store = Sessions(env.db, cfg)
    _, row = store.create()
    state, *_ = store.begin(row)
    rotated = Sessions(env.db, replace(cfg, encryption_key=Fernet.generate_key().decode()))
    with pytest.raises(HTTPException) as caught:
        rotated.consume(row, state)
    assert caught.value.status_code == 400
    with pytest.raises(HTTPException):
        store.consume(row, state)


@pytest.mark.parametrize('origin,local', [('http://evil.invalid',True),
    ('http://localhost:8810',False), ('https://demo.invalid/path',False),
    ('https://demo.invalid?x=y',False), ('https://user@demo.invalid',False)])
def test_configuration_refuses_unsafe_demo_origins(env, origin, local):
    value = replace(config(env), origin=origin, allow_local_http=local)
    with pytest.raises(ValueError):
        value.validate(env.settings)


def test_https_session_cookie_and_no_simulator_routes(env, signing_key):
    from fastapi.testclient import TestClient
    from billing_demo.app import create_app
    cfg = config(env)
    adapter = Auth0OIDC(env.settings, cfg, lambda _:signing_key.public_key())
    app = create_app(env.settings, cfg, env.provider, adapter, env.db)
    with TestClient(app, base_url=cfg.origin) as client:
        response = client.get('/')
        cookie = response.headers['set-cookie']
        assert '__Host-bestbets_demo=' in cookie and 'Secure' in cookie and 'HttpOnly' in cookie
        assert 'Domain=' not in cookie and 'Path=/' in cookie
        for path in ('/authorize','/oauth/token','/checkout/fake','/portal/fake/expire'):
            assert client.get(path).status_code == 404
        assert client.get('/healthz').json()['simulated'] is False
