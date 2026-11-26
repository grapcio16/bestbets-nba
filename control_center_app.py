"""Standalone administration entrypoint; never imports the customer UI."""
import streamlit as st
from access_control import current_role, auth_configured, login_provider

def main():
    st.set_page_config(page_title="HOOPZARO | Control Center", page_icon="📊",
                       layout="wide", initial_sidebar_state="expanded")
    role = current_role()
    if role == "admin":
        from admin_control_center import render
        render(dedicated=True)
        return
    st.markdown("""<style>
    .stApp {background:radial-gradient(ellipse at 70% 0%,#261744,#080d1c 60%);color:#eef1ff;}
    [data-testid="stMainBlockContainer"]{max-width:680px;padding-top:12vh;}
    [data-testid="stHeading"]{color:#c4b5fd;}
    </style>""", unsafe_allow_html=True)
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

if __name__ == "__main__":
    main()
