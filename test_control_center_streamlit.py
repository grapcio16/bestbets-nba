"""Streamlit server-render smoke test, with deterministic fixture data.

No external requests, credentials, or production database connection.
This tests the widget tree, not visual pixel fidelity or real OIDC login.
"""
import unittest
from contextlib import ExitStack
from unittest.mock import patch, Mock
from types import ModuleType
from streamlit.testing.v1 import AppTest
from v8_shadow.evaluation import evaluate_records
from admin_control_center import SECTIONS, SECTION_LABELS

def fixture_report():
    base = {"game_id":"12345","issued_at":"2026-11-24T17:00:00Z",
            "start_utc":"2026-11-25T00:00:00Z","settled_at":"2026-11-25T04:00:00Z",
            "home":"BOS","away":"NYK","actual_home":113,"actual_away":105,
            "mean_home":111,"mean_away":107,"home_win_pct":65,
            "scenario_home":112,"scenario_away":108,"training_examples":100,
            "report":{"total_p10_p50_p90":[200,218,235]}}
    return evaluate_records([{**base,"model_id":"fixture_v81"},
                             {**base,"model_id":"fixture_v82","mean_home":114}],[])

class ControlCenterSmokeTest(unittest.TestCase):
    def app(self):
        return AppTest.from_string("from admin_control_center import render\nrender()",default_timeout=15)

    def test_all_sections_and_interactions(self):
        with ExitStack() as stack:
            fixtures = {
                "access_control.current_role":"admin",
                "access_control.auth_configured":True,
                "access_control._secret_section":{},
                "tracker_storage.tracker_database_url":"",
                "admin_data_intelligence.read_snapshot":{"status":"recent_evidence","worker":{
                    "observed_games":100,"trainable_examples":90,"minimum_examples":80,
                    "rejected_boxscores":0,"newly_ingested_boxscores":2,
                    "run_utc":"2026-11-25T04:00:00+00:00"},"models":[{"model_id":"fixture_v81","archived":1,"settled":1}]},
                "admin_data_intelligence.read_scorecard":fixture_report(),
                "admin_source_monitor.source_snapshot":[{"source":"fixture","status":"schema_ok","elapsed_ms":42}],
                "admin_performance.database_probe":{"status":"ok","connect_ms":20,"query_ms":2,"total_ms":25,"checked_utc":"2026-11-25T04:00:00+00:00"},
                "admin_security.read_recent_events":{"status":"setup_required"},
                "admin_live_data.tracker_summary":{"status":"ok","players":[{"settled":12}],"quarters":[{"settled":8}],"last_run":[]},
                "admin_live_data.account_summary":{"status":"ok","accounts":[{"observed_accounts":4,"seen_last_24_hours":1,"seen_last_7_days":2,"seen_last_30_days":2,"first_seen_last_7_days":1}],"quota":[{"reservations_today":1}]},
                "admin_live_data.stripe_test_summary":{"status":"ok","subscription_counts":{"active":2}},
                "admin_live_data.official_injury_freshness":{"status":"no_recent_report"},
                "admin_revenue.revenue_snapshot":{"status":"ok","checkout_mode":"test","fulfillment_declared_ready":False},
            }
            stack.enter_context(patch.dict("os.environ",{},clear=True))
            for name,value in fixtures.items():
                stack.enter_context(patch(name,return_value=value))
            app=self.app().run()
            for section in SECTIONS:
                with self.subTest(section=section):
                    app.sidebar.radio[0].set_value(section).run()
                    self.assertFalse(app.exception)
                    self.assertEqual(app.title[0].value,SECTION_LABELS[section])
                    self.assertFalse(app.caption)
                    if section in ("AI Engines","Tracker"):
                        self.assertTrue(app.expander)
                    if section=="Revenue":
                        self.assertEqual(next(m.value for m in app.metric if m.label=="Przychód miesięczny"),"$999.00")
                    if section=="Tracker":
                        self.assertEqual(next(m.value for m in app.metric if m.label=="Rozliczone prognozy zawodników"),"12")
                    if section=="Overview":
                        self.assertEqual(next(m.value for m in app.metric if m.label=="Aktywni · 24 godz."),"1")
                    if section=="Users":
                        self.assertEqual(next(m.value for m in app.metric if m.label=="Zaobserwowane konta"),"4")
                    if section=="Performance":
                        self.assertEqual(next(m.value for m in app.metric if m.label=="Połączenie"),"20.0 ms")
            app.sidebar.button[0].click().run()
            self.assertFalse(app.exception)

    def test_all_non_admin_roles(self):
        for role in ("guest","free","premium"):
            with self.subTest(role=role), patch("access_control.current_role",return_value=role), patch("admin_data_intelligence.read_snapshot") as read:
                app=self.app().run()
                self.assertFalse(app.exception)
                self.assertEqual(app.error[0].value,"Brak dostępu.")
                self.assertFalse(app.sidebar.radio)
                read.assert_not_called()

    def test_dedicated_deployment_never_loads_public_frontend(self):
        public = ModuleType("bestbets_custom_screen")
        public.main = Mock()
        settings = {"redirect_uri":"https://hoopzaro-control-center.streamlit.app/oauth2callback"}
        for role in ("guest", "free", "premium", "admin"):
            with self.subTest(role=role), ExitStack() as stack:
                stack.enter_context(patch.dict("sys.modules", {"bestbets_custom_screen":public}))
                stack.enter_context(patch("access_control._secret_section",return_value=settings))
                stack.enter_context(patch("access_control.current_role",return_value=role))
                stack.enter_context(patch("access_control.auth_configured",return_value=True))
                render = stack.enter_context(patch("admin_control_center.render"))
                app = AppTest.from_file("app.py",default_timeout=15).run()
                self.assertFalse(app.exception)
                public.main.assert_not_called()
                if role == "admin":
                    render.assert_called_once_with(dedicated=True)
                else:
                    render.assert_not_called()
                    self.assertEqual(app.title[0].value,"HOOPZARO | Control Center")
                    self.assertEqual(app.button[0].label,"Zaloguj się" if role=="guest" else "Wyloguj się")

    def test_standalone_entrypoint_and_explicit_deployment_mode(self):
        for entry in ("control_center_app.py", "app.py"):
            with self.subTest(entry=entry), ExitStack() as stack:
                stack.enter_context(patch.dict("os.environ", {"HOOPZARO_DEPLOYMENT_MODE":"control_center"}))
                stack.enter_context(patch("access_control._secret_section",return_value={}))
                stack.enter_context(patch("access_control.current_role",return_value="guest"))
                stack.enter_context(patch("access_control.auth_configured",return_value=True))
                render = stack.enter_context(patch("admin_control_center.render"))
                public = ModuleType("bestbets_custom_screen")
                public.main = Mock()
                stack.enter_context(patch.dict("sys.modules", {"bestbets_custom_screen":public}))
                app = AppTest.from_file(entry,default_timeout=15).run()
                self.assertFalse(app.exception)
                self.assertEqual(app.title[0].value,"HOOPZARO | Control Center")
                public.main.assert_not_called()
                render.assert_not_called()

    def test_hostname_routes_to_private_login_without_granting_access(self):
        with ExitStack() as stack:
            stack.enter_context(patch("access_control._secret_section",return_value={}))
            stack.enter_context(patch("access_control.current_role",return_value="guest"))
            stack.enter_context(patch("access_control.auth_configured",return_value=True))
            stack.enter_context(patch("streamlit.context",Mock(url="https://hoopzaro-control-center.streamlit.app/")))
            render = stack.enter_context(patch("admin_control_center.render"))
            app = AppTest.from_file("app.py",default_timeout=15).run()
            self.assertFalse(app.exception)
            self.assertEqual(app.title[0].value,"HOOPZARO | Control Center")
            render.assert_not_called()

    def test_public_deployment_default_unchanged(self):
        public = ModuleType("bestbets_custom_screen")
        public.main = Mock()
        with patch.dict("sys.modules",{"bestbets_custom_screen":public}), patch(
            "access_control._secret_section",return_value={"redirect_uri":"https://hoopzaro.streamlit.app/oauth2callback"}
        ), patch("admin_control_center.render") as render:
            app = AppTest.from_file("app.py",default_timeout=15).run()
            self.assertFalse(app.exception)
            public.main.assert_called_once()
            render.assert_not_called()

if __name__ == "__main__":
    unittest.main()
