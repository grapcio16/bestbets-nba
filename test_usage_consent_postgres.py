"""Integration test ONLY against a disposable CI Postgres service."""
import os
import unittest
from pathlib import Path
from unittest.mock import patch
from contextlib import contextmanager
import psycopg
from usage_consent_receipts import create_receipt,close_receipt,NOTICE_VERSION

OWNER="postgresql://postgres:fixture@127.0.0.1:5432/hoopzaro_analytics"
WRITER="postgresql://hz_analytics_writer:fixture@127.0.0.1:5432/hoopzaro_analytics"
@contextmanager
def cursor(url):
    with psycopg.connect(url) as conn,conn.cursor() as cur:
        yield cur

@unittest.skipUnless(os.environ.get("HOOPZARO_CI_DISPOSABLE_PG")=="true","disposable CI database only")
class PostgresReceiptTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with psycopg.connect(OWNER,autocommit=True) as conn:
            conn.execute("CREATE ROLE hz_analytics_writer LOGIN PASSWORD 'fixture'")
            conn.execute("CREATE ROLE hz_analytics_reader NOLOGIN")
            conn.execute(Path("migrations/20261126_consent_receipts.sql").read_text())
    def test_receipt_transaction_and_permissions(self):
        env={"HOOPZARO_USAGE_CONSENT_READY":"true","HOOPZARO_USAGE_NOTICE_VERSION":NOTICE_VERSION,
             "HOOPZARO_USAGE_NOTICE_URL":"https://hoopzaro.com/privacy",
             "HOOPZARO_ACCOUNT_REGISTRY_ENABLED":"true","HOOPZARO_ACCOUNT_HMAC_KEY":"x"*32,
             "HOOPZARO_ACCOUNT_DATABASE_URL":"fixture"}
        with patch.dict(os.environ,env,clear=True):
            grant=create_receipt(cursor,WRITER,"free","issuer|subject")
            guest=create_receipt(cursor,WRITER,"guest","guest")
            self.assertIsNone(guest.account_receipt_id)
        with psycopg.connect(OWNER) as conn:
            row=conn.execute("SELECT role,notice_version,ended_at,expires_at>accepted_at FROM hz_session_consent WHERE receipt_id=%s",(grant.session_id,)).fetchone()
            self.assertEqual(row,("free",NOTICE_VERSION,None,True))
            row=conn.execute("SELECT account_id FROM hz_account_consent WHERE receipt_id=%s",(grant.account_receipt_id,)).fetchone()
            self.assertEqual(row,(grant.account_id,))
        close_receipt(cursor,WRITER,grant.session_id,grant.account_receipt_id,"withdrawn")
        close_receipt(cursor,WRITER,grant.session_id,grant.account_receipt_id,"logout")
        with psycopg.connect(OWNER) as conn:
            self.assertEqual(conn.execute("SELECT end_reason FROM hz_session_consent WHERE receipt_id=%s",(grant.session_id,)).fetchone(),("withdrawn",))
            self.assertEqual(conn.execute("SELECT end_reason FROM hz_account_consent WHERE receipt_id=%s",(grant.account_receipt_id,)).fetchone(),("withdrawn",))
        for sql in ("SELECT account_id FROM hz_account_consent","DELETE FROM hz_session_consent","UPDATE hz_session_consent SET notice_version='tampered'"):
            with self.subTest(sql=sql),self.assertRaises(psycopg.errors.InsufficientPrivilege):
                with psycopg.connect(WRITER) as conn:
                    conn.execute(sql)
        with self.assertRaises(psycopg.errors.CheckViolation):
            with psycopg.connect(WRITER) as conn:
                conn.execute("INSERT INTO hz_session_consent(receipt_id,notice_version,notice_url,purpose,role) VALUES(gen_random_uuid(),'v','url','other','free')")

if __name__=="__main__":
    unittest.main()
