"""Private, read-only Hoopzaro Control Center."""
from __future__ import annotations

SECTIONS = (
    "Overview", "Data Center", "AI Engines", "Tracker", "Users",
    "Revenue", "Performance", "Security", "Settings",
)

def authorized(role: str) -> bool:
    return role == "admin"

def render():
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

    st.markdown("""<style>
    .stApp { background: radial-gradient(ellipse at 80% 0%, #21143c 0%, #080d1c 45%); color: #edf0ff; }
    [data-testid="stMainBlockContainer"] { max-width: 1440px; padding-top: 2rem; }
    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] h1 { color: #c4b5fd; letter-spacing: .08em; }
    [data-testid="stMetric"] { box-shadow: 0 0 18px #8b5cf618; }
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
    st.sidebar.markdown("[Return to Hoopzaro](?)")
    st.caption("HOOPZARO / CONTROL CENTER / " + section.upper())
    st.title(section)
    st.caption("Internal administration · Read-only preview · NBA 2026–27")
    if st.sidebar.button("Refresh telemetry"):
        snapshot.clear()
        scorecard.clear()
        sources.clear()
        database_health.clear()
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
                st.caption("checked_utc records retrieval time, not report publication. Latency includes parsing. Official injury publication freshness, player completeness and rosters remain unverified.")
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
            st.bar_chart({r["source"]: r["elapsed_ms"] for r in ranked})
            st.caption("Successful source checks only; elapsed time includes response parsing.")
        else:
            st.info("No successful source latency measurements.")
        st.dataframe(results, hide_index=True, use_container_width=True)
        st.info("Public page rendering time, production request history, resource usage and latency percentiles are not instrumented yet.")
        return
    pending = {
        "Users": "Accounts, roles and subscription access",
        "Revenue": "Stripe, recurring revenue and operating costs",
        "Security": "Audit events, authentication and incident monitoring",
        "Settings": "Controlled configuration and feature flags",
    }
    st.info(pending[section] + " — not connected yet.")
    st.caption("No write actions enabled.")
