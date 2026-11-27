import unittest
from unittest.mock import patch, Mock, MagicMock
from usage_analytics_pilot import enabled, observe, observe_account, measured, set_consent, CONSENT_VERSION

class PilotTests(unittest.TestCase):
    def test_admin_only_and_disabled_by_default(self):
        with patch.dict("os.environ",{},clear=True),patch("access_control.current_role",return_value="admin"):
            self.assertFalse(enabled())
        with patch.dict("os.environ",{"HOOPZARO_USAGE_ENABLED":"true","HOOPZARO_USAGE_ADMIN_PILOT":"true","HOOPZARO_USAGE_DATABASE_URL":"test"},clear=True):
            for role in ("guest","free","premium","admin"):
                with patch("access_control.current_role",return_value=role):
                    self.assertEqual(enabled(),role=="admin")
    def test_customer_flag_and_session_consent(self):
        from types import SimpleNamespace
        env={"HOOPZARO_USAGE_ENABLED":"true","HOOPZARO_USAGE_CUSTOMER_ENABLED":"true","HOOPZARO_USAGE_DATABASE_URL":"test",
             "HOOPZARO_USAGE_CONSENT_READY":"true","HOOPZARO_USAGE_NOTICE_VERSION":CONSENT_VERSION,
             "HOOPZARO_USAGE_NOTICE_URL":"https://hoopzaro.com/privacy"}
        state={}
        with patch.dict("os.environ",env,clear=True),patch.dict("sys.modules",{"streamlit":SimpleNamespace(session_state=state)}),patch("access_control.current_role",return_value="free"),patch("access_control.current_principal",return_value="issuer|subject"),patch("usage_analytics_pilot.cursor") as cursor:
            self.assertFalse(enabled())
            self.assertFalse(set_consent(state,"true"))
            self.assertTrue(set_consent(state,True))
            self.assertEqual(state["hz_consent_grant"].notice_version,CONSENT_VERSION)
            self.assertTrue(enabled())
            self.assertEqual(state["hz_usage_session"],state["hz_consent_grant"].session_id)
            state["hz_usage_pending"]={"games"}
            self.assertTrue(set_consent(state,False))
            self.assertFalse(enabled())
            self.assertNotIn("hz_usage_session",state)
            self.assertNotIn("hz_usage_pending",state)
            self.assertNotIn("hz_consent_grant",state)
            self.assertEqual(cursor.call_count,2)
    def test_role_and_idle_gap_bound(self):
        state={"hz_usage_session":"old","hz_usage_role":"free","hz_usage_last":100}
        with patch("usage_analytics_pilot.enabled",return_value=True),patch("access_control.current_role",return_value="premium"),patch.dict("os.environ",{"HOOPZARO_USAGE_DATABASE_URL":"test"}),patch("usage_analytics_pilot.cursor") as cursor,patch("usage_analytics_pilot.time.monotonic",side_effect=[500,1000]):
            observe(state,"home")
            self.assertNotEqual(state["hz_usage_session"],"old")
            execute=cursor.return_value.__enter__.return_value.execute
            self.assertEqual(execute.call_args_list[0].args[1][1:],("premium",0))
            observe(state,"props")
            self.assertEqual(execute.call_args_list[2].args[1][1:],("premium",0))
    def test_guest_account_not_written(self):
        with patch("usage_analytics_pilot.enabled",return_value=True),patch("access_control.current_role",return_value="guest"),patch.dict("os.environ",{"HOOPZARO_ACCOUNT_REGISTRY_ENABLED":"true","HOOPZARO_ACCOUNT_HMAC_KEY":"x"*32,"HOOPZARO_ACCOUNT_DATABASE_URL":"test"}),patch("usage_analytics_pilot.cursor") as cursor:
            observe_account({},"issuer|subject")
            cursor.assert_not_called()
    def test_retention_dry_run_and_database_guard(self):
        from analytics_retention import run
        conn=MagicMock()
        cur=conn.cursor.return_value.__enter__.return_value
        cur.fetchone.side_effect=[("hoopzaro_analytics",),(0,),(1,),(2,),(3,)]
        self.assertEqual(run(conn),{"page_samples":0,"sessions":1,"feature_aggregates":2,"inactive_accounts":3})
        statements=[call.args[0] for call in cur.execute.call_args_list]
        self.assertFalse(any(s.startswith("DELETE") for s in statements))
        self.assertIn("NOT EXISTS",statements[-1])
        cur.reset_mock()
        cur.fetchone.side_effect=[("neondb",)]
        with self.assertRaises(RuntimeError):
            run(conn,apply=True)
        self.assertEqual(cur.execute.call_count,1)
    def test_retention_apply_calls_fixed_function_only(self):
        from analytics_retention import run
        conn=MagicMock()
        cur=conn.cursor.return_value.__enter__.return_value
        counts={"page_samples":1,"sessions":2,"feature_aggregates":3,"inactive_accounts":4}
        cur.fetchone.side_effect=[("hoopzaro_analytics",),(counts,)]
        self.assertEqual(run(conn,apply=True),counts)
        statements=[call.args[0] for call in cur.execute.call_args_list]
        self.assertEqual(statements[-1],"SELECT hz_retention.cleanup()")
        self.assertFalse(any(s.startswith("DELETE") for s in statements))
        cur.fetchone.side_effect=[("hoopzaro_analytics",),({"page_samples":5001},)]
        with self.assertRaises(RuntimeError):
            run(conn,apply=True)
    def test_disabled_preserves_results(self):
        with patch("usage_analytics_pilot.enabled",return_value=False),patch("usage_analytics_pilot.cursor") as cursor:
            observe({},"home")
            observe_account({},"issuer|subject")
            self.assertEqual(measured("props",lambda:42),42)
            cursor.assert_not_called()
    def test_allowed_page_and_throttle(self):
        state={}
        with patch("usage_analytics_pilot.enabled",return_value=True),patch("access_control.current_role",return_value="admin"),patch.dict("os.environ",{"HOOPZARO_USAGE_DATABASE_URL":"test"}),patch("usage_analytics_pilot.cursor") as cursor,patch("usage_analytics_pilot.time.monotonic",side_effect=[100,101]):
            observe(state,"invalid")
            observe(state,"home")
            observe(state,"home")
            self.assertEqual(cursor.call_count,1)
            self.assertIn("hz_usage_session",state)
    def test_batch_keeps_short_visits_across_throttle(self):
        state={}
        with patch("usage_analytics_pilot.enabled",return_value=True),patch("access_control.current_role",return_value="free"),patch.dict("os.environ",{"HOOPZARO_USAGE_DATABASE_URL":"test"}),patch("usage_analytics_pilot.cursor") as cursor,patch("usage_analytics_pilot.time.monotonic",side_effect=[100,101,131]):
            observe(state,"home")
            observe(state,"games",["teams","games",{},"invalid"])
            self.assertEqual(cursor.call_count,1)
            self.assertEqual(state["hz_usage_pending"],{"games","teams"})
            observe(state,"settings",["players","settings"])
            self.assertEqual(cursor.call_count,2)
            execute=cursor.return_value.__enter__.return_value.execute
            self.assertEqual(execute.call_args.args[1][1],["games","players","settings","teams"])
            self.assertEqual(state["hz_usage_pending"],set())
    def test_database_failure_does_not_break_feature(self):
        with patch("usage_analytics_pilot.enabled",return_value=True),patch.dict("os.environ",{"HOOPZARO_USAGE_DATABASE_URL":"test"}),patch("usage_analytics_pilot.cursor",side_effect=RuntimeError("test")):
            self.assertEqual(measured("props",lambda:42),42)
            with self.assertRaises(ValueError):
                measured("props",Mock(side_effect=ValueError("test")))
if __name__=="__main__":
    unittest.main()
