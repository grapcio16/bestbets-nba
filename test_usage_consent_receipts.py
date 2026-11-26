import os
import unittest
from unittest.mock import patch, MagicMock
from types import SimpleNamespace
from dataclasses import replace
from usage_consent_receipts import NOTICE_VERSION, create_receipt, notice_url
from usage_analytics_pilot import enabled, set_consent, refresh_consent, retry_close, observe_account

ENV={"HOOPZARO_USAGE_ENABLED":"true","HOOPZARO_USAGE_CUSTOMER_ENABLED":"true",
     "HOOPZARO_USAGE_DATABASE_URL":"fixture","HOOPZARO_USAGE_CONSENT_READY":"true",
     "HOOPZARO_USAGE_NOTICE_VERSION":NOTICE_VERSION,"HOOPZARO_USAGE_NOTICE_URL":"https://hoopzaro.com/privacy",
     "HOOPZARO_ACCOUNT_REGISTRY_ENABLED":"true","HOOPZARO_ACCOUNT_HMAC_KEY":"x"*32,
     "HOOPZARO_ACCOUNT_DATABASE_URL":"fixture"}
class ConsentTests(unittest.TestCase):
    def setUp(self):
        self.state={}
        self.env=self.enterContext(patch.dict(os.environ,ENV,clear=True))
        self.enterContext(patch.dict("sys.modules",{"streamlit":SimpleNamespace(session_state=self.state)}))
        self.role=self.enterContext(patch("access_control.current_role",return_value="free"))
        self.principal=self.enterContext(patch("access_control.current_principal",return_value="issuer|subject"))
        self.cursor=self.enterContext(patch("usage_analytics_pilot.cursor"))
    def accept(self):
        self.assertTrue(set_consent(self.state,True))
        self.assertTrue(enabled())
        return self.state["hz_consent_grant"]
    def test_committed_receipts_use_separate_identifiers(self):
        grant=self.accept()
        self.assertNotEqual(grant.session_id,grant.account_receipt_id)
        self.assertEqual(self.state["hz_usage_session"],grant.session_id)
        self.assertEqual(len(grant.account_id),64)
        calls=self.cursor.return_value.__enter__.return_value.execute.call_args_list
        self.assertEqual(len(calls),2)
        self.assertNotIn("issuer|subject",str(calls))
        self.assertNotIn(grant.session_id,str(calls[1]))
        self.assertNotIn(grant.account_id,str(calls[0]))
        self.assertFalse(set_consent(self.state,True))
        self.assertEqual(self.cursor.call_count,1)
    def test_commit_failure_denies_collection(self):
        self.cursor.return_value.__exit__.side_effect=RuntimeError("commit failure")
        self.assertTrue(set_consent(self.state,True))
        self.assertFalse(enabled())
        self.assertNotIn("hz_consent_grant",self.state)
        self.assertEqual(self.state["hz_consent_status"],"unavailable")
    def test_withdraw_failure_stops_immediately_and_retries(self):
        self.accept()
        self.state["hz_usage_pending"]={"games"}
        self.cursor.side_effect=RuntimeError("offline")
        self.assertTrue(set_consent(self.state,False))
        self.assertFalse(enabled())
        self.assertNotIn("hz_usage_pending",self.state)
        self.assertEqual(self.state["hz_consent_status"],"withdrawal_pending")
        self.assertTrue(set_consent(self.state,True))
        self.assertFalse(enabled())
        self.cursor.side_effect=None
        self.state["hz_consent_retry_after"]=0
        self.assertTrue(retry_close(self.state))
        self.assertFalse(enabled())
        self.assertNotIn("hz_consent_pending_close",self.state)
    def test_identity_change_expiration_and_role_change(self):
        self.accept()
        self.principal.return_value="issuer|other"
        self.assertFalse(enabled())
        refresh_consent(self.state,"issuer|other","free")
        self.assertNotIn("hz_consent_grant",self.state)
        grant=self.accept()
        self.state["hz_consent_grant"]=replace(grant,deadline=0)
        self.assertFalse(enabled())
        refresh_consent(self.state,"issuer|other","free")
        self.assertNotIn("hz_consent_grant",self.state)
        self.accept()
        self.role.return_value="premium"
        self.assertFalse(enabled())
        refresh_consent(self.state,"issuer|other","premium")
        self.assertNotIn("hz_consent_grant",self.state)
    def test_notice_required_and_change_invalidates(self):
        os.environ["HOOPZARO_USAGE_NOTICE_URL"]="https://elsewhere.test/privacy"
        self.assertEqual(notice_url(),"")
        self.assertTrue(set_consent(self.state,True))
        self.assertFalse(enabled())
        self.cursor.assert_not_called()
        os.environ["HOOPZARO_USAGE_NOTICE_URL"]=ENV["HOOPZARO_USAGE_NOTICE_URL"]
        self.accept()
        os.environ["HOOPZARO_USAGE_NOTICE_URL"]="https://hoopzaro.com/privacy/v3"
        self.assertFalse(enabled())
        refresh_consent(self.state,"issuer|subject","free")
        self.assertNotIn("hz_consent_grant",self.state)
    def test_guest_does_not_have_account_receipt(self):
        self.role.return_value="guest"
        self.principal.return_value="guest"
        grant=self.accept()
        self.assertIsNone(grant.account_receipt_id)
        self.assertIsNone(grant.account_id)
        self.assertEqual(self.cursor.return_value.__enter__.return_value.execute.call_count,1)
    def test_account_registry_requires_matching_proof(self):
        self.accept()
        self.cursor.reset_mock()
        observe_account(self.state,"issuer|different")
        self.cursor.assert_not_called()
    def test_admin_pilot_independent(self):
        self.role.return_value="admin"
        os.environ["HOOPZARO_USAGE_ADMIN_PILOT"]="true"
        os.environ["HOOPZARO_USAGE_CONSENT_READY"]="false"
        self.assertTrue(enabled())
        self.cursor.assert_not_called()

if __name__=="__main__":
    unittest.main()
