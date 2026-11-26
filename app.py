"""Hoopzaro public entrypoint and isolated administration deployment."""
import streamlit as st
from access_control import _secret_section

# Trusted deployment configuration, not the browser host or query string.
# Both deployments use the same source code, but different OIDC redirect URIs.
dedicated = _secret_section("auth").get("redirect_uri") == (
    "https://hoopzaro-control-center.streamlit.app/oauth2callback"
)
control_center_requested = dedicated or st.query_params.get("control_center") == "1"

st.set_page_config(
    page_title="HOOPZARO | Control Center" if control_center_requested else "HOOPZARO | NBA Analytics",
    page_icon="🏀",
    layout="wide",
    initial_sidebar_state="expanded" if control_center_requested else "collapsed",
)

if dedicated:
    from access_control import current_role, auth_configured, login_provider
    role = current_role()
    if role == "admin":
        from admin_control_center import render
        render(dedicated=True)
    else:
        # No public frontend or telemetry is loaded before authorization.
        st.title("HOOPZARO | Control Center")
        st.caption("Private administration · authorized administrators only")
        if role == "guest":
            if not auth_configured():
                st.error("Administrator authentication is not configured.")
            elif st.button("Sign in", type="primary"):
                provider = login_provider()
                if provider is None:
                    st.login()
                else:
                    st.login(provider)
        else:
            st.error("Access denied. An administrator account is required.")
            if st.button("Sign out"):
                st.logout()
        st.stop()
elif control_center_requested:
    from admin_control_center import render
    render()
else:
    from bestbets_custom_screen import main
    main()
