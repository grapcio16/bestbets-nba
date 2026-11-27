"""Admin-only security diagnostics and opt-in structured audit storage."""
import os
from account_registry import pseudonymous_id
from admin_user_management import access_snapshot

ACTIONS = frozenset(("refresh_telemetry", "review_access", "review_models"))
OUTCOMES = frozenset(("success", "failure"))

def audit_enabled():
    return (os.environ.get("HOOPZARO_ADMIN_AUDIT_ENABLED","").strip().lower()=="true"
            and bool(os.environ.get("HOOPZARO_AUDIT_DATABASE_URL","").strip())
            and len(os.environ.get("HOOPZARO_AUDIT_HMAC_KEY","").encode("utf-8"))>=32)

def security_snapshot():
    from access_control import current_role
    if current_role() != "admin":
        return {"status": "denied"}
    access = access_snapshot()
    if access.get("status") != "ok":
        return {"status": "denied"}
    rows = access["allowlist_counts"]
    return {"status": "ok", "oidc_configured": access["oidc_configured"],
            "admin_identifier_entries": sum(row["Admin entries"] for row in rows),
            "overlap_entries": sum(row["Overlapping entries"] for row in rows),
            "audit_recording_enabled": audit_enabled(),
            "audit_storage_configured": bool(os.environ.get("HOOPZARO_AUDIT_DATABASE_URL", "").strip()),
            "audit_key_configured": len(os.environ.get("HOOPZARO_AUDIT_HMAC_KEY", "").encode("utf-8")) >= 32}

def record_admin_event(action, outcome):
    """Explicit trusted server calls only, with opt-in storage."""
    if action not in ACTIONS or outcome not in OUTCOMES or not audit_enabled():
        return False
    from access_control import current_role, current_principal
    if current_role() != "admin":
        return False
    try:
        actor = pseudonymous_id(current_principal(), os.environ.get("HOOPZARO_AUDIT_HMAC_KEY", ""))
        url = os.environ.get("HOOPZARO_AUDIT_DATABASE_URL", "").strip()
        if not url:
            return False
        import psycopg
        with psycopg.connect(url, connect_timeout=5,
                             options="-c statement_timeout=3000 -c lock_timeout=2000") as conn:
            with conn.cursor() as cur:
                cur.execute("""INSERT INTO hoopzaro_admin_audit(actor_id,action,outcome)
                               VALUES (%s,%s,%s)""", (actor,action,outcome))
        return True
    except Exception:
        return False

def read_recent_events():
    from access_control import current_role
    if current_role() != "admin":
        return {"status":"denied"}
    url = os.environ.get("HOOPZARO_AUDIT_DATABASE_URL", "").strip()
    if not url:
        return {"status":"setup_required"}
    try:
        import psycopg
        from psycopg.rows import dict_row
        with psycopg.connect(url, connect_timeout=5, row_factory=dict_row,
                             options="-c statement_timeout=3000 -c default_transaction_read_only=on") as conn:
            with conn.cursor() as cur:
                cur.execute("""SELECT occurred_at,action,outcome FROM hoopzaro_admin_audit
                    ORDER BY occurred_at DESC,event_id DESC LIMIT 100""")
                rows = cur.fetchall()
        return {"status":"ok","events":[{**row,"occurred_at":row["occurred_at"].isoformat()} for row in rows]}
    except Exception:
        return {"status":"unavailable"}
