"""Regression: first Streamlit render ALREADY contains home data.

This specifically covers the previously untested dropped-home_data event:
the initial iframe must never depend on a setComponentValue round trip.
"""
import unittest
from unittest.mock import patch
import bestbets_custom_screen as module

SAMPLE = {
    "games":[], "all_games":[], "ticker":[], "finals":[],
    "form":[], "players":[], "source":"test-only",
    "as_of":"test","fetched_at":"test","coverage":"fixture",
    "error":"Upstream unavailable (mock only)"
}


class InitialHomePayloadTest(unittest.TestCase):
    def test_initial_component_render_has_complete_home_snapshot(self):
        sent=[]
        session={}
        def component(**kwargs):
            sent.append(kwargs)
            return None
        with patch.object(module.st,"session_state",session),\
             patch.object(module.st,"markdown"),\
             patch.object(module,"_cached_brand",return_value=""),\
             patch.object(module,"_safe_centre_live",return_value=SAMPLE),\
             patch.object(module,"COMPONENT",side_effect=component):
            module.main()
        self.assertEqual(len(sent),1)
        home=sent[0]["payload"]["home"]
        self.assertEqual({k:home[k] for k in SAMPLE},SAMPLE)
        self.assertEqual(home.get("calendar_extras"),{})
        self.assertIsNone(home.get("calendar_requested_day"))
        self.assertEqual(session["bb10_centre_data"],SAMPLE)
        self.assertIn("bb10_centre_last_at",session)

    def test_centre_failures_have_visible_nonloading_state(self):
        with patch.object(module,"_cached_centre_live",side_effect=TimeoutError("network simulation")):
            status=module._safe_centre_live()
        self.assertIsInstance(status,dict)
        self.assertEqual(status["games"],[])
        self.assertEqual(status["players"],[])
        self.assertIn("Nie udało się",status["error"])

    def test_bad_source_shape_does_not_leave_spinner(self):
        with patch.object(module,"_cached_centre_live",return_value=None):
            result=module._safe_centre_live()
        self.assertIn("error",result)
        self.assertEqual(result["ticker"],[])


if __name__=="__main__":
    unittest.main()
