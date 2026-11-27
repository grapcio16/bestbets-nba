import json
import unittest
from unittest.mock import patch
from billing_sandbox_reconcile import parse_config,ReadOnlyStripe,reconcile
from billing_sandbox_adapter import BillingError,StripeTestAPI
from billing_sandbox_policy import Decision
from test_billing_sandbox_adapter import API

def fixture():
    return dict(database_url="postgresql://hz_billing_sandbox_reconcile:fixture@example.invalid/hoopzaro_billing_sandbox",
                stripe_key="rk_test_fixture0123456789",stripe_account="acct_fixture",
                price_id="price_fixture",product_id="prod_fixture",testers=["a"*64])

class ReconcileTests(unittest.TestCase):
    def test_config_boundaries(self):
        cfg=fixture()
        self.assertEqual(parse_config(json.dumps(cfg)),cfg)
        for changes in ({"stripe_key":"sk_test_fixture0123456789"},{"stripe_key":"rk_live_fixture0123456789"},
            {"database_url":cfg["database_url"].replace("reconcile","app")},
            {"database_url":cfg["database_url"].replace("/hoopzaro_billing_sandbox","/neondb")},
            {"testers":[]},{"testers":["a"*64,"a"*64]},{"testers":["bad"]},{"testers":["a"*64]*11}):
            with self.subTest(changes=list(changes)),self.assertRaises((ValueError,BillingError)):
                parse_config(json.dumps({**cfg,**changes}))
    def test_transport_no_writes(self):
        api=ReadOnlyStripe("rk_test_fixture0123456789","acct_fixture")
        with patch.object(StripeTestAPI,"request",return_value={"id":"acct_fixture"}) as request:
            for params,key in (({},None),(None,"fixture"),({"x":"y"},"fixture")):
                with self.assertRaises(BillingError):
                    api.request("/v1/checkout/sessions",params,key)
            request.assert_not_called()
            self.assertEqual(api.request("/v1/account"),{"id":"acct_fixture"})
            request.assert_called_once_with("/v1/account")
    def test_worker_only_explicit_testers(self):
        cfg=fixture()
        with patch("billing_sandbox_reconcile.verify_role"),patch("billing_sandbox_reconcile.ReadOnlyStripe",return_value=API()),patch("billing_sandbox_reconcile.SandboxService") as service:
            worker=service.return_value
            worker.reconcile_account.return_value=Decision(False,"subscription_not_active")
            self.assertEqual(reconcile(cfg),{"denied":1})
            worker.reconcile_account.assert_called_once_with("a"*64)
            worker.start.assert_not_called()
            worker.reconcile_account.return_value=Decision(False,"verification_unavailable_or_invalid")
            self.assertEqual(reconcile(cfg),{"denied":1,"verification_errors":1})
if __name__=="__main__":
    unittest.main()
