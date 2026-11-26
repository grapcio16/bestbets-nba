import unittest
from unittest.mock import patch, Mock
from usage_analytics_pilot import enabled, observe, observe_account, measured

class PilotTests(unittest.TestCase):
    def test_admin_only_and_disabled_by_default(self):
        with patch.dict("os.environ",{},clear=True),patch("access_control.current_role",return_value="admin"):
            self.assertFalse(enabled())
        with patch.dict("os.environ",{"HOOPZARO_USAGE_ENABLED":"true","HOOPZARO_USAGE_ADMIN_PILOT":"true","HOOPZARO_USAGE_DATABASE_URL":"test"},clear=True):
            for role in ("guest","free","premium","admin"):
                with patch("access_control.current_role",return_value=role):
                    self.assertEqual(enabled(),role=="admin")
    def test_disabled_preserves_results(self):
        with patch("usage_analytics_pilot.enabled",return_value=False),patch("usage_analytics_pilot.cursor") as cursor:
            observe({},"home")
            observe_account({},"issuer|subject")
            self.assertEqual(measured("props",lambda:42),42)
            cursor.assert_not_called()
    def test_allowed_page_and_throttle(self):
        state={}
        with patch("usage_analytics_pilot.enabled",return_value=True),patch.dict("os.environ",{"HOOPZARO_USAGE_DATABASE_URL":"test"}),patch("usage_analytics_pilot.cursor") as cursor,patch("usage_analytics_pilot.time.monotonic",side_effect=[100,101]):
            observe(state,"invalid")
            observe(state,"home")
            observe(state,"home")
            self.assertEqual(cursor.call_count,1)
            self.assertIn("hz_usage_session",state)
    def test_database_failure_does_not_break_feature(self):
        with patch("usage_analytics_pilot.enabled",return_value=True),patch.dict("os.environ",{"HOOPZARO_USAGE_DATABASE_URL":"test"}),patch("usage_analytics_pilot.cursor",side_effect=RuntimeError("test")):
            self.assertEqual(measured("props",lambda:42),42)
            with self.assertRaises(ValueError):
                measured("props",Mock(side_effect=ValueError("test")))
if __name__=="__main__":
    unittest.main()
