"""Standalone administration entrypoint; never imports the customer UI."""
import streamlit as st

def main():
    from access_control import current_role, auth_configured, login_provider
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
    [data-testid="stButton"] button{min-height:48px;border:1px solid #9a7aff;border-radius:12px;background:#3c2c71;color:#fff;font-weight:650;}
    [data-testid="stMainBlockContainer"]{padding:12vh 2rem 3rem;}
    [data-testid="stHeader"]{background:#080d1c;}
    </style>""", unsafe_allow_html=True)
    st.title("HOOPZARO | Control Center")
    st.markdown("Prywatny panel administracyjny")
    if role == "guest":
        if not auth_configured():
            st.error("Logowanie administratora nie jest skonfigurowane.")
        elif st.button("Zaloguj się", type="primary"):
            provider = login_provider()
            if provider is None:
                st.login()
            else:
                st.login(provider)
    else:
        st.error("Brak dostępu. Wymagane konto administratora.")
        if st.button("Wyloguj się"):
            st.logout()
    st.stop()

if __name__ == "__main__":
    main()
