"""Read-only deployment diagnostics and non-persistent settings drafts."""
from collections.abc import Mapping

# Deliberately exclude payment, entitlement and model controls from editable
# drafts until their independent authorization and rollback paths exist.
DRAFT_DEFAULTS = {"maintenance_requested": False, "announcement_enabled": False,
                  "announcement_text": ""}

def validate_draft(values):
    if not isinstance(values, Mapping) or set(values) != set(DRAFT_DEFAULTS):
        raise ValueError("Unsupported settings")
    for key in ("maintenance_requested", "announcement_enabled"):
        if type(values[key]) is not bool:
            raise ValueError("Invalid switch value")
    message = values["announcement_text"]
    if not isinstance(message, str) or len(message) > 300:
        raise ValueError("Announcement must be plain text, at most 300 characters")
    if any(ord(c) < 32 or ord(c) == 127 for c in message):
        raise ValueError("Control characters are not allowed")
    message = message.strip()
    if values["announcement_enabled"] and not message:
        raise ValueError("Enabled announcements require text")
    return {"maintenance_requested": values["maintenance_requested"],
            "announcement_enabled": values["announcement_enabled"],
            "announcement_text": message}

def settings_snapshot():
    from access_control import current_role, auth_configured
    if current_role() != "admin":
        return {"status": "denied"}
    from admin_revenue import revenue_snapshot
    from admin_security import security_snapshot
    from tracker_storage import tracker_database_url
    revenue = revenue_snapshot()
    security = security_snapshot()
    return {
        "status": "ok",
        "oidc_configured": auth_configured(),
        "tracker_url_configured": bool(tracker_database_url()),
        "checkout_mode": revenue.get("checkout_mode", "unknown"),
        "fulfillment_declared_ready": revenue.get("fulfillment_declared_ready", False),
        "audit_storage_configured": security.get("audit_storage_configured", False),
        "audit_key_configured": security.get("audit_key_configured", False),
        "settings_write_enabled": False,
    }
