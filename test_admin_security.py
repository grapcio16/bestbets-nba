import unittest
from unittest.mock import patch
from admin_security import security_snapshot, record_admin_event, read_recent_events

class SecurityTest(unittest.TestCase):
    def test_non_admin_denied_before_access(self):
        for role in ("guest", "free", "premium"):
            with patch("access_control.current_role", return_value=role), patch("admin_security.access_snapshot") as access:
                self.assertEqual(security_snapshot(), {"status":"denied"})
                self.assertEqual(read_recent_events(), {"status":"denied"})
                self.assertFalse(record_admin_event("review_models", "success"))
                access.assert_not_called()

    def test_no_arbitrary_payload(self):
        with patch("access_control.current_role") as role:
            self.assertFalse(record_admin_event("arbitrary content", "success"))
            self.assertFalse(record_admin_event("review_models", "arbitrary content"))
            role.assert_not_called()

    def test_summary_no_secret_values(self):
        access={"status":"ok","oidc_configured":True,"allowlist_counts":[{"Admin entries":2,"Overlapping entries":1},{"Admin entries":1,"Overlapping entries":0}]}
        with patch("access_control.current_role",return_value="admin"), patch("admin_security.access_snapshot",return_value=access), patch.dict("os.environ",{"HOOPZARO_AUDIT_DATABASE_URL":"private_url","HOOPZARO_AUDIT_HMAC_KEY":"s"*32},clear=True):
            result=security_snapshot()
            self.assertEqual(result["admin_identifier_entries"],3)
            self.assertEqual(result["overlap_entries"],1)
            self.assertTrue(result["audit_storage_configured"])
            self.assertTrue(result["audit_key_configured"])
            self.assertNotIn("private_url",str(result))
            self.assertNotIn("s"*32,str(result))

    def test_missing_storage(self):
        with patch("access_control.current_role",return_value="admin"), patch.dict("os.environ",{},clear=True):
            self.assertEqual(read_recent_events(),{"status":"setup_required"})

if __name__ == "__main__":
    unittest.main()
