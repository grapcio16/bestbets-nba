"""Standalone Streamlit sandbox; never change the public app entrypoint to this file."""
import hashlib
import hmac
import os
import streamlit as st
from access_control import auth_configured,current_claims,current_principal,login_provider
from billing_sandbox_adapter import StripeTestAPI,BillingError,approved_return_url
from billing_sandbox_store import Store,SandboxService,tester_identity
from billing_sandbox_config import load_config,check_connections

st.set_page_config(page_title="HOOPZARO | Billing sandbox",page_icon="🏀")
st.title("HOOPZARO — Billing sandbox")
st.warning("Środowisko testowe. Nie pobiera prawdziwych płatności i nie nadaje dostępu w aplikacji publicznej.")
if not auth_configured():
    st.error("Brak konfiguracji osobnego logowania testowego.")
    st.stop()
claims=current_claims()
principal=current_principal()
if principal=="guest":
    if st.button("Zaloguj się przez Google"):
        provider=login_provider()
        st.login(provider) if provider else st.login()
    st.stop()
if st.button("Wyloguj"):
    st.logout()
    st.stop()
if tester_identity(principal) is None:
    # Enrollment: only a verified test email explicitly allowed by deployment
    # may see its own account hash. Never expose raw subject or the HMAC key.
    email=str(claims.get("email") or "").casefold().strip()
    allowed={x.strip().casefold() for x in os.environ.get("HOOPZARO_BILLING_SANDBOX_ENROLL_EMAILS","").split(",") if x.strip()}
    key=os.environ.get("HOOPZARO_BILLING_SANDBOX_HMAC_KEY","").encode()
    if claims.get("email_verified") is True and email in allowed and len(key)>=32:
        st.caption("Identyfikator do wpisania na listę testerów (nie jest hasłem):")
        st.code(hmac.new(key,principal.encode(),hashlib.sha256).hexdigest())
    else:
        st.info("To konto nie należy do pilotażu.")
    st.stop()
config,problems=load_config(os.environ)
if problems:
    st.error("Brak poprawnej konfiguracji sandbox — sprawdź poniższe pola w Secrets.")
    for name,message in problems.items():
        st.markdown("**"+name+"**")
        st.caption(message)
    st.stop()
api=StripeTestAPI(config["STRIPE_KEY"],config["STRIPE_ACCOUNT"])
service=SandboxService(Store(config["DATABASE_URL"]),api,config["PRICE_ID"],
    config["PRODUCT_ID"],config["RETURN_URL"])
if st.button("Sprawdź konfigurację (bez płatności)"):
    for name,result in check_connections(config).items():
        if result=="OK":
            st.success(name+": OK")
        else:
            st.error(name+": "+result)
st.write("Testowana subskrypcja: 9,99 USD / miesiąc.")
if st.button("Utwórz lub otwórz testową sesję Checkout"):
    try:
        url=service.start(principal)
        st.link_button("Otwórz bezpieczny Stripe Checkout (TEST)",url)
    except Exception:
        st.error("Nie udało się utworzyć lub wznowić sesji. Nie twórz drugiej subskrypcji; sprawdź istniejący zakup.")
if st.button("Zweryfikuj uprawnienie testowe"):
    result=service.decision(principal)
    if result.allowed:
        st.success("PREMIUM SANDBOX — zweryfikowane uprawnienie testowe.")
        st.caption("Ważność dowodu do: "+result.expires_at.isoformat())
    else:
        st.info("FREE SANDBOX — brak potwierdzonego uprawnienia.")
        st.caption(result.reason)
