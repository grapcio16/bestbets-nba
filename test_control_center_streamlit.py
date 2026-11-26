"""Streamlit server-render smoke test, with deterministic fixture data.

No external requests, credentials, or production database connection.
This tests the widget tree, not visual pixel fidelity or real OIDC login.
"""
import unittest
from datetime import datetime, timezone, timedelta
from contextlib import ExitStack
from unittest.mock import patch, Mock
from types import ModuleType
from streamlit.testing.v1 import AppTest
from v8_shadow.evaluation import evaluate_records
from admin_control_center import SECTIONS, SECTION_LABELS
from admin_dashboard_ui import grid_markup, metric_markup, health_markup, table_markup, bars_markup, model_name

def fixture_tracker_history():
    now = datetime.now(timezone.utc)
    start = now - timedelta(days=1)
    return {"status":"ok","rows":[{"game_id":"12345","model_id":"auto_context_full_v75",
        "start_utc":start,"issued":start-timedelta(hours=2),"settled":start+timedelta(hours=3),
        "away":"BOS","home":"NYK","pred_away":110.0,"pred_home":105.0,
        "actual_away":115,"actual_home":101,"home_win_pct":40.0,
        "player_id":"1","player_name":"Test Player","team":"BOS","pts_pred":20.0,"pts_actual":24.0,
        "quarter":1}]}


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
                "admin_live_data.tracker_summary":{"status":"ok","players":[{"model_id":"auto_player_form_v74","settled":12,"pts_mae":4.8}],"quarters":[{"model_id":"auto_q_v72_shadow_v1","settled":8,"team_points_mae":5.1}],"last_run":[]},
                "admin_tracker_history.read_history":fixture_tracker_history(),
                "admin_live_data.account_summary":{"status":"ok","accounts":[{"observed_accounts":4,"seen_last_24_hours":1,"seen_last_7_days":2,"seen_last_30_days":2,"first_seen_last_7_days":1}],"quota":[{"reservations_today":1}]},
                "admin_live_data.usage_summary":{"status":"ok","sessions":[{"recent_sessions":2,"new_sessions_24h":2,"active_sessions_24h":2,"active_sessions_7d":2}],"daily":[{"day":datetime.now(timezone.utc).date(),"sessions":2}],"pages":[{"page":"home","sessions":2}],"features":[{"feature":"props","calls":4,"failures":0,"avg_ms":1200}]},
                "admin_live_data.stripe_test_summary":{"status":"ok","subscription_counts":{"active":2}},
                "admin_stripe_payments.stripe_payment_summary":{"status":"ok","mode":"test","currencies":{"usd":{"captured_minor":999,"refunded_minor":0,"successful":1,"failed":0,"other":0}}},
                "admin_live_data.official_injury_freshness":{"status":"no_recent_report"},
                "admin_revenue.revenue_snapshot":{"status":"ok","checkout_mode":"test","fulfillment_declared_ready":False},
            }
            stack.enter_context(patch.dict("os.environ",{},clear=True))
            for name,value in fixtures.items():
                stack.enter_context(patch(name,return_value=value))
            app=self.app().run()
            for section in SECTIONS:
                with self.subTest(section=section):
                    next(b for b in app.sidebar.button if b.key=="hz_nav_"+section).click().run()
                    self.assertFalse(app.exception)
                    self.assertEqual(app.title[0].value,SECTION_LABELS[section])
                    self.assertFalse(app.caption)
                    if section == "AI Engines":
                        self.assertEqual(len(app.expander),1)
                        self.assertTrue(any("hz-bar-panel" in m.value for m in app.markdown))
                        self.assertTrue(any("Wspólna próba: 1 meczów" in m.value for m in app.markdown))
                    if section=="Revenue":
                        self.assertTrue(any("Aktywne subskrypcje testowe" in m.value and "Udane płatności testowe" in m.value for m in app.markdown))
                        self.assertTrue(any("9.99 USD" in m.value for m in app.markdown))
                        self.assertTrue(any('hz-kpi-label">Przychód miesięczny</div><div><div class="hz-kpi-value">$999.00</div>' in m.value for m in app.markdown))
                    if section=="Tracker":
                        self.assertTrue(any("hz-match-score" in m.value and "115 : 101" in m.value for m in app.markdown))
                        self.assertTrue(any("hz-status-settled" in m.value for m in app.markdown))
                        self.assertFalse(any("Wspólna próba:" in m.value for m in app.markdown))
                        app.button(key="hz_tracker_tab_players").click().run()
                        self.assertFalse(app.exception)
                        self.assertTrue(any("Test Player" in m.value for m in app.markdown))
                        app.button(key="hz_tracker_tab_quarters").click().run()
                        self.assertFalse(app.exception)
                        self.assertTrue(any("Q1" in m.value and "hz-status-settled" in m.value for m in app.markdown))
                        day=app.date_input(key="hz_tracker_day").value
                        app.button(key="hz_tracker_prev").click().run()
                        self.assertFalse(app.exception)
                        self.assertEqual(app.date_input(key="hz_tracker_day").value,day-timedelta(days=1))
                    if section=="Overview":
                        self.assertTrue(any('hz-kpi-label">Aktywne konta · 24 godz.</div><div><div class="hz-kpi-value">1</div>' in m.value for m in app.markdown))
                        self.assertTrue(any("PILOT ADMIN" in m.value for m in app.markdown))
                        self.assertTrue(any("Udane płatności testowe" in m.value for m in app.markdown))
                        self.assertTrue(any("hz-over-fill" in m.value and "sesji" in m.value for m in app.markdown))
                        self.assertTrue(any("Player Props" in m.value and "1,20" in m.value for m in app.markdown))
                        self.assertFalse(any("Archiwum V8" in m.value for m in app.markdown))
                        app.radio(key="hz_over_period").set_value(30).run()
                        self.assertFalse(app.exception)
                        app.button(key="hz_over_users").click().run()
                        self.assertFalse(app.exception)
                        self.assertEqual(app.title[0].value,"Użytkownicy")
                    if section=="Users":
                        self.assertTrue(any('hz-kpi-label">Zaobserwowane konta</div><div><div class="hz-kpi-value">4</div>' in m.value for m in app.markdown))
                    if section=="Performance":
                        self.assertTrue(any('hz-kpi-label">Połączenie</div><div><div class="hz-kpi-value">20.0 ms</div>' in m.value for m in app.markdown))
            next(b for b in app.sidebar.button if b.label=="Odśwież dane").click().run()
            self.assertFalse(app.exception)

    def test_overview_missing_vs_zero_and_escaped_labels(self):
        from admin_overview import aggregate, daily_chart, page_chart
        from datetime import date
        data=aggregate({"status":"ok","accounts":[]},{"status":"ok","sessions":[{"recent_sessions":0}],"features":[]})
        self.assertEqual(data,{"accounts":0,"active_accounts":0,"sessions":0,"calls":0,"failures":0})
        self.assertTrue(all(v is None for v in aggregate({"status":"unavailable"},{"status":"unavailable"}).values()))
        chart=daily_chart({"status":"ok","daily":[{"day":"2026-11-20","sessions":3},{"day":"2026-11-01","sessions":50}]},7,date(2026,11,26))
        self.assertIn("20.11",chart)
        self.assertNotIn("01.11",chart)
        self.assertIn("&lt;script&gt;",page_chart({"status":"ok","pages":[{"page":"<script>","sessions":1}]}))

    def test_dashboard_markup_escaping_and_missing_values(self):
        markup = grid_markup([("Konta", 0), ("<script>", "Brak danych", '"onclick="bad')], 4)
        self.assertIn('hz-kpi-value">0</div>', markup)
        self.assertIn('hz-kpi-value">—</div>', markup)
        self.assertNotIn("<script>", markup)
        self.assertIn("&quot;onclick=&quot;bad", markup)
        self.assertIn("is-empty", markup)
        self.assertIn("&lt;script&gt;", health_markup("<script>", "OK", "ok"))

    def test_readable_tables_and_charts(self):
        self.assertEqual(model_name("auto_context_full_v75"),"V7.5")
        self.assertIn("&lt;script&gt;",table_markup([{"Model":"<script>"}]))
        self.assertNotIn("<script>",bars_markup([("<script>",4.2)]))
        self.assertIn("4,20",bars_markup([("V7.5",4.2)]))
        self.assertEqual(bars_markup([("V7.5",None)]),"")

    def test_common_sample_is_real_intersection(self):
        base = {"issued_at":"2026-11-24T17:00:00Z","start_utc":"2026-11-25T00:00:00Z",
                "settled_at":"2026-11-25T04:00:00Z","home":"BOS","away":"NYK",
                "actual_home":113,"actual_away":105,"mean_home":111,"mean_away":107,"home_win_pct":65}
        rows=[{**base,"model_id":model,"game_id":gid} for model,ids in
              [("a",["1","2"]),("b",["1","3"]),("c",["2","3"])] for gid in ids]
        report=evaluate_records(rows,[])
        self.assertEqual(report["shared_cohort"]["n"],0)
        self.assertEqual(report["shared_cohort"]["metrics"],{})
        self.assertEqual(len(report["common_game_comparisons"]),3)

    def test_tracker_consensus_and_safe_hero(self):
        from admin_tracker_view import consensus, match_hero, compact_rows
        row=fixture_tracker_history()["rows"][0]
        self.assertEqual(consensus([row],"games"),((115.0,101.0),"settled"))
        self.assertEqual(consensus([row,{**row,"actual_home":99}],"games"),(None,"conflict"))
        self.assertEqual(consensus([{**row,"settled":None}],"games"),(None,"waiting"))
        self.assertIn("&lt;script&gt;",match_hero("<script>","NYK",(115,101),"settled"))
        result=compact_rows([row],"games","PTS",datetime.now(timezone.utc))[0]
        self.assertEqual(result["Trafienie"],"Tak")
        self.assertEqual(result["Błąd na drużynę"],"4,50")

    def test_all_non_admin_roles(self):
        for role in ("guest","free","premium"):
            with self.subTest(role=role), patch("access_control.current_role",return_value=role), patch("admin_data_intelligence.read_snapshot") as read:
                app=self.app().run()
                self.assertFalse(app.exception)
                self.assertEqual(app.error[0].value,"Brak dostępu.")
                self.assertFalse(app.sidebar.button)
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
