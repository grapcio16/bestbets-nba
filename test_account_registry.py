import os
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
from uuid import uuid4
from account_registry import pseudonymous_id, reserve_free_props, refund_failed_props

class RegistryUnitTest(unittest.TestCase):
    def test_pseudonym(self):
        key = "a"*32
        self.assertEqual(pseudonymous_id("issuer|subject",key),pseudonymous_id("issuer|subject",key))
        self.assertNotEqual(pseudonymous_id("issuer|subject",key),pseudonymous_id("issuer|Subject",key))
        self.assertNotIn("subject",pseudonymous_id("issuer|subject",key))
        for principal, secret in (("guest",key),("issuer|subject","short")):
            with self.assertRaises(ValueError):
                pseudonymous_id(principal,secret)

    def test_admin_premium_bypass(self):
        for role in ("admin","premium"):
            with patch("access_control.current_role",return_value=role), patch("account_registry._connect") as db:
                self.assertEqual(reserve_free_props(""),{"status":"unlimited"})
                db.assert_not_called()

    def test_guest_and_failure(self):
        with patch("access_control.current_role",return_value="guest"), patch("account_registry._identity",return_value=(None,"guest")):
            self.assertEqual(reserve_free_props(""),{"status":"login_required"})
        with patch("access_control.current_role",return_value="free"), patch("account_registry._identity",return_value=("a"*64,"free")):
            self.assertEqual(reserve_free_props(""),{"status":"unavailable"})

@unittest.skipUnless(os.environ.get("HOOPZARO_TEST_ACCOUNT_DB"),"isolated PostgreSQL test DB required")
class RegistryPostgresTest(unittest.TestCase):
    def test_parallel_limit_and_token_scoped_refund(self):
        url=os.environ["HOOPZARO_TEST_ACCOUNT_DB"]
        account=pseudonymous_id(str(uuid4()),"b"*32)
        with patch("access_control.current_role",return_value="free"), patch("account_registry._identity",return_value=(account,"free")):
            with ThreadPoolExecutor(max_workers=8) as pool:
                results=list(pool.map(lambda _: reserve_free_props(url), range(8)))
            self.assertEqual(sum(r["status"]=="reserved" for r in results),1)
            self.assertEqual(sum(r["status"]=="limit_reached" for r in results),7)
            original=next(r for r in results if r["status"]=="reserved")
            self.assertFalse(refund_failed_props(url,{**original,"token":uuid4()}))
            self.assertTrue(refund_failed_props(url,original))
            replacement=reserve_free_props(url)
            self.assertEqual(replacement["status"],"reserved")
            self.assertFalse(refund_failed_props(url,original))
            self.assertEqual(reserve_free_props(url)["status"],"limit_reached")

if __name__ == "__main__":
    unittest.main()
