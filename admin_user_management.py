"""Admin-only aggregate view of configured access, not a user directory."""
from collections.abc import Mapping

def normalized_entries(value):
    if not isinstance(value, (list, tuple, set)):
        return set()
    return {str(item).strip().casefold() for item in value if str(item).strip()}

def summarize_access(access, oidc_configured):
    access = access if isinstance(access, Mapping) else {}
    admins = {kind: normalized_entries(access.get("admin_" + kind))
              for kind in ("subjects", "emails")}
    premium = {kind: normalized_entries(access.get("premium_" + kind))
               for kind in ("subjects", "emails")}
    # A subject and verified email can refer to the same person; never sum them
    # and call the result a count of accounts or paying customers.
    rows = []
    for kind in ("subjects", "emails"):
        rows.append({"Identifier type": kind,
                     "Admin entries": len(admins[kind]),
                     "Premium entries": len(premium[kind]),
                     "Overlapping entries": len(admins[kind] & premium[kind])})
    return {"oidc_configured": bool(oidc_configured), "allowlist_counts": rows,
            "registered_accounts": None, "active_accounts": None,
            "paying_subscribers": None, "daily_props_usage": None}

def access_snapshot():
    # Reuse current server-side role and secret loading. Never expose identifiers.
    from access_control import current_role, auth_configured, _secret_section
    if current_role() != "admin":
        return {"status": "denied"}
    return {"status": "ok", **summarize_access(_secret_section("access"), auth_configured())}
