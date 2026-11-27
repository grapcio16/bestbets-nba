"""Run ONLY against disposable CI PostgreSQL, never against Neon."""
import os
import unittest
from pathlib import Path
if os.environ.get("HOOPZARO_CI_DISPOSABLE_PG")=="true":
    import psycopg
OWNER="postgresql://postgres:fixture@127.0.0.1:5432/hoopzaro_analytics"
RUNNER="postgresql://hz_retention_runner:fixture@127.0.0.1:5432/hoopzaro_analytics"
@unittest.skipUnless(os.environ.get("HOOPZARO_CI_DISPOSABLE_PG")=="true","CI only")
class RetentionPostgresTests(unittest.TestCase):
    def test_fixed_scope(self):
        with psycopg.connect(OWNER,autocommit=True) as conn:
            conn.execute("""CREATE ROLE hz_retention_runner LOGIN PASSWORD 'fixture';
            CREATE TABLE hoopzaro_accounts(account_id text PRIMARY KEY,last_seen_at timestamptz);
            CREATE TABLE hoopzaro_props_daily(account_id text REFERENCES hoopzaro_accounts ON DELETE CASCADE,quota_day date);
            CREATE TABLE hz_usage_sessions(session_id uuid PRIMARY KEY,last_seen timestamptz);
            CREATE TABLE hz_usage_daily(day date,session_id uuid,page text);
            CREATE TABLE hz_feature_daily(day date,feature text);
            CREATE TABLE hz_session_consent(receipt_id uuid);
            CREATE TABLE hz_account_consent(receipt_id uuid);
            CREATE TABLE hoopzaro_admin_audit(id int);
            INSERT INTO hoopzaro_accounts VALUES ('old',now()-interval '100 days'),('quota',now()-interval '100 days'),('recent',now());
            INSERT INTO hoopzaro_props_daily VALUES ('quota',current_date);
            INSERT INTO hz_usage_sessions VALUES ('00000000-0000-4000-8000-000000000001',now()-interval '31 days'),('00000000-0000-4000-8000-000000000002',now()-interval '31 days'),('00000000-0000-4000-8000-000000000003',now());
            INSERT INTO hz_usage_daily VALUES ((now() AT TIME ZONE 'UTC')::date-31,'00000000-0000-4000-8000-000000000001','home'),((now() AT TIME ZONE 'UTC')::date,'00000000-0000-4000-8000-000000000002','home');
            INSERT INTO hz_feature_daily VALUES ((now() AT TIME ZONE 'UTC')::date-91,'simulation'),((now() AT TIME ZONE 'UTC')::date,'simulation');
            INSERT INTO hz_session_consent VALUES (gen_random_uuid());
            INSERT INTO hz_account_consent VALUES (gen_random_uuid());
            INSERT INTO hoopzaro_admin_audit VALUES (1);""")
            conn.execute(Path("migrations/retention_runner_v2.sql").read_text())
        from analytics_retention import run,verify_runner
        with psycopg.connect(RUNNER) as conn:
            conn.execute("SET TRANSACTION READ ONLY")
            self.assertTrue(verify_runner(conn))
        with psycopg.connect(OWNER) as conn:
            with self.assertRaises(RuntimeError):
                verify_runner(conn)
        with psycopg.connect(RUNNER) as conn:
            self.assertEqual(run(conn,apply=True),dict(page_samples=1,sessions=1,feature_aggregates=1,inactive_accounts=1))
            self.assertEqual(run(conn,apply=True),dict(page_samples=0,sessions=0,feature_aggregates=0,inactive_accounts=0))
        with psycopg.connect(OWNER) as conn:
            self.assertEqual(conn.execute("SELECT account_id FROM hoopzaro_accounts ORDER BY 1").fetchall(),[("quota",),("recent",)])
            for table in ("hoopzaro_props_daily","hz_session_consent","hz_account_consent","hoopzaro_admin_audit"):
                self.assertEqual(conn.execute("SELECT count(*) FROM "+table).fetchone()[0],1)
        for sql in ("SELECT * FROM hoopzaro_accounts","DELETE FROM hz_usage_daily","DELETE FROM hoopzaro_props_daily"):
            with self.subTest(sql=sql),self.assertRaises(psycopg.errors.InsufficientPrivilege):
                with psycopg.connect(RUNNER) as conn:
                    conn.execute(sql)
if __name__=="__main__":
    unittest.main()
