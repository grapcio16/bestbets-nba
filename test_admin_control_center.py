import unittest
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

if __name__ == "__main__":
    unittest.main()
