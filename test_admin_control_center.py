import unittest
from datetime import date, datetime, timedelta, timezone
from unittest.mock import Mock, patch
from admin_control_center import authorized, render, SECTIONS

class ControlCenterTest(unittest.TestCase):
    def test_roles(self):
        self.assertTrue(authorized("admin"))
        for role in ("guest", "free", "premium", "", None, "Admin"):
            self.assertFalse(authorized(role))

    def test_navigation(self):
        self.assertEqual(len(SECTIONS), 9)
        self.assertEqual(len(set(SECTIONS)), 9)

    def test_denial_before_data_access(self):
        for role in ("guest", "free", "premium"):
            fake_st = Mock()
            with patch.dict("sys.modules", {"streamlit": fake_st}), patch("access_control.current_role", return_value=role), patch("admin_data_intelligence.read_snapshot") as read:
                render()
                fake_st.error.assert_called_once()
                fake_st.stop.assert_called_once()
                read.assert_not_called()

class TrackerHistoryTest(unittest.TestCase):
    def test_admin_required_before_query(self):
        from admin_tracker_history import read_history
        with patch("access_control.current_role",return_value="free"),patch("admin_tracker_history._read") as read:
            self.assertEqual(read_history("url","2026-27","games",date(2026,11,20),date(2026,11,26)),{"status":"denied"})
            read.assert_not_called()

    def test_local_date_bounds_and_limit(self):
        from admin_tracker_history import read_history
        with patch("access_control.current_role",return_value="admin"),patch("admin_tracker_history._read",return_value={"status":"ok","rows":[]}) as read:
            self.assertEqual(read_history("url","2026-27","games",date(2026,11,20),date(2026,11,26))["status"],"ok")
            params=read.call_args.args[1][0][2]
            self.assertEqual(params[1],datetime(2026,11,19,23,tzinfo=timezone.utc))
            self.assertEqual(params[2],datetime(2026,11,26,23,tzinfo=timezone.utc))
            self.assertEqual(params[:3],params[3:])
            self.assertEqual(read_history("url","2026-27","games",date(2026,10,1),date(2026,11,26))["status"],"invalid_range")
            read.return_value={"status":"ok","rows":[{}]*5001}
            self.assertEqual(read_history("url","2026-27","players",date(2026,11,20),date(2026,11,26))["status"],"too_many")

    def test_classification_and_error(self):
        from admin_tracker_history import classify, summarize
        start=datetime(2026,11,25,1,tzinfo=timezone.utc)
        now=start+timedelta(hours=4)
        row={"start_utc":start,"issued":start-timedelta(hours=2),"settled":start+timedelta(hours=3),
             "pred_away":110,"pred_home":105,"actual_away":115,"actual_home":101}
        self.assertEqual(classify(row,"games",now=now),"settled")
        self.assertEqual(classify({**row,"issued":start-timedelta(minutes=14)},"games",now=now),"excluded")
        self.assertEqual(classify({**row,"settled":None},"games",now=now),"waiting")
        self.assertEqual(classify({**row,"settled":None},"games",now=start-timedelta(minutes=1)),"upcoming")
        self.assertEqual(classify({**row,"actual_away":None},"games",now=now),"excluded")
        data=summarize([row,{**row,"settled":None}],"games",now=now)
        self.assertEqual(data["settled"],1)
        self.assertEqual(data["waiting"],1)
        self.assertEqual(data["mae"],4.5)

if __name__ == "__main__":
    unittest.main()
