"""Authentication and entitlement regression tests. No live identity provider."""
import unittest
from datetime import datetime, timezone

from unittest.mock import patch
from access_control import account_key, role_from_claims, auth_context


NOW = datetime(2026, 11, 14, tzinfo=timezone.utc)
IDENTITY = {
    "iss": "https://accounts.google.com", "sub": "person-123",
    "email": "Owner@Example.com", "email_verified": True,
    "exp": 1820000000,
}


class RoleChecks(unittest.TestCase):
    def test_guest_never_gets_premium(self):
        self.assertEqual(role_from_claims({}, {"admin_emails": ["owner@example.com"]}, now=NOW), "guest")
        self.assertEqual(role_from_claims({"email": "owner@example.com"},
                                          {"admin_emails": ["owner@example.com"]}, now=NOW), "guest")

    def test_verified_admin_email_has_free_premium(self):
        self.assertEqual(role_from_claims(IDENTITY, {"admin_emails": ["owner@example.com"]}, now=NOW), "admin")
        self.assertEqual(role_from_claims(IDENTITY, {}, now=NOW), "free")

    def test_spoofed_email_or_unverified_claim_does_not_grant_admin(self):
        for value in (False, "true", None):
            user = {**IDENTITY, "email_verified": value}
            self.assertEqual(role_from_claims(user, {"admin_emails": ["owner@example.com"]}, now=NOW), "free")

    def test_subject_is_issuer_scoped_and_expires(self):
        key = account_key(IDENTITY)
        self.assertEqual(role_from_claims(IDENTITY, {"admin_subjects": [key]}, now=NOW), "admin")
        self.assertEqual(role_from_claims({**IDENTITY, "iss": "https://another.example"},
                                          {"admin_subjects": [key]}, now=NOW), "free")
        self.assertEqual(role_from_claims({**IDENTITY, "exp": 100},
                                          {"admin_subjects": [key]}, now=NOW), "guest")

    def test_paid_account_requires_explicit_server_allowlist(self):
        key = account_key(IDENTITY)
        self.assertEqual(role_from_claims(IDENTITY, {"premium_subjects": [key]}, now=NOW), "premium")
        self.assertEqual(role_from_claims(IDENTITY, {"premium_emails": ["owner@example.com"]}, now=NOW), "premium")
        self.assertEqual(role_from_claims(IDENTITY, {"premium_emails": ["other@example.com"]}, now=NOW), "free")

    def test_profile_context_discloses_only_authenticated_verified_email(self):
        for claims, expected in ((IDENTITY, IDENTITY["email"]),
                                 ({**IDENTITY, "email_verified": False}, ""),
                                 ({**IDENTITY, "exp": 100}, ""),
                                 ({}, "")):
            with self.subTest(claims=claims), patch("access_control.current_claims", return_value=claims), patch("access_control._secret_section", return_value={}), patch("access_control.auth_configured", return_value=True):
                data = auth_context()
                self.assertEqual(data["email"], expected)
                self.assertNotIn("sub", data)
                self.assertNotIn("iss", data)
                if data["role"] == "guest":
                    self.assertEqual(data["name"], "")
                    self.assertEqual(data["provider"], "")

if __name__ == "__main__":
    unittest.main()
