"""Bounded analytics retention. No payments, authentication, audit or quota mutations."""
import os

# UTC dates use 30/90 calendar-day windows including the current day.
# Retain account rows with quota dependencies; never cascade-delete quota.
RULES=(
    ("page_samples","hz_usage_daily","day < (now() AT TIME ZONE 'UTC')::date - 29"),
    ("sessions","hz_usage_sessions","last_seen < now()-interval '30 days' AND NOT EXISTS (SELECT 1 FROM public.hz_usage_daily d WHERE d.session_id=hz_usage_sessions.session_id)"),
    ("feature_aggregates","hz_feature_daily","day < (now() AT TIME ZONE 'UTC')::date - 89"),
    ("inactive_accounts","hoopzaro_accounts","last_seen_at < now()-interval '90 days' AND NOT EXISTS (SELECT 1 FROM public.hoopzaro_props_daily q WHERE q.account_id=hoopzaro_accounts.account_id)"),
)

def run(conn, apply=False):
    with conn.cursor() as cur:
        cur.execute("SELECT current_database()")
        if cur.fetchone()[0]!="hoopzaro_analytics":
            raise RuntimeError("Unexpected retention database")
        cur.execute("SET LOCAL statement_timeout='15s'")
        cur.execute("SET LOCAL lock_timeout='2s'")
        results={}
        for label,table,predicate in RULES:
            if apply:
                cur.execute(f"DELETE FROM public.{table} WHERE {predicate}")
                results[label]=cur.rowcount
            else:
                cur.execute(f"SELECT count(*) FROM public.{table} WHERE {predicate}")
                results[label]=cur.fetchone()[0]
        return results

def main():
    import json
    import psycopg
    url=os.environ.get("HOOPZARO_RETENTION_DATABASE_URL","").strip()
    apply=os.environ.get("HOOPZARO_RETENTION_APPLY","").strip().lower()=="true"
    if not url:
        raise SystemExit("Missing retention database configuration")
    try:
        with psycopg.connect(url,connect_timeout=5) as conn:
            if not apply:
                conn.execute("SET TRANSACTION READ ONLY")
            result=run(conn,apply=apply)
        print(json.dumps({"applied":apply,"counts":result},sort_keys=True))
    except Exception:
        raise SystemExit("Retention failed; transaction rolled back") from None

if __name__=="__main__":
    main()
