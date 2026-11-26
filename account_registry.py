"""Opt-in account registry and daily Props quota. Not an entitlement authority.

Only verified server-side identity may reach these functions. No runtime DDL.
The UTC calendar-day policy is provisional until global reset policy is approved.
"""
from hashlib import sha256
import hmac
import os
from uuid import uuid4

def pseudonymous_id(principal, secret):
    if not isinstance(principal, str) or not principal or principal == "guest":
        raise ValueError("Verified principal required")
    if not isinstance(secret, str) or len(secret.encode("utf-8")) < 32:
        raise ValueError("Dedicated account HMAC key required")
    return hmac.new(secret.encode("utf-8"), principal.encode("utf-8"), sha256).hexdigest()

def _identity():
    from access_control import current_principal, current_role
    role = current_role()
    if role not in ("free", "premium", "admin"):
        return None, "guest"
    return pseudonymous_id(current_principal(), os.environ.get("HOOPZARO_ACCOUNT_HMAC_KEY", "")), role

def _connect(url):
    if not url:
        raise RuntimeError("Dedicated account database configuration required")
    import psycopg
    return psycopg.connect(url, connect_timeout=5,
                           options="-c statement_timeout=5000 -c lock_timeout=3000")

def _observe(cur, account, role):
    cur.execute("""INSERT INTO hoopzaro_accounts(account_id,last_observed_role)
        VALUES (%s,%s) ON CONFLICT(account_id) DO UPDATE SET
        last_seen_at=now(), last_observed_role=EXCLUDED.last_observed_role""",
        (account,role))

def observe_current_account(url):
    """Record one verified account; role is a snapshot, never used for authorization."""
    account, role = _identity()
    if not account:
        return False
    with _connect(url) as conn, conn.cursor() as cur:
        _observe(cur,account,role)
    return True

def reserve_free_props(url):
    """Atomically admit at most one Free request per UTC day, across processes."""
    try:
        from access_control import current_role
        if current_role() in ("premium","admin"):
            return {"status":"unlimited"}
        account, role = _identity()
        if role != "free" or not account:
            return {"status":"login_required"}
        reservation = uuid4()
        with _connect(url) as conn, conn.cursor() as cur:
            _observe(cur,account,role)
            cur.execute("""INSERT INTO hoopzaro_props_daily(account_id,quota_day,reservation_id)
                VALUES (%s, (now() AT TIME ZONE 'UTC')::date, %s)
                ON CONFLICT(account_id,quota_day) DO NOTHING
                RETURNING quota_day""",(account,reservation))
            row = cur.fetchone()
        return ({"status":"reserved", "day":row[0], "token":reservation}
                if row else {"status":"limit_reached"})
    except Exception:
        # Fail closed; no fallback to session or local storage.
        return {"status":"unavailable"}

def refund_failed_props(url, reservation):
    """Server-only refund for a confirmed failed request before any result is exposed.

    Never accept a reservation or a success/failure decision from a browser.
    The token and date scope prevent a delayed failure deleting another request.
    """
    if not isinstance(reservation,dict) or reservation.get("status") != "reserved":
        return False
    try:
        account, role = _identity()
        if role != "free" or not account:
            return False
        with _connect(url) as conn, conn.cursor() as cur:
            cur.execute("""DELETE FROM hoopzaro_props_daily
                WHERE account_id=%s AND quota_day=%s AND reservation_id=%s""",
                (account,reservation["day"],reservation["token"]))
            deleted = cur.rowcount == 1
        return deleted
    except Exception:
        return False
