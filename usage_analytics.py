"""Opt-in application analytics. No raw identifiers, search text, IP or user agent."""
import os
import time
from uuid import uuid4
from contextlib import contextmanager

PAGES = frozenset(("home","props","games","simulations","players","teams","settings"))
FEATURES = frozenset(("simulation","player_simulation","scenario","minutes","props","backtest"))
ROLES = frozenset(("guest","free","premium","admin"))

def enabled():
    return os.environ.get("HOOPZARO_USAGE_ENABLED","").lower()=="true" and bool(os.environ.get("HOOPZARO_USAGE_DATABASE_URL","").strip())

def _connect():
    import psycopg
    return psycopg.connect(os.environ["HOOPZARO_USAGE_DATABASE_URL"],connect_timeout=2,
                           options="-c statement_timeout=1500 -c lock_timeout=700")

def observe(state, page, role):
    """Bounded session sample, not proof of a unique visitor or exact dwell time."""
    if not enabled() or page not in PAGES or role not in ROLES:
        return
    now=time.monotonic()
    last=state.get("hz_usage_last",0)
    previous=state.get("hz_usage_page")
    if now-last<30 and (previous==page or now-last<3):
        return
    session=state.setdefault("hz_usage_session",str(uuid4()))
    seconds=min(90,max(0,int(now-last))) if last else 0
    # Throttle failures too; analytics must not block application functionality.
    state["hz_usage_last"]=now
    state["hz_usage_page"]=page
    try:
        with _connect() as conn, conn.cursor() as cur:
            cur.execute("""INSERT INTO hz_usage_sessions(session_id,role) VALUES (%s,%s)
                ON CONFLICT(session_id) DO UPDATE SET last_seen=now(),role=EXCLUDED.role,
                observed_seconds=hz_usage_sessions.observed_seconds+%s""",(session,role,seconds))
            cur.execute("""INSERT INTO hz_usage_daily(day,session_id,page)
                VALUES ((now() AT TIME ZONE 'UTC')::date,%s,%s)
                ON CONFLICT(day,session_id,page) DO UPDATE SET samples=hz_usage_daily.samples+1""",(session,page))
    except Exception:
        pass

def record(feature, outcome, elapsed_ms):
    if not enabled() or feature not in FEATURES or outcome not in ("success","failure"):
        return
    try:
        elapsed_ms=max(0,min(600000,int(elapsed_ms)))
        with _connect() as conn, conn.cursor() as cur:
            cur.execute("""INSERT INTO hz_feature_daily(day,feature,outcome,total_ms)
                VALUES ((now() AT TIME ZONE 'UTC')::date,%s,%s,%s)
                ON CONFLICT(day,feature,outcome) DO UPDATE SET calls=hz_feature_daily.calls+1,
                total_ms=hz_feature_daily.total_ms+EXCLUDED.total_ms""",(feature,outcome,elapsed_ms))
    except Exception:
        pass

def measured(feature, fn, *args, **kwargs):
    """Count actual server calls, including structured failures; never change result."""
    start=time.monotonic()
    outcome="failure"
    try:
        result=fn(*args,**kwargs)
        outcome="failure" if result is None or (isinstance(result,dict) and result.get("error")) else "success"
        return result
    finally:
        record(feature,outcome,(time.monotonic()-start)*1000)
