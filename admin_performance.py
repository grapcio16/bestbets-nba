"""Read-only point-in-time performance diagnostics for verified admins."""
from datetime import datetime, timezone
from time import monotonic

def database_probe(url, connect=None, clock=monotonic):
    result = {"status": "setup_required", "connect_ms": None,
              "query_ms": None, "total_ms": None,
              "checked_utc": datetime.now(timezone.utc).isoformat()}
    if not url:
        return result
    start = clock()
    try:
        if connect is None:
            from psycopg import connect
        with connect(url, connect_timeout=5,
                     options="-c statement_timeout=3000 -c default_transaction_read_only=on") as conn:
            connected = clock()
            result["connect_ms"] = round((connected-start)*1000, 1)
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                if cur.fetchone() != (1,):
                    raise ValueError("Unexpected probe response")
            result["query_ms"] = round((clock()-connected)*1000, 1)
        result["status"] = "ok"
    except Exception:
        result["status"] = "unavailable"
    result["total_ms"] = round((clock()-start)*1000, 1)
    return result

def summarize_sources(rows):
    """Rank only successful HTTP/schema probes; never average in failures."""
    valid = [r for r in rows if r.get("status") in ("schema_ok", "empty_response")
             and isinstance(r.get("elapsed_ms"), (int, float))
             and r["elapsed_ms"] >= 0]
    return sorted(valid, key=lambda r: r["elapsed_ms"], reverse=True)
