"""Minimal durable consent receipts. No credentials or direct identity stored in SQL."""
from dataclasses import dataclass
from urllib.parse import urlsplit
from uuid import uuid4
import os
import hmac
import hashlib
import time

NOTICE_VERSION="2026-11-26-v2"
PURPOSE="optional_usage_analytics"
MAX_SESSION_SECONDS=86400
END_REASONS=frozenset(("withdrawn","identity_changed","expired","disabled","logout"))

@dataclass(frozen=True)
class Grant:
    session_id: str
    account_receipt_id: str | None
    account_id: str | None
    role: str
    principal: str  # ephemeral server state only; never inserted into SQL
    notice_version: str
    deadline: float

def notice_url():
    if os.environ.get("HOOPZARO_USAGE_CONSENT_READY","").strip().lower()!="true":
        return ""
    if os.environ.get("HOOPZARO_USAGE_NOTICE_VERSION","").strip()!=NOTICE_VERSION:
        return ""
    raw=os.environ.get("HOOPZARO_USAGE_NOTICE_URL","").strip()
    try:
        u=urlsplit(raw)
        if (len(raw)>512 or u.scheme!="https" or u.netloc not in ("hoopzaro.com","www.hoopzaro.com")
                or not u.path.startswith("/privacy") or u.query or u.fragment):
            return ""
    except ValueError:
        return ""
    return raw

def account_identifier(principal):
    if os.environ.get("HOOPZARO_ACCOUNT_REGISTRY_ENABLED","").strip().lower()!="true":
        return None
    key=os.environ.get("HOOPZARO_ACCOUNT_HMAC_KEY","").encode()
    url=os.environ.get("HOOPZARO_ACCOUNT_DATABASE_URL","").strip()
    if len(key)<32 or not url or not isinstance(principal,str) or not principal or principal=="guest":
        return None
    return hmac.new(key,principal.encode(),hashlib.sha256).hexdigest()

def create_receipt(cursor, url, role, principal):
    """Both independent receipts commit together before granting consent."""
    policy=notice_url()
    if not policy or role not in ("guest","free","premium"):
        raise ValueError("Consent unavailable")
    if not isinstance(principal,str) or not principal or (role=="guest")!=(principal=="guest"):
        raise ValueError("Invalid identity")
    account=account_identifier(principal) if role!="guest" else None
    session_id=str(uuid4())
    account_receipt=str(uuid4()) if account else None
    deadline=time.monotonic()+MAX_SESSION_SECONDS
    with cursor(url) as cur:
        cur.execute("""INSERT INTO public.hz_session_consent(receipt_id,notice_version,notice_url,purpose,role)
            VALUES (%s,%s,%s,%s,%s)""",(session_id,NOTICE_VERSION,policy,PURPOSE,role))
        if account:
            cur.execute("""INSERT INTO public.hz_account_consent(receipt_id,account_id,notice_version,notice_url,purpose)
                VALUES (%s,%s,%s,%s,%s)""",(account_receipt,account,NOTICE_VERSION,policy,PURPOSE))
    return Grant(session_id,account_receipt,account,role,principal,NOTICE_VERSION,deadline)

def close_receipt(cursor,url,session_id,account_receipt_id,reason):
    if reason not in END_REASONS:
        raise ValueError("Invalid end reason")
    with cursor(url) as cur:
        cur.execute("""UPDATE public.hz_session_consent SET ended_at=now(),end_reason=%s
            WHERE receipt_id=%s AND ended_at IS NULL""",(reason,session_id))
        if account_receipt_id:
            cur.execute("""UPDATE public.hz_account_consent SET ended_at=now(),end_reason=%s
                WHERE receipt_id=%s AND ended_at IS NULL""",(reason,account_receipt_id))
