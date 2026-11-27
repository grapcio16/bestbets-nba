"""Disposable CI PostgreSQL only. No Stripe or Neon calls."""
import os
import unittest
from pathlib import Path
if os.environ.get("HOOPZARO_CI_DISPOSABLE_PG")=="true":
    import psycopg
from billing_sandbox_store import Store,db
from billing_sandbox_policy import CheckoutBinding
OWNER="postgresql://postgres:fixture@127.0.0.1:5432/hoopzaro_billing_sandbox"
APP="postgresql://hz_billing_sandbox_app:fixture@127.0.0.1:5432/hoopzaro_billing_sandbox"
HOOK="postgresql://hz_billing_sandbox_webhook:fixture@127.0.0.1:5432/hoopzaro_billing_sandbox"
@unittest.skipUnless(os.environ.get("HOOPZARO_CI_DISPOSABLE_PG")=="true","CI only")
class BillingStoreTests(unittest.TestCase):
    def test_persist_and_isolate(self):
        with psycopg.connect(OWNER,autocommit=True) as c:
            c.execute("CREATE ROLE hz_billing_sandbox_app LOGIN PASSWORD 'fixture'")
            c.execute("CREATE ROLE hz_billing_sandbox_webhook LOGIN PASSWORD 'fixture'")
            c.execute(Path("migrations/billing_sandbox_v1.sql").read_text())
        store=Store(APP)
        a=store.reserve("a"*64)
        self.assertEqual(a.attempt_id,store.reserve("a"*64).attempt_id)
        store.save_checkout(a,"cs_test_fixture")
        a=store.get("a"*64)
        b=CheckoutBinding(a.account_id,a.checkout_id,"cus_fixture","sub_fixture","price_fixture")
        store.bind_subscription(a,b)
        self.assertEqual(store.get("a"*64).subscription_id,"sub_fixture")
        self.assertIsNone(store.get("b"*64))
        other=store.reserve("b"*64)
        with self.assertRaises(psycopg.errors.UniqueViolation):
            store.save_checkout(other,"cs_test_fixture")
        with db(HOOK) as cur:
            for _ in range(2):
                cur.execute("INSERT INTO hz_sandbox_webhook_events(event_id,event_type) VALUES ('evt_fixture','invoice.paid') ON CONFLICT(event_id) DO NOTHING")
        with psycopg.connect(OWNER) as c:
            self.assertEqual(c.execute("SELECT count(*) FROM hz_sandbox_webhook_events").fetchone()[0],1)
        for url,sql in ((APP,"DELETE FROM hz_sandbox_checkout"),(APP,"UPDATE hz_sandbox_checkout SET account_id='x'"),(APP,"SELECT * FROM hz_sandbox_webhook_events"),(HOOK,"SELECT * FROM hz_sandbox_checkout")):
            with self.subTest(sql=sql),self.assertRaises(psycopg.errors.InsufficientPrivilege):
                with psycopg.connect(url) as c:
                    c.execute(sql)
if __name__=="__main__": unittest.main()
