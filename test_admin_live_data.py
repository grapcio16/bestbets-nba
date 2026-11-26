"""Offline integration contract tests. Never connect to live services."""
import unittest
from datetime import datetime, timezone
from admin_stripe_payments import stripe_payment_summary, payment_rows, money_label
from unittest.mock import Mock, patch
from admin_live_data import stripe_test_summary, tracker_summary, account_summary
from account_registry import can_show_free_result, free_props_enabled, registry_enabled

class LiveDataTests(unittest.TestCase):
    def test_tracker_missing_configuration(self):
        self.assertEqual(tracker_summary("","2026-27"),{"status":"setup_required"})
    def test_account_admin_gate(self):
        for role in ("guest","free","premium"):
            with patch("access_control.current_role",return_value=role):
                self.assertEqual(account_summary(),{"status":"denied"})
    def test_stripe_admin_gate_and_restricted_key(self):
        get=Mock()
        with patch("access_control.current_role",return_value="free"):
            self.assertEqual(stripe_test_summary(get),{"status":"denied"})
        with patch("access_control.current_role",return_value="admin"), patch.dict("os.environ",{"HOOPZARO_STRIPE_TEST_READ_KEY":"rk_live_placeholder"},clear=True):
            self.assertEqual(stripe_test_summary(get),{"status":"test_restricted_key_required"})
        get.assert_not_called()
    def test_stripe_counts_and_redaction(self):
        response=Mock(status_code=200)
        response.json.return_value={"data":[{"id":"sub_fixture","livemode":False,"status":"active","customer":"private"}],"has_more":False}
        get=Mock(return_value=response)
        with patch("access_control.current_role",return_value="admin"), patch.dict("os.environ",{"HOOPZARO_STRIPE_TEST_READ_KEY":"rk_test_fixture"},clear=True):
            result=stripe_test_summary(get)
        self.assertEqual(result["subscription_counts"],{"active":1})
        self.assertNotIn("private",str(result))
        self.assertNotIn("sub_fixture",str(result))
        self.assertNotIn("rk_test_fixture",str(result))
    def test_live_data_rejected(self):
        response=Mock(status_code=200)
        response.json.return_value={"data":[{"id":"sub_fixture","livemode":True,"status":"active"}],"has_more":False}
        with patch("access_control.current_role",return_value="admin"), patch.dict("os.environ",{"HOOPZARO_STRIPE_TEST_READ_KEY":"rk_test_fixture"},clear=True):
            self.assertEqual(stripe_test_summary(Mock(return_value=response)),{"status":"unavailable"})
    def test_payment_gate_and_empty_data(self):
        get=Mock()
        now=datetime(2026,11,26,tzinfo=timezone.utc)
        with patch("access_control.current_role",return_value="free"):
            self.assertEqual(stripe_payment_summary(get,now),{"status":"denied"})
        with patch("access_control.current_role",return_value="admin"), patch.dict("os.environ",{"HOOPZARO_STRIPE_TEST_READ_KEY":"rk_live_fixture"},clear=True):
            self.assertEqual(stripe_payment_summary(get,now),{"status":"test_restricted_key_required"})
        get.assert_not_called()
        response=Mock(status_code=200)
        response.json.return_value={"data":[],"has_more":False}
        with patch("access_control.current_role",return_value="admin"), patch.dict("os.environ",{"HOOPZARO_STRIPE_TEST_READ_KEY":"rk_test_fixture"},clear=True):
            result=stripe_payment_summary(Mock(return_value=response),now)
        self.assertEqual(result["status"],"ok")
        self.assertEqual(result["currencies"],{})
    def test_payment_totals_redaction_and_currency_separation(self):
        now=datetime(2026,11,26,tzinfo=timezone.utc)
        row={"id":"ch_private","livemode":False,"currency":"usd","created":int(now.timestamp())-100,
             "status":"succeeded","paid":True,"captured":True,"amount_captured":999,"amount_refunded":100,
             "billing_details":{"email":"private@example.invalid"}}
        responses=[]
        for rows,more in (([row],True),([{**row,"id":"ch_other","currency":"eur","amount_captured":2000,"amount_refunded":0},
             {**row,"id":"ch_failed","status":"failed","paid":False,"captured":False,"amount_captured":0,"amount_refunded":0}],False)):
            resp=Mock(status_code=200)
            resp.json.return_value={"data":rows,"has_more":more}
            responses.append(resp)
        get=Mock(side_effect=responses)
        with patch("access_control.current_role",return_value="admin"), patch.dict("os.environ",{"HOOPZARO_STRIPE_TEST_READ_KEY":"rk_test_fixture"},clear=True):
            result=stripe_payment_summary(get,now)
        self.assertEqual(result["currencies"]["usd"],{"captured_minor":999,"refunded_minor":100,"successful":1,"failed":1,"other":0})
        self.assertEqual(result["currencies"]["eur"]["captured_minor"],2000)
        self.assertEqual(get.call_args.kwargs["params"]["starting_after"],"ch_private")
        self.assertFalse(get.call_args.kwargs["allow_redirects"])
        self.assertNotIn("private",str(result))
        self.assertNotIn("rk_test_",str(result))
        self.assertEqual(payment_rows(result)[1]["Pobrano (test)"],"9.99 USD")
        self.assertEqual(money_label(1000,"jpy"),"1,000 jedn. API (JPY)")
    def test_payment_incomplete_or_live_rejected(self):
        now=datetime(2026,11,26,tzinfo=timezone.utc)
        row={"id":"ch_fixture","livemode":False,"currency":"usd","created":int(now.timestamp())-100,
             "status":"succeeded","paid":True,"captured":True,"amount_captured":999,"amount_refunded":0}
        def response(data,more):
            r=Mock(status_code=200)
            r.json.return_value={"data":data,"has_more":more}
            return r
        with patch("access_control.current_role",return_value="admin"), patch.dict("os.environ",{"HOOPZARO_STRIPE_TEST_READ_KEY":"rk_test_fixture"},clear=True):
            self.assertEqual(stripe_payment_summary(Mock(return_value=response([{**row,"livemode":True}],False)),now),{"status":"unavailable"})
            self.assertEqual(stripe_payment_summary(Mock(return_value=response([row],True)),now),{"status":"unavailable"})
            get=Mock(side_effect=[response([{**row,"id":f"ch_{i}"}],True) for i in range(5)])
            self.assertEqual(stripe_payment_summary(get,now),{"status":"page_limit_reached"})
            self.assertEqual(payment_rows({"status":"page_limit_reached"}),[])
    def test_rollout_default_off(self):
        with patch.dict("os.environ",{},clear=True):
            self.assertFalse(registry_enabled())
            self.assertFalse(free_props_enabled())
        with patch.dict("os.environ",{"HOOPZARO_ACCOUNT_REGISTRY_ENABLED":"true","HOOPZARO_ACCOUNT_DATABASE_URL":"fake","HOOPZARO_ACCOUNT_HMAC_KEY":"a"*32},clear=True):
            self.assertTrue(registry_enabled())
            self.assertFalse(free_props_enabled())
    def test_free_result_bound_to_date_and_role(self):
        today="2026-11-26"
        self.assertTrue(can_show_free_result("free",True,today,today))
        for role,enabled,day in (("guest",True,today),("free",False,today),("free",True,"2026-11-25"),("free",True,None)):
            self.assertFalse(can_show_free_result(role,enabled,day,today))

if __name__=="__main__":
    unittest.main()
