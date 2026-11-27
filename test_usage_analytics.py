import unittest
from unittest.mock import patch, Mock
from usage_analytics import observe, measured, record

class UsageAnalyticsTest(unittest.TestCase):
    def test_disabled_no_connection(self):
        with patch("usage_analytics.enabled",return_value=False), patch("usage_analytics._connect") as connect:
            observe({}, "home", "guest")
            record("props","success",12)
            connect.assert_not_called()

    def test_sampling_throttle_and_allowlist(self):
        state={}
        with patch("usage_analytics.enabled",return_value=True), patch("usage_analytics._connect") as connect, patch("usage_analytics.time.monotonic",side_effect=[100,101,150]):
            observe(state,"unknown","guest")
            observe(state,"home","guest")
            observe(state,"home","guest")
            observe(state,"props","guest")
            self.assertEqual(connect.call_count,2)
            self.assertEqual(state["hz_usage_page"],"props")
            self.assertNotIn("email",str(state))

    def test_measured_preserves_return_and_exception(self):
        with patch("usage_analytics.record") as log:
            self.assertEqual(measured("props",lambda: {"value":1}),{"value":1})
            self.assertEqual(log.call_args.args[:2],("props","success"))
            self.assertEqual(measured("simulation",lambda: {"error":"unavailable"}),{"error":"unavailable"})
            self.assertEqual(log.call_args.args[:2],("simulation","failure"))
            with self.assertRaises(ValueError):
                measured("props",Mock(side_effect=ValueError("test")))
            self.assertEqual(log.call_args.args[:2],("props","failure"))

    def test_admin_aggregate_denies_other_roles(self):
        from admin_live_data import usage_summary
        with patch("access_control.current_role",return_value="free"),patch("admin_live_data._read") as read:
            self.assertEqual(usage_summary(),{"status":"denied"})
            read.assert_not_called()

if __name__=="__main__":
    unittest.main()
