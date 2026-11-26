import unittest
from unittest.mock import patch
from admin_settings import DRAFT_DEFAULTS, validate_draft, settings_snapshot

class SettingsTest(unittest.TestCase):
    def test_default(self):
        self.assertEqual(validate_draft(DRAFT_DEFAULTS), DRAFT_DEFAULTS)
    def test_valid_announcement(self):
        result = validate_draft({**DRAFT_DEFAULTS,"announcement_enabled":True,"announcement_text":" Maintenance notice "})
        self.assertEqual(result["announcement_text"], "Maintenance notice")
    def test_reject_invalid(self):
        for change in ({"maintenance_requested":"yes"},{"announcement_enabled":True},{"announcement_text":"a"*301},{"announcement_text":"test\ntext"},{"price":1}):
            with self.assertRaises(ValueError):
                validate_draft({**DRAFT_DEFAULTS,**change})
    def test_access(self):
        for role in ("guest","free","premium"):
            with patch("access_control.current_role",return_value=role), patch("tracker_storage.tracker_database_url") as db:
                self.assertEqual(settings_snapshot(),{"status":"denied"})
                db.assert_not_called()
    def test_snapshot_redacts(self):
        with patch("access_control.current_role",return_value="admin"), patch("access_control.auth_configured",return_value=True), patch("tracker_storage.tracker_database_url",return_value="secret_db"), patch("admin_revenue.revenue_snapshot",return_value={"checkout_mode":"test","fulfillment_declared_ready":False,"secret":"secret_stripe"}), patch("admin_security.security_snapshot",return_value={"audit_storage_configured":True,"audit_key_configured":True,"key":"secret_audit"}):
            result=settings_snapshot()
            self.assertTrue(result["tracker_url_configured"])
            self.assertFalse(result["settings_write_enabled"])
            self.assertNotIn("secret_",str(result))

if __name__ == "__main__":
    unittest.main()
