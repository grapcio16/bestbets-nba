"""Durable sessions; atomic, single-use, cookie-bound login transactions."""
import hashlib
import hmac
import json
import secrets
import time
from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import delete
from fastapi import HTTPException
from billing_backend.db import Account
from .models import WebSession, LoginFlow


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


class Sessions:
    def __init__(self, db, config):
        self.db, self.config = db, config
        self.cipher = Fernet(config.encryption_key.encode())

    def create(self, user_id=None, expires=None):
        token = secrets.token_urlsafe(32)
        row = WebSession(id=digest(token), user_id=user_id, csrf=secrets.token_urlsafe(32),
            expires_at=expires or int(time.time())+900)
        with self.db.transaction() as s:
            s.add(row)
        return token, row

    def get(self, request):
        raw = request.cookies.get(self.config.cookie_name, '')
        if not 20 <= len(raw) <= 128:
            return None
        with self.db.transaction() as s:
            row = s.get(WebSession, digest(raw))
            if row is None or row.expires_at <= time.time():
                return None
            if row.user_id:
                account = s.get(Account, row.user_id)
                if account is None or account.disabled:
                    return None
            return row

    def revoke(self, row):
        with self.db.transaction() as s:
            s.execute(delete(WebSession).where(WebSession.id == row.id))

    def set_cookie(self, response, token, row):
        response.set_cookie(self.config.cookie_name, token,
            max_age=max(0, row.expires_at-int(time.time())), httponly=True,
            secure=self.config.secure, samesite='lax', path='/')

    def check_csrf(self, request, row, form):
        values = form.getlist('csrf')
        if (row is None or request.headers.get('origin') != self.config.origin
                or len(values) != 1 or not hmac.compare_digest(values[0], row.csrf)):
            raise HTTPException(403, 'Invalid session or CSRF')

    def begin(self, row):
        state, nonce, verifier = (secrets.token_urlsafe(32) for _ in range(3))
        with self.db.transaction() as s:
            # Bound storage and invalidate older attempts from the same browser.
            s.execute(delete(LoginFlow).where(LoginFlow.session_id == row.id))
            s.execute(delete(LoginFlow).where(LoginFlow.expires_at < int(time.time())))
            s.execute(delete(WebSession).where(WebSession.expires_at < int(time.time())))
            s.add(LoginFlow(id=digest(state), session_id=row.id, expires_at=int(time.time())+300,
                encrypted=self.cipher.encrypt(json.dumps([nonce,verifier]).encode()).decode()))
        return state, nonce, verifier

    def consume(self, row, state):
        if not isinstance(state, str) or not 20 <= len(state) <= 128 or row is None:
            raise HTTPException(400, 'Invalid login transaction')
        with self.db.transaction() as s:
            flow = s.get(LoginFlow, digest(state), with_for_update=True)
            if flow is None or flow.session_id != row.id or flow.expires_at <= time.time():
                raise HTTPException(400, 'Invalid login transaction')
            encrypted = flow.encrypted
            s.delete(flow)
        try:
            return json.loads(self.cipher.decrypt(encrypted.encode(), ttl=300))
        except (InvalidToken, ValueError, TypeError):
            raise HTTPException(400, 'Expired or invalid login transaction')
