"""Hoopzaro public entrypoint, with an isolated Control Center route.

Control Center UI revision: 2026-11-26-r10 (Stripe test billing; automatic code refresh).
Entrypoint revision tracks UI updates for deployment file watchers.
"""
import os
from urllib.parse import urlsplit
import streamlit as st
from access_control import _secret_section

ADMIN_HOST = "hoopzaro-control-center.streamlit.app"

def is_control_center_deployment():
    # Routing only: URL/headers never grant any privilege.
    if os.environ.get("HOOPZARO_DEPLOYMENT_MODE", "").strip().lower() == "control_center":
        return True
    try:
        if urlsplit(str(_secret_section("auth").get("redirect_uri", ""))).hostname == ADMIN_HOST:
            return True
    except ValueError:
        pass
    try:
        if urlsplit(str(st.context.url or "")).hostname == ADMIN_HOST:
            return True
    except (AttributeError, ValueError, RuntimeError):
        pass
    try:
        return any(str(st.context.headers.get(name, "")).strip().lower() == ADMIN_HOST
                   for name in ("Host", "X-Forwarded-Host"))
    except (AttributeError, RuntimeError):
        return False

if is_control_center_deployment():
    from control_center_app import main
    main()
else:
    control_center_requested = st.query_params.get("control_center") == "1"
    st.set_page_config(
        page_title="HOOPZARO | Control Center" if control_center_requested else "HOOPZARO | NBA Analytics",
        page_icon="🏀", layout="wide",
        initial_sidebar_state="expanded" if control_center_requested else "collapsed",
    )
    if control_center_requested:
        from admin_control_center import render
        render()
    else:
        from bestbets_custom_screen import main
        main()
