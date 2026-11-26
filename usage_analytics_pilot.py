"""Opt-in telemetry; admin pilot or explicit session consent. No entitlements."""
import os
import hmac
import hashlib
import time
from uuid import uuid4
from contextlib import contextmanager

PAGES=frozenset(("home","props","games","simulations","players","teams","settings"))
FEATURES=frozenset(("simulation","player_simulation","scenario","minutes","props","backtest"))

CONSENT_VERSION="2026-11-26-v1"
ROLES=frozenset(("admin","free","premium","guest"))

def _flag(name):
    return os.environ.get(name,"").strip().lower()=="true"

def audience_available():
    return (_flag("HOOPZARO_USAGE_ENABLED") and _flag("HOOPZARO_USAGE_CUSTOMER_ENABLED")
            and bool(os.environ.get("HOOPZARO_USAGE_DATABASE_URL","").strip()))

def enabled():
    from access_control import current_role
    if not _flag("HOOPZARO_USAGE_ENABLED") or not os.environ.get("HOOPZARO_USAGE_DATABASE_URL","").strip():
        return False
    role=current_role()
    if role=="admin" and _flag("HOOPZARO_USAGE_ADMIN_PILOT"):
        return True
    if role not in ROLES or not audience_available():
        return False
    import streamlit as st
    return st.session_state.get("hz_usage_consent")==CONSENT_VERSION

def set_consent(state, accepted):
    # Optional, per-session consent; never use a client-supplied role or identifier.
    if type(accepted) is not bool:
        return False
    if accepted and not audience_available():
        return False
    if accepted == (state.get("hz_usage_consent")==CONSENT_VERSION):
        return False
    if accepted:
        state["hz_usage_consent"]=CONSENT_VERSION
    else:
        state.pop("hz_usage_consent",None)
    for key in ("hz_usage_session","hz_usage_last","hz_account_last","hz_usage_role","hz_account_role","hz_usage_pending"):
        state.pop(key,None)
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
            ms=min(600000,max(0,int((time.monotonic()-start)*1000)))
            with cursor(os.environ["HOOPZARO_USAGE_DATABASE_URL"]) as cur:
                cur.execute("""INSERT INTO hz_feature_daily(day,feature,outcome,total_ms)
                    VALUES ((now() AT TIME ZONE 'UTC')::date,%s,%s,%s)
                    ON CONFLICT(day,feature,outcome) DO UPDATE SET
                    calls=hz_feature_daily.calls+1,total_ms=hz_feature_daily.total_ms+EXCLUDED.total_ms""",(feature,outcome,ms))
        except Exception:
            pass
