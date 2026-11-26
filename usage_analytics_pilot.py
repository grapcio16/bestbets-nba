"""Opt-in admin-only telemetry pilot; no changes to customer access or UI."""
import os
import hmac
import hashlib
import time
from uuid import uuid4
from contextlib import contextmanager

PAGES=frozenset(("home","props","games","simulations","players","teams","settings"))
FEATURES=frozenset(("simulation","player_simulation","scenario","minutes","props","backtest"))

def enabled():
    from access_control import current_role
    return (os.environ.get("HOOPZARO_USAGE_ENABLED","").lower()=="true"
            and os.environ.get("HOOPZARO_USAGE_ADMIN_PILOT","").lower()=="true"
            and bool(os.environ.get("HOOPZARO_USAGE_DATABASE_URL","").strip())
            and current_role()=="admin")

@contextmanager
def cursor(url):
    import psycopg
    with psycopg.connect(url,connect_timeout=2) as conn,conn.cursor() as cur:
        cur.execute("SET LOCAL statement_timeout = '1500ms'")
        cur.execute("SET LOCAL lock_timeout = '700ms'")
        yield cur

def observe(state,page):
    if not enabled() or not isinstance(page,str) or page not in PAGES:
        return
    now=time.monotonic()
    last=state.get("hz_usage_last")
    if last is not None and now-last<30:
        return
    state["hz_usage_last"]=now
    sid=state.setdefault("hz_usage_session",str(uuid4()))
    seconds=min(90,max(0,int(now-last))) if last is not None else 0
    try:
        with cursor(os.environ["HOOPZARO_USAGE_DATABASE_URL"]) as cur:
            cur.execute("""INSERT INTO hz_usage_sessions(session_id,role) VALUES (%s,'admin')
                ON CONFLICT(session_id) DO UPDATE SET last_seen=now(),
                observed_seconds=hz_usage_sessions.observed_seconds+%s""",(sid,seconds))
            cur.execute("""INSERT INTO hz_usage_daily(day,session_id,page)
                VALUES ((now() AT TIME ZONE 'UTC')::date,%s,%s)
                ON CONFLICT(day,session_id,page) DO UPDATE SET samples=hz_usage_daily.samples+1""",(sid,page))
    except Exception:
        pass

def observe_account(state,principal):
    if not enabled() or os.environ.get("HOOPZARO_ACCOUNT_REGISTRY_ENABLED","").lower()!="true":
        return
    secret=os.environ.get("HOOPZARO_ACCOUNT_HMAC_KEY","").encode()
    url=os.environ.get("HOOPZARO_ACCOUNT_DATABASE_URL","").strip()
    if len(secret)<32 or not url or not isinstance(principal,str) or not principal or principal=="guest":
        return
    now=time.monotonic()
    last=state.get("hz_account_last")
    if last is not None and now-last<1800:
        return
    state["hz_account_last"]=now
    account=hmac.new(secret,principal.encode(),hashlib.sha256).hexdigest()
    try:
        with cursor(url) as cur:
            cur.execute("""INSERT INTO hoopzaro_accounts(account_id,last_observed_role)
                VALUES (%s,'admin') ON CONFLICT(account_id) DO UPDATE SET
                last_seen_at=now(),last_observed_role='admin'""",(account,))
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
