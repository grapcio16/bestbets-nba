import unittest
from unittest.mock import patch
from admin_user_management import summarize_access, access_snapshot

class UserManagementTest(unittest.TestCase):
    def test_counts_and_privacy(self):
        result = summarize_access({"admin_emails":["PRIVATE@example.com"," private@example.com "],
            "premium_emails":["private@example.com","other@example.com"],
            "admin_subjects":["issuer|subject"]}, True)
        self.assertEqual(result["allowlist_counts"][1]["Admin entries"],1)
        self.assertEqual(result["allowlist_counts"][1]["Premium entries"],2)
        self.assertEqual(result["allowlist_counts"][1]["Overlapping entries"],1)
        self.assertIsNone(result["registered_accounts"])
        self.assertIsNone(result["paying_subscribers"])
        self.assertNotIn("example.com",str(result))
        self.assertNotIn("issuer|subject",str(result))

    def test_missing_and_malformed(self):
        result = summarize_access({"admin_emails":"not-a-list"},False)
        self.assertEqual(result["allowlist_counts"][1]["Admin entries"],0)
        self.assertFalse(result["oidc_configured"])

    def test_denial_before_secrets(self):
        for role in ("guest","free","premium"):
            with patch("access_control.current_role",return_value=role), patch("access_control._secret_section") as secrets:
                self.assertEqual(access_snapshot(),{"status":"denied"})
                secrets.assert_not_called()

if __name__ == "__main__":
    unittest.main()
