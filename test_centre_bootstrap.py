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

    def test_paid_player_props_never_cross_account_boundaries(self):
        for principal, entitled, role in [
            ("account-B", True, "premium"), ("guest", False, "guest")
        ]:
            with self.subTest(next_principal=principal):
                session={
                    "bb10_premium_principal":"account-A",
                    "bb10_identity_epoch":7,
                    "bb10_payload":{"player":{"name":"Private analysis for A"},"error":""},
                    "bb10_premium_game":{"private":"A"},
                    "bb10_premium_players":{"private":"A"},
                    "bb10_premium_player_averages":{"private":"A"},
                    "bb10_premium_team_analytics":{"private":"A"},
                    "bb10_admin_report":{"private":"A"},
                }
                sent=[]
                with patch.object(module.st,"session_state",session),\
                     patch.object(module.st,"markdown"),\
                     patch.object(module,"current_principal",return_value=principal),\
                     patch.object(module,"premium_entitled",return_value=entitled),\
                     patch.object(module,"current_role",return_value=role),\
                     patch.object(module,"auth_context",return_value={"role":role}),\
                     patch.object(module,"_cached_brand",return_value=""),\
                     patch.object(module,"_safe_centre_live",return_value=SAMPLE),\
                     patch.object(module,"COMPONENT",side_effect=lambda **kwargs: sent.append(kwargs)):
                    module.main()
                self.assertEqual(session["bb10_payload"],{"player":None,"error":""})
                self.assertEqual(session["bb10_identity_epoch"],8)
                self.assertEqual(session["bb10_premium_principal"],principal)
                self.assertEqual(sent[0]["payload"]["auth"]["session_epoch"],8)
                self.assertIsNone(sent[0]["payload"]["player"])
                self.assertIsNone(sent[0]["payload"]["premium_simulation"]["game"])
                self.assertIsNone(sent[0]["payload"]["premium_simulation"]["players"])
                self.assertIsNone(sent[0]["payload"]["premium_player_averages"])
                self.assertIsNone(sent[0]["payload"]["premium_team_analytics"])
                self.assertIsNone(sent[0]["payload"]["admin_report"])

    def test_entitlement_revocation_scrubs_props_even_without_account_change(self):
        session={
            "bb10_premium_principal":"account-A", "bb10_identity_epoch":3,
            "bb10_payload":{"player":{"name":"Former paid result"},"error":""},
        }
        sent=[]
        with patch.object(module.st,"session_state",session),\
             patch.object(module.st,"markdown"),\
             patch.object(module,"current_principal",return_value="account-A"),\
             patch.object(module,"premium_entitled",return_value=False),\
             patch.object(module,"current_role",return_value="free"),\
             patch.object(module,"auth_context",return_value={"role":"free"}),\
             patch.object(module,"_cached_brand",return_value=""),\
             patch.object(module,"_safe_centre_live",return_value=SAMPLE),\
             patch.object(module,"COMPONENT",side_effect=lambda **kwargs: sent.append(kwargs)):
            module.main()
        self.assertIsNone(sent[0]["payload"]["player"])
        self.assertIsNone(session["bb10_payload"]["player"])
        self.assertEqual(session["bb10_identity_epoch"],3)

    def test_premium_result_survives_an_unrelated_refresh_for_same_account(self):
        player={"name":"Current premium result"}
        session={
            "bb10_premium_principal":"account-A", "bb10_identity_epoch":3,
            "bb10_payload":{"player":player,"error":""},
        }
        sent=[]
        with patch.object(module.st,"session_state",session),\
             patch.object(module.st,"markdown"),\
             patch.object(module,"current_principal",return_value="account-A"),\
             patch.object(module,"premium_entitled",return_value=True),\
             patch.object(module,"current_role",return_value="premium"),\
             patch.object(module,"auth_context",return_value={"role":"premium"}),\
             patch.object(module,"_cached_brand",return_value=""),\
             patch.object(module,"_safe_centre_live",return_value=SAMPLE),\
             patch.object(module,"COMPONENT",side_effect=lambda **kwargs: sent.append(kwargs)):
            module.main()
        self.assertEqual(sent[0]["payload"]["player"],player)
        self.assertEqual(session["bb10_identity_epoch"],3)

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
