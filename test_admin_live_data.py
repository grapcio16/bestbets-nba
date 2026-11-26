"""Offline integration contract tests. Never connect to live services."""
import unittest
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
