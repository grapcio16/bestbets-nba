from dataclasses import replace
from datetime import datetime, timedelta, timezone
import unittest
from billing_sandbox_policy import CheckoutBinding,SandboxEvidence,decide_sandbox_access

class SandboxDecisionTests(unittest.TestCase):
    def setUp(self):
        self.now=datetime(2026,11,26,12,tzinfo=timezone.utc)
        self.binding=CheckoutBinding("a"*64,"cs_test_fixture","cus_fixture","sub_fixture","price_fixture")
        self.evidence=SandboxEvidence(False,"cs_test_fixture","cus_fixture","sub_fixture","price_fixture","active","in_fixture",True,True,True,999,"usd",True,self.now-timedelta(days=1),self.now+timedelta(days=29),self.now)
        self.args=dict(principal_hmac="a"*64,configured_price_id="price_fixture",pilot_enabled=True,tester_allowed=True,now=self.now)
    def decide(self,evidence=None,binding=None,**kwargs):
        return decide_sandbox_access(binding or self.binding,evidence or self.evidence,**{**self.args,**kwargs})
    def test_valid_sandbox_grant_is_short_lived(self):
        result=self.decide()
        self.assertTrue(result.allowed)
        self.assertEqual(result.expires_at,self.now+timedelta(minutes=5))
    def test_flags_and_identity(self):
        for kwargs in (dict(pilot_enabled=False),dict(tester_allowed=False),dict(principal_hmac="b"*64),dict(configured_price_id="price_other")):
            with self.subTest(kwargs=kwargs):
                self.assertFalse(self.decide(**kwargs).allowed)
    def test_mismatch_or_live_never_grants(self):
        for fields in (dict(livemode=True),dict(livemode=None),dict(checkout_id="cs_test_other"),dict(customer_id="cus_other"),dict(subscription_id="sub_other"),dict(price_id="price_other"),dict(exact_single_monthly_item=False)):
            with self.subTest(fields=fields):
                self.assertFalse(self.decide(replace(self.evidence,**fields)).allowed)
    def test_no_trial_or_unpaid(self):
        for status in ("trialing","incomplete","past_due","unpaid","canceled","paused","unknown"):
            with self.subTest(status=status):
                self.assertFalse(self.decide(replace(self.evidence,subscription_status=status)).allowed)
    def test_payment_evidence_required(self):
        for fields in (dict(invoice_id=""),dict(invoice_paid=False),dict(captured_card_payment=False),dict(no_refund_or_dispute=False),dict(no_refund_or_dispute=None),dict(amount_minor=0),dict(amount_minor=998),dict(currency="eur"),dict(amount_minor=True)):
            with self.subTest(fields=fields):
                self.assertFalse(self.decide(replace(self.evidence,**fields)).allowed)
    def test_stale_future_expired_and_excessive_period(self):
        for fields in (dict(verified_at=self.now-timedelta(minutes=6)),dict(verified_at=self.now+timedelta(seconds=1)),dict(paid_through=self.now),dict(paid_from=self.now+timedelta(days=1)),dict(paid_through=self.now+timedelta(days=60)),dict(paid_through=self.now.replace(tzinfo=None))):
            with self.subTest(fields=fields):
                self.assertFalse(self.decide(replace(self.evidence,**fields)).allowed)
    def test_missing_evidence(self):
        self.assertFalse(decide_sandbox_access(self.binding,None,**self.args).allowed)

if __name__=="__main__":
    unittest.main()
