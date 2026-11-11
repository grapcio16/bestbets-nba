"""Offline, no-secret tests for the isolated BestBets Stripe sandbox."""
import unittest
from types import SimpleNamespace

from stripe_test_billing import (
    BillingNotConfigured, StripeTestGateway, TestBillingConfig, has_premium_access
)


def config(**changes):
    params = {
        "secret_key":"sk_test_FAKE_FOR_AUTOMATED_TESTS_123456",
        "price_id":"price_TEST123456",
        "webhook_secret":"whsec_FAKE_FOR_AUTOMATED_TESTS_123456",
        "app_url":"https://bestbets-nba.streamlit.app",
    }
    params.update(changes)
    return TestBillingConfig(**params)


class FakeSession:
    calls=[]
    @classmethod
    def create(cls, **kwargs):
        cls.calls.append(kwargs)
        return {"livemode": False, "url": "https://checkout.stripe.com/c/pay/cs_test_fake123"}


class FakePortal:
    calls=[]
    @classmethod
    def create(cls, **kwargs):
        cls.calls.append(kwargs)
        return {"livemode": False, "url": "https://billing.stripe.com/p/session/test123"}


class FakeWebhook:
    next_event={}
    args=[]
    @classmethod
    def construct_event(cls,payload,signature,secret):
        cls.args.append((payload,signature,secret))
        if signature != "t=1,v1=verified-for-fake-tests":
            raise ValueError("Signature verification failed")
        return cls.next_event


class FakeSDK:
    api_key=""
    checkout=SimpleNamespace(Session=FakeSession)
    billing_portal=SimpleNamespace(Session=FakePortal)
    Webhook=FakeWebhook


def event(kind, **overrides):
    obj={"customer":"cus_abc12345","subscription":"sub_abc12345","status":"active"}
    obj.update(overrides)
    return {"id":"evt_abc12345","type":kind,"livemode":False,"data":{"object":obj}}


class StripeTestBillingTest(unittest.TestCase):
    def setUp(self):
        FakeSession.calls.clear()
        FakePortal.calls.clear()
        FakeWebhook.args.clear()
        FakeWebhook.next_event={}
        self.gateway=StripeTestGateway(config(),FakeSDK)

    def test_no_live_key(self):
        with self.assertRaises(BillingNotConfigured):
            StripeTestGateway(config(secret_key="sk_live_FAKE_123456789"),FakeSDK)
        with self.assertRaises(BillingNotConfigured):
            StripeTestGateway(config(webhook_secret=""),FakeSDK)
        with self.assertRaises(BillingNotConfigured):
            StripeTestGateway(config(app_url="javascript:alert(1)"),FakeSDK)
        with self.assertRaises(BillingNotConfigured):
            StripeTestGateway(config(app_url="http://notlocalhost.example"),FakeSDK)

    def test_test_checkout_uses_server_identity_and_price(self):
        url=self.gateway.create_checkout(
            authenticated_user_id="test-user-1234",request_id="request-123456",
            verified_email="user@example.invalid"
        )
        self.assertTrue(url.startswith("https://checkout.stripe.com/"))
        p=FakeSession.calls[-1]
        self.assertEqual(p["mode"],"subscription")
        self.assertEqual(p["line_items"],[{"price":"price_TEST123456","quantity":1}])
        self.assertEqual(p["client_reference_id"],"test-user-1234")
        self.assertEqual(p["subscription_data"]["metadata"]["internal_user_id"],"test-user-1234")
        self.assertEqual(p["idempotency_key"],"bestbets-test-request-123456")
        self.assertEqual(p["customer_email"],"user@example.invalid")
        self.assertIn("{CHECKOUT_SESSION_ID}",p["success_url"])
        self.assertEqual(p["cancel_url"],"https://bestbets-nba.streamlit.app/?checkout=cancelled")

    def test_prevent_customer_id_forgery_patterns(self):
        with self.assertRaises(ValueError):
            self.gateway.create_checkout(authenticated_user_id="../guest",request_id="request-123456")
        with self.assertRaises(ValueError):
            self.gateway.create_checkout(authenticated_user_id="test-user-1234",request_id="x")
        with self.assertRaises(ValueError):
            self.gateway.create_checkout(authenticated_user_id="test-user-1234",request_id="request-123456",verified_customer_id="cus_bad?evil")
        with self.assertRaises(ValueError):
            self.gateway.create_checkout(authenticated_user_id="test-user-1234",request_id="request-123456",verified_customer_id="cus_12345678",verified_email="foo@example.invalid")

    def test_validated_portal(self):
        url=self.gateway.create_customer_portal(
            verified_customer_id="cus_abc12345",authenticated_user_id="test-user-1234"
        )
        self.assertEqual(url,"https://billing.stripe.com/p/session/test123")
        self.assertEqual(FakePortal.calls[-1]["customer"],"cus_abc12345")
        with self.assertRaises(ValueError):
            self.gateway.create_customer_portal(
                verified_customer_id="cus_../other",authenticated_user_id="test-user-1234"
            )

    def test_webhook_signature_is_checked_before_use(self):
        FakeWebhook.next_event=event("customer.subscription.updated",id="sub_abc12345")
        with self.assertRaises(ValueError):
            self.gateway.verify_webhook(raw_body=b'{"data":{}}',signature="invalid")
        self.assertTrue(FakeWebhook.args)
        self.assertEqual(FakeWebhook.args[-1][0],b'{"data":{}}')
        self.assertEqual(FakeWebhook.args[-1][2],config().webhook_secret)

    def test_subscription_status_updated_without_automatic_access(self):
        FakeWebhook.next_event=event("customer.subscription.updated",id="sub_abc12345",status="active")
        result=self.gateway.verify_webhook(raw_body=b"RAW-UNCHANGED",signature="t=1,v1=verified-for-fake-tests")
        self.assertEqual(result.kind,"customer.subscription.updated")
        self.assertEqual(result.subscription_status,"active")
        self.assertEqual(result.customer_id,"cus_abc12345")
        self.assertEqual(result.subscription_id,"sub_abc12345")
        self.assertTrue(has_premium_access("active"))
        self.assertTrue(has_premium_access("trialing"))
        for status in ("past_due","unpaid","incomplete","incomplete_expired","canceled",None,""):
            self.assertFalse(has_premium_access(status))
        FakeWebhook.next_event=event("customer.subscription.deleted",id="sub_abc12345",status="active")
        self.assertEqual(self.gateway.verify_webhook(raw_body=b"raw",signature="t=1,v1=verified-for-fake-tests").subscription_status,"canceled")

    def test_checkout_completion_does_not_grant_premium(self):
        FakeWebhook.next_event=event("checkout.session.completed",mode="subscription")
        e=self.gateway.verify_webhook(raw_body=b"raw",signature="t=1,v1=verified-for-fake-tests")
        self.assertIsNone(e.subscription_status)
        FakeWebhook.next_event=event("checkout.session.completed",mode="payment")
        self.assertIsNone(self.gateway.verify_webhook(raw_body=b"raw",signature="t=1,v1=verified-for-fake-tests"))

    def test_ignore_events_and_reject_live_webhook(self):
        FakeWebhook.next_event=event("charge.succeeded")
        self.assertIsNone(self.gateway.verify_webhook(raw_body=b"raw",signature="t=1,v1=verified-for-fake-tests"))
        FakeWebhook.next_event={**event("customer.subscription.updated",id="sub_abc12345"),"livemode":True}
        with self.assertRaises(BillingNotConfigured):
            self.gateway.verify_webhook(raw_body=b"raw",signature="t=1,v1=verified-for-fake-tests")
        with self.assertRaises(ValueError):
            self.gateway.verify_webhook(raw_body=b"",signature="t=1,v1=verified-for-fake-tests")
        with self.assertRaises(ValueError):
            self.gateway.verify_webhook(raw_body=b"raw",signature="")

    def test_invoice_events(self):
        FakeWebhook.next_event=event("invoice.payment_failed",subscription="sub_abc12345")
        e=self.gateway.verify_webhook(raw_body=b"raw",signature="t=1,v1=verified-for-fake-tests")
        self.assertEqual(e.kind,"invoice.payment_failed")
        self.assertIsNone(e.subscription_status)
        FakeWebhook.next_event=event("invoice.paid",subscription=None,parent={"subscription_details":{"subscription":"sub_abc12345"}})
        e=self.gateway.verify_webhook(raw_body=b"raw",signature="t=1,v1=verified-for-fake-tests")
        self.assertEqual(e.subscription_id,"sub_abc12345")

if __name__=="__main__":
    unittest.main()
