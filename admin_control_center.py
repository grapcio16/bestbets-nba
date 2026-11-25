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
    from admin_data_intelligence import read_snapshot
    from tracker_storage import tracker_database_url

    @st.cache_data(ttl=120, show_spinner=False)
    def snapshot(season):
        return read_snapshot(tracker_database_url(), season)

    st.markdown("""<style>
    .stApp { background: #080d1c; color: #edf0ff; }
    [data-testid="stMetric"] { border: 1px solid #343052; border-radius: 14px;
        padding: 16px; background: #11192e; }
    [data-testid="stMetricValue"] { color: #b69aff; }
    [data-testid="stSidebar"] { background: #101528; }
    </style>""", unsafe_allow_html=True)
    st.sidebar.title("HOOPZARO")
    st.sidebar.caption("CONTROL CENTER · ADMIN")
    section = st.sidebar.radio("Navigation", SECTIONS)
    st.sidebar.markdown("[Return to Hoopzaro](?)")
    st.title(section)
    st.caption("Internal administration · Read-only preview")
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
                st.info("NBA/ESPN live latency, injuries and player completeness are not connected yet.")
        if section in ("Overview", "AI Engines", "Tracker"):
            st.subheader("V8 archive")
            if models:
                st.dataframe(models, hide_index=True, use_container_width=True)
            else:
                st.info("No verified archive summary available.")
            st.caption("Archive counts are not accuracy metrics or proof of live source availability.")
        return
    pending = {
        "Users": "Accounts, roles and subscription access",
        "Revenue": "Stripe, recurring revenue and operating costs",
        "Performance": "API latency, page load and database timing",
        "Security": "Audit events, authentication and incident monitoring",
        "Settings": "Controlled configuration and feature flags",
    }
    st.info(pending[section] + " — not connected yet.")
    st.caption("No write actions enabled.")
