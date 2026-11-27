"""Opt-in telemetry; admin pilot or explicit session consent. No entitlements."""
import os
import hmac
import hashlib
import time
from uuid import uuid4
from contextlib import contextmanager

PAGES=frozenset(("home","props","games","simulations","players","teams","settings"))
FEATURES=frozenset(("simulation","player_simulation","scenario","minutes","props","backtest"))

from usage_consent_receipts import NOTICE_VERSION as CONSENT_VERSION, Grant, notice_url, create_receipt, close_receipt

ROLES=frozenset(("admin","free","premium","guest"))

def _flag(name):
    return os.environ.get(name,"").strip().lower()=="true"

def audience_available():
    return (_flag("HOOPZARO_USAGE_ENABLED") and _flag("HOOPZARO_USAGE_CUSTOMER_ENABLED")
            and bool(os.environ.get("HOOPZARO_USAGE_DATABASE_URL","").strip())
            and bool(notice_url()))

def _valid_grant(state, role, principal):
    grant=state.get("hz_consent_grant")
    return (isinstance(grant,Grant) and grant.notice_version==CONSENT_VERSION and grant.notice_url==notice_url()
            and grant.role==role and grant.principal==principal
            and time.monotonic()<grant.deadline)

def enabled():
    from access_control import current_role, current_principal
    if not _flag("HOOPZARO_USAGE_ENABLED") or not os.environ.get("HOOPZARO_USAGE_DATABASE_URL","").strip():
        return False
    role=current_role()
    if role=="admin" and _flag("HOOPZARO_USAGE_ADMIN_PILOT"):
        return True
    if role not in ("guest","free","premium") or not audience_available():
        return False
    import streamlit as st
    return _valid_grant(st.session_state,role,current_principal())

def _clear_collection(state):
    for key in ("hz_usage_consent","hz_usage_session","hz_usage_last","hz_account_last","hz_usage_role","hz_account_role","hz_usage_pending"):
        state.pop(key,None)

def retry_close(state):
    pending=state.get("hz_consent_pending_close")
    if not pending:
        return True
    now=time.monotonic()
    if now<state.get("hz_consent_retry_after",0):
        return False
    try:
        close_receipt(cursor,os.environ["HOOPZARO_USAGE_DATABASE_URL"],*pending)
        state.pop("hz_consent_pending_close",None)
        state.pop("hz_consent_retry_after",None)
        state["hz_consent_status"]="off"
        return True
    except Exception:
        state["hz_consent_retry_after"]=now+30
        state["hz_consent_status"]="withdrawal_pending"
        return False

def end_consent(state,reason):
    # Stop collection before attempting any I/O, including DB failure.
    grant=state.pop("hz_consent_grant",None)
    _clear_collection(state)
    if isinstance(grant,Grant):
        state["hz_consent_pending_close"]=(grant.session_id,grant.account_receipt_id,reason)
        state.pop("hz_consent_retry_after",None)
    state["hz_consent_status"]="off"
    if not retry_close(state):
        state["hz_consent_status"]="withdrawal_pending"
    return True

def refresh_consent(state,principal,role):
    retry_close(state)
    grant=state.get("hz_consent_grant")
    if not isinstance(grant,Grant):
        return
    if grant.principal!=principal or grant.role!=role:
        end_consent(state,"identity_changed")
    elif time.monotonic()>=grant.deadline:
        end_consent(state,"expired")
    elif not audience_available() or grant.notice_url!=notice_url() or grant.notice_version!=CONSENT_VERSION:
        end_consent(state,"disabled")

def set_consent(state, accepted, principal=None):
    from access_control import current_role, current_principal
    if type(accepted) is not bool:
        return False
    role=current_role()
    principal=current_principal() if principal is None else principal
    if not accepted:
        return end_consent(state,"withdrawn")
    refresh_consent(state,principal,role)
    if _valid_grant(state,role,principal):
        return False
    if not audience_available() or state.get("hz_consent_pending_close") or role not in ("guest","free","premium"):
        state["hz_consent_status"]="unavailable" if not state.get("hz_consent_pending_close") else "withdrawal_pending"
        return True
    try:
        grant=create_receipt(cursor,os.environ["HOOPZARO_USAGE_DATABASE_URL"],role,principal)
    except Exception:
        _clear_collection(state)
        state["hz_consent_status"]="unavailable"
        return True
    _clear_collection(state)
    state["hz_consent_grant"]=grant
    state["hz_usage_session"]=grant.session_id
    state["hz_usage_role"]=role
    state["hz_consent_status"]="on"
    return True

@contextmanager
def cursor(url):
    import psycopg
    with psycopg.connect(url,connect_timeout=2) as conn,conn.cursor() as cur:
        cur.execute("SET LOCAL statement_timeout = '1500ms'")
        cur.execute("SET LOCAL lock_timeout = '700ms'")
        yield cur

def observe(state,page,visited=None):
    if not enabled():
        return
    pages={page} if isinstance(page,str) and page in PAGES else set()
    if isinstance(visited,list):
        pages.update(p for p in visited[:len(PAGES)] if isinstance(p,str) and p in PAGES)
    if not pages:
        return
    from access_control import current_role
    role=current_role()
    if role not in ROLES:
        return
    now=time.monotonic()
    if state.get("hz_usage_role")!=role:
        state.pop("hz_usage_session",None)
        state.pop("hz_usage_last",None)
        state.pop("hz_usage_pending",None)
        state["hz_usage_role"]=role
    pending=state.setdefault("hz_usage_pending",set())
    pending.update(pages)
    last=state.get("hz_usage_last")
    if last is not None and now-last<30:
        return
    state["hz_usage_last"]=now
    sid=state.setdefault("hz_usage_session",str(uuid4()))
    seconds=min(90,max(0,int(now-last))) if last is not None and 0<=now-last<=120 else 0
    try:
        with cursor(os.environ["HOOPZARO_USAGE_DATABASE_URL"]) as cur:
            cur.execute("""INSERT INTO hz_usage_sessions(session_id,role) VALUES (%s,%s)
                ON CONFLICT(session_id) DO UPDATE SET last_seen=now(),
                observed_seconds=hz_usage_sessions.observed_seconds+%s""",(sid,role,seconds))
            cur.execute("""INSERT INTO hz_usage_daily(day,session_id,page)
                SELECT (now() AT TIME ZONE 'UTC')::date,%s,unnest(%s::text[])
                ON CONFLICT(day,session_id,page) DO UPDATE SET samples=hz_usage_daily.samples+1""",(sid,sorted(pending)))
        pending.clear()
    except Exception:
        pass

def observe_account(state,principal):
    if not enabled() or os.environ.get("HOOPZARO_ACCOUNT_REGISTRY_ENABLED","").lower()!="true":
        return
    from access_control import current_role
    role=current_role()
    if role not in ("admin","free","premium"):
        return
    secret=os.environ.get("HOOPZARO_ACCOUNT_HMAC_KEY","").encode()
    url=os.environ.get("HOOPZARO_ACCOUNT_DATABASE_URL","").strip()
    if len(secret)<32 or not url or not isinstance(principal,str) or not principal or principal=="guest":
        return
    now=time.monotonic()
    last=state.get("hz_account_last") if state.get("hz_account_role")==role else None
    if last is not None and now-last<1800:
        return
    state["hz_account_last"]=now
    state["hz_account_role"]=role
    account=hmac.new(secret,principal.encode(),hashlib.sha256).hexdigest()
    if role!="admin":
        grant=state.get("hz_consent_grant")
        if not isinstance(grant,Grant) or grant.account_id!=account or not grant.account_receipt_id:
            return
    try:
        with cursor(url) as cur:
            cur.execute("""INSERT INTO hoopzaro_accounts(account_id,last_observed_role)
                VALUES (%s,%s) ON CONFLICT(account_id) DO UPDATE SET
                last_seen_at=now(),last_observed_role=EXCLUDED.last_observed_role""",(account,role))
    except Exception:
        pass

def measured(feature,fn,*args,**kwargs):
    if feature not in FEATURES or not enabled():
        return fn(*args,**kwargs)
    start=time.monotonic()
    outcome="failure"
    try:
        result=fn(*args,**kwargs)
        if result is not None and not (isinstance(result,dict) and (result.get("error") or result.get("status") in ("unavailable","connection_issue","error","denied"))):
            outcome="success"
        return result
    finally:
        try:
            if not enabled():
                # Do not persist telemetry after the grant expires during a long call.
                raise RuntimeError("Telemetry disabled")
            ms=min(600000,max(0,int((time.monotonic()-start)*1000)))
            with cursor(os.environ["HOOPZARO_USAGE_DATABASE_URL"]) as cur:
                cur.execute("""INSERT INTO hz_feature_daily(day,feature,outcome,total_ms)
                    VALUES ((now() AT TIME ZONE 'UTC')::date,%s,%s,%s)
                    ON CONFLICT(day,feature,outcome) DO UPDATE SET
                    calls=hz_feature_daily.calls+1,total_ms=hz_feature_daily.total_ms+EXCLUDED.total_ms""",(feature,outcome,ms))
        except Exception:
            pass
