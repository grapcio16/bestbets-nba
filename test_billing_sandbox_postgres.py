"""Disposable CI PostgreSQL only. No Stripe or Neon calls."""
import os
import unittest
from pathlib import Path
if os.environ.get("HOOPZARO_CI_DISPOSABLE_PG")=="true":
    import psycopg
from billing_sandbox_store import Store,db
from billing_sandbox_policy import CheckoutBinding,Decision
from datetime import datetime,timezone,timedelta
OWNER="postgresql://postgres:fixture@127.0.0.1:5432/hoopzaro_billing_sandbox"
APP="postgresql://hz_billing_sandbox_app:fixture@127.0.0.1:5432/hoopzaro_billing_sandbox"
HOOK="postgresql://hz_billing_sandbox_webhook:fixture@127.0.0.1:5432/hoopzaro_billing_sandbox"
WORKER="postgresql://hz_billing_sandbox_reconcile:fixture@127.0.0.1:5432/hoopzaro_billing_sandbox"
@unittest.skipUnless(os.environ.get("HOOPZARO_CI_DISPOSABLE_PG")=="true","CI only")
class BillingStoreTests(unittest.TestCase):
    def test_persist_and_isolate(self):
        with psycopg.connect(OWNER,autocommit=True) as c:
            c.execute("CREATE ROLE hz_billing_sandbox_app LOGIN PASSWORD 'fixture'")
            c.execute("CREATE ROLE hz_billing_sandbox_webhook LOGIN PASSWORD 'fixture'")
            c.execute(Path("migrations/billing_sandbox_v1.sql").read_text())
            c.execute(Path("migrations/billing_sandbox_lifecycle_v1.sql").read_text())
            c.execute("CREATE ROLE hz_billing_sandbox_reconcile LOGIN PASSWORD 'fixture'")
            c.execute(Path("migrations/billing_sandbox_reconcile_v1.sql").read_text())
            c.execute(Path("migrations/billing_sandbox_retry_v1.sql").read_text())
        store=Store(APP)
        a=store.reserve("a"*64)
        self.assertEqual(a.attempt_id,store.reserve("a"*64).attempt_id)
        store.save_checkout(a,"cs_test_fixture")
        a=store.get("a"*64)
        b=CheckoutBinding(a.account_id,a.checkout_id,"cus_fixture","sub_fixture","price_fixture")
        store.bind_subscription(a,b)
        self.assertEqual(store.get("a"*64).subscription_id,"sub_fixture")
        now=datetime.now(timezone.utc)
        good=Decision(True,"verified_sandbox_payment",now+timedelta(minutes=5))
        denied=Decision(False,"refund_or_dispute")
        self.assertTrue(store.record_verification(a.account_id,now,good))
        self.assertTrue(store.record_verification(a.account_id,now+timedelta(seconds=1),denied))
        self.assertFalse(store.record_verification(a.account_id,now,good))
        with db(APP) as cur:
            cur.execute("SELECT allowed,reason,expires_at FROM hz_sandbox_verification WHERE account_id=%s",(a.account_id,))
            self.assertEqual(cur.fetchone(),(False,"refund_or_dispute",None))
        with self.assertRaises(psycopg.errors.CheckViolation):
            store.record_verification(a.account_id,now+timedelta(seconds=2),Decision(True,"verified_sandbox_payment",now+timedelta(days=30)))
        with self.assertRaises(psycopg.errors.InsufficientPrivilege):
            with db(HOOK) as cur:
                cur.execute("SELECT * FROM hz_sandbox_verification")
        self.assertIsNone(store.get("b"*64))
        other=store.reserve("b"*64)
        with self.assertRaises(psycopg.errors.UniqueViolation):
            store.save_checkout(other,"cs_test_fixture")
        with db(HOOK) as cur:
            for _ in range(2):
                cur.execute("INSERT INTO hz_sandbox_webhook_events(event_id,event_type) VALUES ('evt_fixture','invoice.paid') ON CONFLICT(event_id) DO NOTHING")
        with psycopg.connect(OWNER) as c:
            self.assertEqual(c.execute("SELECT count(*) FROM hz_sandbox_webhook_events").fetchone()[0],1)
        from billing_sandbox_reconcile import verify_role
        verify_role(WORKER)
        worker=Store(WORKER)
        self.assertEqual(worker.get(a.account_id).subscription_id,"sub_fixture")
        self.assertTrue(worker.record_verification(a.account_id,now+timedelta(seconds=3),denied))
        for sql in ("DELETE FROM hz_sandbox_verification","INSERT INTO hz_sandbox_checkout(account_id,attempt_id) VALUES ('x',gen_random_uuid())","UPDATE hz_sandbox_checkout SET checkout_id=NULL","SELECT * FROM hz_sandbox_webhook_events"):
            with self.subTest(sql=sql),self.assertRaises(psycopg.errors.InsufficientPrivilege):
                with db(WORKER) as cur:
                    cur.execute(sql)
        for url,sql in ((APP,"DELETE FROM hz_sandbox_verification"),(APP,"DELETE FROM hz_sandbox_checkout"),(APP,"UPDATE hz_sandbox_checkout SET account_id='x'"),(APP,"SELECT * FROM hz_sandbox_webhook_events"),(HOOK,"SELECT * FROM hz_sandbox_checkout")):
            with self.subTest(sql=sql),self.assertRaises(psycopg.errors.InsufficientPrivilege):
                with psycopg.connect(url) as c:
                    c.execute(sql)
        self.assertFalse(store.prepare_retry(a))  # refund is not terminal
        terminal=Decision(False,"subscription_not_active")
        self.assertTrue(worker.record_verification(a.account_id,now+timedelta(seconds=4),terminal,a.attempt_id))
        with self.assertRaises(psycopg.errors.InsufficientPrivilege):
            worker.prepare_retry(a)
        self.assertTrue(store.prepare_retry(a))
        self.assertFalse(store.prepare_retry(a))
        new=store.get(a.account_id)
        self.assertNotEqual(new.attempt_id,a.attempt_id)
        self.assertIsNone(new.checkout_id)
        self.assertIsNone(new.customer_id)
        self.assertFalse(worker.record_verification(a.account_id,now+timedelta(seconds=10),good,a.attempt_id))
        with psycopg.connect(OWNER) as c:
            self.assertEqual(c.execute("SELECT count(*) FROM hz_sandbox_checkout_history WHERE attempt_id=%s AND subscription_id='sub_fixture'",(a.attempt_id,)).fetchone()[0],1)
            self.assertEqual(c.execute("SELECT allowed,reason,expires_at FROM hz_sandbox_verification WHERE account_id=%s",(a.account_id,)).fetchone(),(False,"checkout_incomplete",None))
        with self.assertRaises(psycopg.errors.InsufficientPrivilege):
            with db(APP) as cur: cur.execute("DELETE FROM hz_sandbox_checkout_history")
        with self.assertRaises(psycopg.errors.InsufficientPrivilege):
            with db(APP) as cur: cur.execute("UPDATE hz_sandbox_checkout SET attempt_id=gen_random_uuid()")
if __name__=="__main__": unittest.main()

