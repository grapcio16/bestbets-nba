"""Private Hoopzaro Control Center; opt-in audit only, no production setting mutations."""
from __future__ import annotations

SECTIONS = (
    "Overview", "Data Center", "AI Engines", "Tracker", "Users",
    "Revenue", "Performance", "Security", "Settings",
)

def authorized(role: str) -> bool:
    return role == "admin"

def render(*, dedicated=False):
    import streamlit as st
    from access_control import current_role
    # Never rely on URL, browser state or premium entitlement for authorization.
    if not authorized(current_role()):
        st.error("Access denied.")
        st.stop()
        return
    from admin_data_intelligence import read_snapshot, read_scorecard
    from tracker_storage import tracker_database_url
    from admin_source_monitor import source_snapshot
    from admin_performance import database_probe, summarize_sources
    from admin_live_data import tracker_summary, account_summary, stripe_test_summary, official_injury_freshness
    from admin_security import audit_enabled, record_admin_event
    from account_registry import registry_enabled, free_props_enabled

    @st.cache_data(ttl=120, show_spinner=False)
    def snapshot(season):
        return read_snapshot(tracker_database_url(), season)

    @st.cache_data(ttl=300, show_spinner=False)
    def scorecard(season):
        return read_scorecard(tracker_database_url(), season)

    @st.cache_data(ttl=300, show_spinner=False)
    def sources():
        return source_snapshot()

    @st.cache_data(ttl=300, show_spinner=False)
    def database_health():
        return database_probe(tracker_database_url())

    @st.cache_data(ttl=180, show_spinner=False)
    def tracker_metrics(season):
        return tracker_summary(tracker_database_url(), season)

    @st.cache_data(ttl=300, show_spinner=False)
    def accounts():
        return account_summary()

    @st.cache_data(ttl=300, show_spinner=False)
    def stripe_test():
        return stripe_test_summary()

    @st.cache_data(ttl=300, show_spinner=False)
    def injury_index():
        return official_injury_freshness()

    st.markdown("""<style>
    .stApp { background: radial-gradient(ellipse at 80% 0%, #21143c 0%, #080d1c 45%); color: #edf0ff; }
    [data-testid="stMainBlockContainer"] { max-width: 1440px; padding-top: 2rem; }
    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] h1 { color: #c4b5fd; letter-spacing: .08em; }
    [data-testid="stMetric"] { box-shadow: 0 0 18px #8b5cf618; }
    [data-testid="stMetricLabel"], [data-testid="stMetricLabel"] p { color:#aebbd7 !important; }
    [data-testid="stSidebar"] p, [data-testid="stSidebar"] label { color:#e8e7ff; }
    [data-testid="stSidebar"] [data-testid="stRadio"] label { padding:6px 4px; border-radius:8px; }
    [data-testid="stSidebar"] [data-testid="stRadio"] label:has(input:checked) { background:#33245d; }
    [data-testid="stMainBlockContainer"] h1,[data-testid="stMainBlockContainer"] h2,[data-testid="stMainBlockContainer"] h3 { color:#eef0ff; }
    [data-testid="stMainBlockContainer"] [data-testid="stCaptionContainer"] { color:#a6b1cc; }
    [data-testid="stDataFrame"] { border-radius: 10px; overflow: hidden; }
    @media(max-width: 700px) { [data-testid="stMainBlockContainer"] { padding: 1.2rem; } }
    [data-testid="stMetric"] { border: 1px solid #343052; border-radius: 14px;
        padding: 16px; background: #11192e; }
    [data-testid="stMetricValue"] { color: #b69aff; }
    [data-testid="stSidebar"] { background: #101528; }
    </style>""", unsafe_allow_html=True)
    st.sidebar.title("HOOPZARO")
    st.sidebar.caption("CONTROL CENTER · ADMIN")
    section = st.sidebar.radio("Navigation", SECTIONS)
    if not dedicated:
        st.sidebar.markdown("[Return to Hoopzaro](?)")
    st.caption("HOOPZARO / CONTROL CENTER / " + section.upper())
    st.title(section)
    st.caption("Internal administration · NBA 2026–27 · production controls locked")
    if st.sidebar.button("Refresh telemetry"):
        snapshot.clear()
        scorecard.clear()
        sources.clear()
        database_health.clear()
        tracker_metrics.clear()
        accounts.clear()
        stripe_test.clear()
        injury_index.clear()
        if audit_enabled() and not record_admin_event("refresh_telemetry", "success"):
            st.warning("Telemetry cache cleared; audit record could not be saved.")
    if dedicated and st.sidebar.button("Sign out"):
        st.logout()
        st.stop()
        return
    st.divider()
    if section == "Overview":
        st.subheader("Application usage")
        registry = accounts()
        fields = (("Observed accounts", "observed_accounts"),
                  ("Active last 24 hours", "seen_last_24_hours"),
                  ("Active last 7 days", "seen_last_7_days"),
                  ("Active last 30 days", "seen_last_30_days"),
                  ("First seen last 7 days", "first_seen_last_7_days"))
        rows = registry.get("accounts", [])
        available = registry.get("status") == "ok"
        cols = st.columns(3)
        for i, (label, key) in enumerate(fields):
            if i == 3:
                cols = st.columns(3)
            value = sum(r[key] for r in rows) if available and all(key in r for r in rows) else "Unavailable"
            cols[i % 3].metric(label, value)
        cols[2].metric("Free Props reservations today (UTC)",
                       registry["quota"][0]["reservations_today"] if available else "Unavailable")
        if not available:
            st.info("Account registry not connected or unavailable.")
        st.caption("Observed signed-in accounts, including admins. Activity uses last recorded account observation; anonymous visits and live concurrent users are not measured.")
        cols = st.columns(2)
        cols[0].metric("Actual revenue", "Not connected")
        cols[1].metric("Active paid subscriptions", "Not connected")
        st.caption("Live billing is not connected; test subscriptions are separate.")
        st.divider()
    if section in ("Overview", "Data Center", "AI Engines", "Tracker"):
        data = snapshot("2026-27")
        worker = data.get("worker") or {}
        models = data.get("models") or []
        st.write("V8 telemetry:", data.get("status", "unavailable"))
        if section in ("Overview", "Data Center"):
            cols = st.columns(3)
            for col, name, field in zip(cols, ("Observed games", "Training examples", "Rejected boxscores"),
                                      ("observed_games", "trainable_examples", "rejected_boxscores")):
                col.metric(name, worker.get(field, "Unavailable"))
            if worker.get("run_utc"):
                st.caption("Last recorded worker activity (UTC): " + worker["run_utc"])
            if section == "Data Center":
                st.write("Minimum training examples:", worker.get("minimum_examples", "Unavailable"))
                st.write("Newly ingested boxscores:", worker.get("newly_ingested_boxscores", "Unavailable"))
                st.subheader("Source availability · point-in-time")
                st.caption("Direct endpoint checks, not end-to-end production health. Cached for 5 minutes.")
                results = sources()
                st.dataframe(results, hide_index=True, use_container_width=True)
                issues = [r["source"] for r in results if r["status"] not in ("schema_ok", "empty_response")]
                if issues:
                    st.warning("Source checks requiring review: " + ", ".join(issues))
                if any(r["status"] == "empty_response" for r in results):
                    st.info("An empty list may be legitimate; it does not prove full coverage or healthy rosters.")
                st.caption("checked_utc records retrieval time, not report publication. Latency includes parsing.")
                st.subheader("Official NBA injury report · publication index")
                injury = injury_index()
                st.write("Report index:", injury.get("status", "unavailable"))
                if injury.get("published_utc"):
                    st.caption("Publication UTC: " + injury["published_utc"])
                st.caption("A recent link is not proof of PDF availability, player completeness or roster accuracy.")
        if section in ("Overview", "AI Engines", "Tracker"):
            st.subheader("V8 archive")
            if models:
                st.dataframe(models, hide_index=True, use_container_width=True)
            else:
                st.info("No verified archive summary available.")
            st.caption("Archive counts are not accuracy metrics or proof of live source availability.")
        if section in ("AI Engines", "Tracker"):
            report = scorecard("2026-27")
            st.subheader("Prospective model performance")
            if report.get("status") in ("unavailable", "setup_required"):
                st.warning("Verified scorecard unavailable.")
            elif report.get("status") == "waiting_for_settled_games":
                st.info("Waiting for valid settled V8 forecasts. No V8 accuracy claims.")
            rows = report.get("common_game_comparisons") or []
            if rows:
                st.caption("Each pair uses identical verified final games and frozen pregame forecasts. Different pairs can have different samples.")
                for comparison in rows:
                    with st.expander(f'{comparison["left"]} vs {comparison["right"]} · {comparison["same_game_n"]} games'):
                        if comparison.get("historical_training_sample_differs"):
                            st.warning("Training sample sizes differ; effects of model changes cannot be isolated.")
                        metrics = []
                        for side in ("left", "right"):
                            m = comparison[side + "_metrics"]
                            metrics.append({
                                "Model": comparison[side],
                                "Games": m.get("n"),
                                "Team MAE": m.get("team_points_mae"),
                                "Total MAE": m.get("total_points_mae"),
                                "Winner %": m.get("winner_hit_pct"),
                                "Brier": m.get("brier"),
                                "Scenario MAE": m.get("scenario_team_points_mae"),
                                "Total interval coverage %": m.get("total_80pct_interval_coverage"),
                                "Intervals checked": m.get("total_intervals_checked"),
                            })
                        st.dataframe(metrics, hide_index=True, use_container_width=True)
            else:
                st.info("No verified common-game comparisons available.")
            st.caption("Research only. Small samples do not establish superiority. Lower MAE and Brier are better.")
        if section in ("Overview", "Tracker"):
            detail = tracker_metrics("2026-27")
            st.subheader("Tracker · players & quarters")
            if detail.get("status") == "ok":
                player_rows = detail.get("players", [])
                quarter_rows = detail.get("quarters", [])
                cols = st.columns(2)
                cols[0].metric("Settled player forecasts", sum(row["settled"] for row in player_rows))
                cols[1].metric("Settled quarter forecasts", sum(row["settled"] for row in quarter_rows))
                if detail.get("last_run"):
                    st.caption("Latest V7 tracker run")
                    st.dataframe(detail["last_run"], hide_index=True, use_container_width=True)
                if section == "Tracker":
                    st.write("Player points, rebounds and assists")
                    st.dataframe(player_rows, hide_index=True, use_container_width=True)
                    st.write("Quarter archive")
                    st.dataframe(quarter_rows, hide_index=True, use_container_width=True)
                    st.caption("Metrics use each model's own archived sample; not a matched-game comparison.")
            else:
                st.info("Player / quarter tracker archive unavailable.")
        return
    if section == "Performance":
        st.subheader("Neon · database connectivity")
        db = database_health()
        st.caption("Read-only SELECT 1. Cached for 5 minutes.")
        cols = st.columns(3)
        for col, label, key in zip(cols, ("Connect", "Query + cursor", "Total"),
                                   ("connect_ms", "query_ms", "total_ms")):
            value = db.get(key)
            col.metric(label, f"{value:.1f} ms" if value is not None else "Unavailable")
        if db["status"] != "ok":
            st.warning("Database check did not complete successfully.")
        st.caption("Checked UTC: " + db["checked_utc"])
        st.subheader("Source latency")
        results = sources()
        ranked = summarize_sources(results)
        if ranked:
            st.bar_chart([{"Source": r["source"], "Milliseconds": r["elapsed_ms"]} for r in ranked], x="Source", y="Milliseconds")
            st.caption("Successful source checks only; elapsed time includes response parsing.")
        else:
            st.info("No successful source latency measurements.")
        st.dataframe(results, hide_index=True, use_container_width=True)
        st.info("Public page rendering time, production request history, resource usage and latency percentiles are not instrumented yet.")
        return
    if section == "Users":
        from admin_user_management import access_snapshot
        access = access_snapshot()
        if access.get("status") != "ok":
            st.error("Access denied.")
            return
        st.subheader("Identity & entitlement")
        st.write("OIDC configuration:", "Configured" if access["oidc_configured"] else "Not configured")
        st.caption("Configuration only; this does not verify the identity provider is online.")
        st.dataframe(access["allowlist_counts"], hide_index=True, use_container_width=True)
        st.caption("Counts are unique configured identifiers per type, not people or paying subscribers. Admin takes precedence over Premium.")
        st.write("Account observation:", "Enabled" if registry_enabled() else "Disabled")
        st.write("Daily Free Props:", "Enabled" if free_props_enabled() else "Disabled")
        st.caption("UTC reset; database reservations are enforced server-side only after explicit enablement. Paying subscribers are not verified.")
        st.subheader("Account registry · durable observations")
        registry = accounts()
        if registry.get("status") == "ok":
            rows = registry["accounts"]
            cols = st.columns(3)
            cols[0].metric("Observed accounts", sum(r["observed_accounts"] for r in rows))
            cols[1].metric("Seen last 30 days", sum(r["seen_last_30_days"] for r in rows))
            cols[2].metric("UTC quota reservations", registry["quota"][0]["reservations_today"])
            st.dataframe(rows, hide_index=True, use_container_width=True)
            st.caption("Observed identities, not identity-provider registrations or verified paying subscribers.")
        else:
            st.info("Dedicated account registry not configured or unavailable.")
        st.caption("No role mutations enabled.")
        return
    if section == "Security":
        from admin_security import security_snapshot, read_recent_events
        security = security_snapshot()
        if security.get("status") != "ok":
            st.error("Access denied.")
            return
        st.subheader("Identity & access diagnostics")
        cols = st.columns(2)
        cols[0].metric("Admin identifier entries", security["admin_identifier_entries"])
        cols[1].metric("Overlapping identifiers", security["overlap_entries"])
        st.caption("Identifier entries are not unique people. OIDC configuration is not a live login test.")
        st.write("OIDC configuration:", "Configured" if security["oidc_configured"] else "Missing")
        st.write("Audit database configuration:", "Configured" if security["audit_storage_configured"] else "Missing")
        st.write("Audit HMAC key length:", "Configured" if security["audit_key_configured"] else "Missing or short")
        if security["overlap_entries"]:
            st.warning("Admin and Premium allowlists overlap. Review intended access; admin role takes precedence.")
        st.subheader("Administrative audit")
        audit = read_recent_events()
        if audit.get("status") == "ok":
            if audit["events"]:
                st.dataframe(audit["events"], hide_index=True, use_container_width=True)
            else:
                st.info("No recorded events in this audit store.")
        else:
            st.info("Audit records unavailable or not configured.")
        st.caption("Latest 100 events; no raw identities, secrets or arbitrary metadata.")
        st.write("Audit recording:", "Enabled" if security.get("audit_recording_enabled") else "Disabled")
        if audit_enabled() and st.button("Record access review"):
            if record_admin_event("review_access", "success"):
                st.success("Review recorded.")
            else:
                st.warning("Audit event could not be saved.")
        st.info("Login anomaly monitoring, backup verification and incident response are not connected. Absence of alerts is not proof of safety.")
        return
    if section == "Revenue":
        from admin_revenue import revenue_snapshot, project_revenue
        revenue = revenue_snapshot()
        if revenue.get("status") != "ok":
            st.error("Access denied.")
            return
        st.subheader("Stripe · payment configuration")
        st.write("Checkout configuration:", revenue["checkout_mode"])
        st.write("Fulfillment readiness declared:", revenue["fulfillment_declared_ready"])
        st.caption("Configuration only. No Stripe API verification, live payment or subscription reconciliation.")
        cols = st.columns(2)
        cols[0].metric("Actual revenue", "Not connected")
        cols[1].metric("Active paid subscriptions", "Not connected")
        st.subheader("Stripe · restricted test subscription summary")
        stripe = stripe_test()
        if stripe.get("status") == "ok":
            counts = stripe["subscription_counts"]
            if counts:
                st.dataframe([{"Status": k, "Test subscriptions": v} for k,v in sorted(counts.items())], hide_index=True, use_container_width=True)
            else:
                st.info("No subscriptions returned in test mode.")
            st.caption("Test-mode records only. No revenue or Premium entitlement is inferred.")
        else:
            st.info("Stripe test summary: " + stripe.get("status","unavailable"))
        st.divider()
        st.subheader("Revenue Simulator · USD")
        st.caption("Hypothetical scenario, not actual revenue. Assumes one successful monthly payment per subscriber.")
        cols = st.columns(2)
        n = cols[0].number_input("Paying subscribers", min_value=0, max_value=10000000, value=100, step=1)
        price = cols[1].number_input("Monthly price (USD)", min_value=0.0, max_value=100000.0, value=9.99, step=0.01)
        cols = st.columns(2)
        fixed = cols[0].number_input("Fixed monthly costs (USD)", min_value=0.0, max_value=100000000.0, value=100.0)
        variable = cols[1].number_input("Variable monthly cost per subscriber (USD)", min_value=0.0, max_value=100000.0, value=0.0)
        cols = st.columns(2)
        pct = cols[0].number_input("Payment fee (%)", min_value=0.0, max_value=100.0, value=0.0, step=0.1)
        fee = cols[1].number_input("Fixed fee per payment (USD)", min_value=0.0, max_value=100000.0, value=0.0, step=0.01)
        p = project_revenue(n, price, fixed, pct, fee, variable)
        cols = st.columns(3)
        cols[0].metric("Monthly gross", f'${p["monthly_gross"]:,.2f}')
        cols[1].metric("Annualized gross", f'${p["annualized_gross"]:,.2f}')
        cols[2].metric("Monthly operating result", f'${p["monthly_operating_result"]:,.2f}')
        st.metric("Break-even subscribers", p["break_even_subscribers"] if p["break_even_subscribers"] is not None else "No positive contribution")
        st.dataframe([{"Monthly payment fees": float(p["monthly_payment_fees"]),
                       "Monthly fixed costs": float(p["monthly_fixed_cost"]),
                       "Monthly variable costs": float(p["monthly_variable_cost"])}], hide_index=True, use_container_width=True)
        st.caption("Defaults are illustrative and editable. No taxes, refunds, churn or currency conversion unless explicitly modeled in costs. Not accounting profit.")
        return
    if section == "Settings":
        from admin_settings import settings_snapshot, validate_draft
        config = settings_snapshot()
        if config.get("status") != "ok":
            st.error("Access denied.")
            return
        st.subheader("Deployment configuration")
        st.caption("Read-only configuration indicators, not live service checks.")
        for label, key in (("OIDC", "oidc_configured"), ("Tracker database", "tracker_url_configured"),
                           ("Audit database", "audit_storage_configured"), ("Audit key length", "audit_key_configured")):
            st.write(label + ":", "Configured" if config[key] else "Missing")
        st.write("Checkout mode:", config["checkout_mode"])
        st.write("Fulfillment readiness declared:", config["fulfillment_declared_ready"])
        st.write("Account registry:", "Enabled" if registry_enabled() else "Disabled")
        st.write("Free Props:", "Enabled" if free_props_enabled() else "Disabled")
        st.write("Audit recording:", "Enabled" if audit_enabled() else "Disabled")
        st.divider()
        st.subheader("Change preview")
        st.warning("Preview only. No changes are saved or applied to the public app.")
        with st.form("control_center_settings_preview"):
            maintenance = st.checkbox("Request maintenance mode", value=False)
            enabled = st.checkbox("Enable announcement", value=False)
            announcement = st.text_input("Announcement (plain text)", max_chars=300)
            submitted = st.form_submit_button("Validate draft")
        if submitted:
            try:
                draft = validate_draft({"maintenance_requested":maintenance,
                    "announcement_enabled":enabled, "announcement_text":announcement})
                st.success("Draft validated. No changes applied.")
                st.write("Maintenance requested:", draft["maintenance_requested"])
                st.write("Announcement enabled:", draft["announcement_enabled"])
                if draft["announcement_enabled"]:
                    st.text(draft["announcement_text"])
            except ValueError as exc:
                st.error(str(exc))
        st.info("Feature activation, maintenance enforcement, payment changes, model selection and rollback are not connected.")
        return

