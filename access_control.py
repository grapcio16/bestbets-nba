"""Server-side HOOPZARO access roles, backed by Streamlit's verified OIDC login.

Roles are NEVER inferred from IP addresses, browser storage, URL parameters,
Streamlit session flags or values sent by the embedded JavaScript frontend.
Administrators have Premium access without a Stripe subscription.

Configure an OIDC identity provider under [auth] and allowed accounts under
[access] in the *deployment secrets*, never commit secrets to GitHub.
"""
from __future__ import annotations

from datetime import datetime, timezone
from math import isfinite
from typing import Any, Mapping


def _items(value: Any) -> set[str]:
    if not isinstance(value, (list, tuple, set)):
        return set()
    return {str(item).strip().casefold() for item in value if str(item).strip()}


def _subjects(value: Any) -> set[str]:
    """OIDC issuer and subject are case-sensitive identifiers."""
    if not isinstance(value, (list, tuple, set)):
        return set()
    return {item for item in value if isinstance(item, str) and item}


def account_key(claims: Mapping[str, Any]) -> str:
    """Issuer + immutable subject avoids collisions across OIDC providers."""
    issuer = str(claims.get("iss") or "").strip()
    subject = str(claims.get("sub") or "").strip()
    return f"{issuer}|{subject}" if issuer and subject else ""


def role_from_claims(
    claims: Mapping[str, Any] | None,
    access: Mapping[str, Any] | None,
    *,
    now: datetime | None = None,
) -> str:
    """Return guest/free/premium/admin. Only signed-in OIDC claims qualify."""
    claims = claims or {}
    access = access or {}
    key = account_key(claims)
    if not key:
        return "guest"

    clock = now or datetime.now(timezone.utc)
    try:
        expires = claims.get("exp")
        not_before = claims.get("nbf")
        if expires is not None and (isinstance(expires, bool) or not isfinite(float(expires)) or float(expires) <= clock.timestamp()):
            return "guest"
        if not_before is not None and (isinstance(not_before, bool) or not isfinite(float(not_before)) or float(not_before) > clock.timestamp()):
            return "guest"
    except (TypeError, ValueError, OverflowError):
        return "guest"

    if key in _subjects(access.get("admin_subjects")):
        return "admin"
    # Email can serve as a convenient fallback only when the OIDC provider
    # explicitly verified it. Unknown/missing email_verified is NOT enough.
    email = str(claims.get("email") or "").strip().casefold()
    verified = claims.get("email_verified") is True
    if verified and email and email in _items(access.get("admin_emails")):
        return "admin"
    if key in _subjects(access.get("premium_subjects")):
        return "premium"
    if verified and email and email in _items(access.get("premium_emails")):
        return "premium"
    return "free"


def _secret_section(name: str) -> dict:
    import streamlit as st

    try:
        section = st.secrets.get(name, {})
        return dict(section) if isinstance(section, Mapping) else {}
    except (FileNotFoundError, OSError, KeyError):
        return {}
    except Exception as exc:
        # StreamlitSecretNotFoundError also appears when no secrets file exists;
        # this should never make the entire public application unavailable.
        if type(exc).__name__ == "StreamlitSecretNotFoundError":
            return {}
        raise


def auth_configured() -> bool:
    settings = _secret_section("auth")
    return bool(settings.get("client_id") or any(
        isinstance(value, Mapping) and value.get("client_id")
        for value in settings.values()
    ))


def login_provider() -> str | None:
    """Support both a default [auth] provider and a named [auth.google]."""
    settings = _secret_section("auth")
    if settings.get("client_id"):
        return None
    providers = [key for key, value in settings.items()
                 if isinstance(value, Mapping) and value.get("client_id")]
    return str(providers[0]) if len(providers) == 1 else None


def current_claims() -> dict:
    import streamlit as st

    if not auth_configured():
        return {}
    try:
        if not st.user.is_logged_in:
            return {}
        claims = st.user.to_dict()
        return claims if isinstance(claims, dict) and account_key(claims) else {}
    except (AttributeError, KeyError):
        return {}


def current_role() -> str:
    return role_from_claims(current_claims(), _secret_section("access"))


def premium_entitled() -> bool:
    return current_role() in ("admin", "premium")


def auth_context() -> dict:
    """Non-sensitive presentation fields; never used by the server as proof."""
    claims = current_claims()
    role = role_from_claims(claims, _secret_section("access"))
    display = str(claims.get("name") or claims.get("email") or "").strip()[:80]
    return {
        "configured": auth_configured(),
        "logged_in": role != "guest",
        "role": role,
        "name": display,
    }


def current_principal() -> str:
    """Bind per-session Premium result caches to a single OIDC identity."""
    claims = current_claims()
    return account_key(claims) if role_from_claims(claims, _secret_section("access")) != "guest" else "guest"
