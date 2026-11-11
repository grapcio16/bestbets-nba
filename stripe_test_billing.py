"""Stripe Billing TEST-ONLY infrastructure for BestBets (not wired to public app).

There is deliberately no self-service anonymous checkout endpoint: the
production application has no trusted authentication session or persistent
subscriber database yet. The application server must provide an authenticated
internal user ID and independently stored Stripe customer ID.

Never pass Stripe secrets to the browser or commit them to GitHub.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import os
import re
from typing import Any, Mapping, Optional, Protocol
from urllib.parse import urlparse

ALLOWED_EVENTS = frozenset({
    "checkout.session.completed",
    "customer.subscription.created",
    "customer.subscription.updated",
    "customer.subscription.deleted",
    "invoice.paid",
    "invoice.payment_failed",
    "invoice.payment_action_required",
    "customer.subscription.paused",
    "customer.subscription.resumed",
    "charge.refunded",
    "charge.dispute.created",
    "charge.dispute.closed",
})
PREMIUM_STATUSES = frozenset({"active"})
API_VERSION = "2025-02-24.acacia"
ID_RE = re.compile(r"^[A-Za-z0-9_-]{8,128}$")
STRIPE_CUSTOMER_RE = re.compile(r"^cus_[A-Za-z0-9]+$")
STRIPE_SUB_RE = re.compile(r"^sub_[A-Za-z0-9]+$")


class BillingNotConfigured(RuntimeError):
    """Billing has not been safely configured for a test environment."""


def _obj(value: Any, key: str, default: Any = None) -> Any:
    """Access fields from StripeObject or dict without exposing user data."""
    if isinstance(value, Mapping):
        return value.get(key, default)
    return getattr(value, key, default)


def _validated_url(value: str, *, local_dev: bool = False) -> str:
    if not value or any(c.isspace() for c in value):
        raise BillingNotConfigured("Return URL is missing or invalid")
    parsed = urlparse(value)
    if parsed.username or parsed.password or parsed.fragment or parsed.query or parsed.path not in ("", "/"):
        raise BillingNotConfigured("Return URL must be an origin without credentials, query or fragment")
    if parsed.scheme == "https" and parsed.hostname and parsed.port in (None, 443):
        return value
    if local_dev and parsed.scheme == "http" and parsed.hostname in {"localhost", "127.0.0.1"}:
        return value
    raise BillingNotConfigured("A secure HTTPS return URL is required")


@dataclass(frozen=True)
class TestBillingConfig:
    __test__ = False
    secret_key: str = field(repr=False)
    price_id: str
    webhook_secret: str = field(repr=False)
    app_url: str
    # Only the test Stripe account is supported until explicit merchant review.

    def validate(self) -> None:
        if not self.secret_key.startswith("sk_test_") or len(self.secret_key) < 12:
            raise BillingNotConfigured("Use a TEST secret key; live keys are forbidden")
        if not self.webhook_secret.startswith("whsec_") or len(self.webhook_secret) < 12:
            raise BillingNotConfigured("Missing Stripe webhook signing secret")
        if not re.fullmatch(r"price_[A-Za-z0-9]+", self.price_id):
            raise BillingNotConfigured("Invalid Stripe recurring price ID")
        _validated_url(self.app_url, local_dev=True)
        # No approval flag can turn this adapter into a live-money adapter.

    @classmethod
    def from_env(cls) -> "TestBillingConfig":
        return cls(
            secret_key=os.getenv("STRIPE_TEST_SECRET_KEY", ""),
            price_id=os.getenv("STRIPE_TEST_PRICE_ID", ""),
            webhook_secret=os.getenv("STRIPE_TEST_WEBHOOK_SECRET", ""),
            app_url=os.getenv("BESTBETS_APP_URL", ""),
        )


@dataclass(frozen=True)
class BillingEvent:
    event_id: str
    kind: str
    customer_id: str
    subscription_id: str
    subscription_status: Optional[str]
    charge_id: str = ""
    # This is an authenticated STRIPE event, not automatic authorization.
    # A persistent, idempotent data-store consumer must reconcile it.


def has_premium_access(stripe_status: Optional[str]) -> bool:
    """Legacy status hint ONLY; never use for authorization or paid access."""
    return stripe_status in PREMIUM_STATUSES


class _StripeSDK(Protocol):
    api_key: str
    checkout: Any
    billing_portal: Any
    Webhook: Any


class StripeTestGateway:
    def __init__(self, config: TestBillingConfig, sdk: _StripeSDK):
        config.validate()
        self.config = config
        self.sdk = sdk
        # Never mutate the process-global SDK key (unsafe across instances).

    def create_checkout(
        self,
        *,
        authenticated_user_id: str,
        request_id: str,
        verified_customer_id: Optional[str] = None,
        verified_email: Optional[str] = None,
    ) -> str:
        """Create a TEST subscription Checkout URL.

        authenticated_user_id must come from a verified login, NEVER from
        arbitrary browser JSON. verified_customer_id is retrieved using that
        user ID from a trusted server-side database, never a client parameter.
        request_id is generated by the server and kept stable on retry.
        """
        if not ID_RE.fullmatch(authenticated_user_id):
            raise ValueError("Authenticated user ID is missing or invalid")
        if not ID_RE.fullmatch(request_id):
            raise ValueError("Request ID must be generated by the application server")
        if verified_customer_id is not None and not STRIPE_CUSTOMER_RE.fullmatch(verified_customer_id):
            raise ValueError("Untrusted Stripe customer ID")
        if verified_email is not None and ("@" not in verified_email or len(verified_email)>254):
            raise ValueError("Invalid verified customer email")
        if verified_customer_id and verified_email:
            raise ValueError("Specify existing customer ID or verified email, not both")

        base = self.config.app_url.rstrip("/")
        args = {
            "mode": "subscription",
            "line_items": [{"price": self.config.price_id, "quantity": 1}],
            "success_url": f"{base}/?checkout=success&session_id={{CHECKOUT_SESSION_ID}}",
            "cancel_url": f"{base}/?checkout=cancelled",
            "client_reference_id": authenticated_user_id,
            "metadata": {"internal_user_id": authenticated_user_id},
            "subscription_data": {"metadata": {"internal_user_id": authenticated_user_id}},
            "billing_address_collection": "auto",
        }
        if verified_customer_id:
            args["customer"] = verified_customer_id
        if verified_email:
            args["customer_email"] = verified_email

        session = self.sdk.checkout.Session.create(
            **args,
            api_key=self.config.secret_key, stripe_version=API_VERSION,
            # Stripe SDK forwards this as request option; request_id is trusted.
            idempotency_key=f"bestbets-test-{request_id}",
        )
        if _obj(session, "livemode") is not False:
            raise BillingNotConfigured("Live Checkout session refused")
        url = _obj(session, "url", "")
        if not isinstance(url, str) or not url.startswith("https://checkout.stripe.com/"):
            raise RuntimeError("Stripe did not return a valid hosted checkout URL")
        return url

    def create_customer_portal(
        self, *, verified_customer_id: str, authenticated_user_id: str
    ) -> str:
        """Only pass a customer ID obtained from the authenticated user's DB row."""
        if not STRIPE_CUSTOMER_RE.fullmatch(verified_customer_id):
            raise ValueError("Invalid verified Stripe customer ID")
        if not ID_RE.fullmatch(authenticated_user_id):
            raise ValueError("Invalid authenticated user ID")
        result = self.sdk.billing_portal.Session.create(
            customer=verified_customer_id, return_url=self.config.app_url,
            api_key=self.config.secret_key, stripe_version=API_VERSION,
        )
        if _obj(result, "livemode", False):
            raise BillingNotConfigured("Live customer portal refused")
        url = _obj(result, "url", "")
        if not isinstance(url, str) or not url.startswith("https://billing.stripe.com/"):
            raise RuntimeError("Stripe did not return a valid billing portal URL")
        return url

    def verify_webhook(self, *, raw_body: bytes, signature: str) -> Optional[BillingEvent]:
        """Verify the EXACT raw body before reading ANY event fields.

        Returns a normalized event, or None for irrelevant notifications.
        Updating customer records must happen in an idempotent transaction
        keyed by event_id in a persistent database (not Streamlit session_state).
        """
        if not isinstance(raw_body, bytes) or not raw_body or len(raw_body)>1024*1024:
            raise ValueError("Invalid webhook request body")
        if not signature:
            raise ValueError("Missing Stripe-Signature")
        event = self.sdk.Webhook.construct_event(raw_body, signature, self.config.webhook_secret)
        if _obj(event, "livemode", True) is not False:
            raise BillingNotConfigured("Live webhook event refused in test gateway")
        if _obj(event, "account"):
            raise ValueError("Stripe Connect events are not supported")
        kind = _obj(event, "type", "")
        if kind not in ALLOWED_EVENTS:
            return None
        event_id = _obj(event, "id", "")
        if not isinstance(event_id, str) or not re.fullmatch(r"evt_[A-Za-z0-9]+", event_id):
            raise ValueError("Malformed Stripe event ID")
        obj = _obj(_obj(event, "data", {}), "object", {})
        if kind.startswith("charge."):
            charge = _obj(obj, "charge") if kind.startswith("charge.dispute.") else _obj(obj, "id")
            if not isinstance(charge, str) or not re.fullmatch(r"ch_[A-Za-z0-9]+", charge):
                raise ValueError("Malformed charge ID")
            return BillingEvent(event_id, kind, "", "", None, charge)
        customer = _obj(obj, "customer", "")
        subscription = _obj(obj, "subscription", "")
        if kind.startswith("customer.subscription."):
            subscription = _obj(obj, "id", "")
        if kind == "checkout.session.completed":
            # Checkout completion does NOT prove the subscription is active.
            if _obj(obj, "mode") != "subscription":
                return None
        if kind.startswith("invoice."):
            if not subscription:
                parent = _obj(_obj(obj, "parent", {}), "subscription_details", {})
                subscription = _obj(parent, "subscription", "")
            if not subscription:
                return None  # unrelated one-off invoice, never a subscription grant
        if not isinstance(customer, str) or not STRIPE_CUSTOMER_RE.fullmatch(customer):
            raise ValueError("Unknown Stripe customer")
        if not isinstance(subscription, str) or not STRIPE_SUB_RE.fullmatch(subscription):
            raise ValueError("Missing Stripe subscription ID")
        status = _obj(obj, "status") if kind.startswith("customer.subscription.") else None
        if kind == "customer.subscription.deleted":
            status = "canceled"
        return BillingEvent(
            event_id=event_id, kind=kind, customer_id=customer,
            subscription_id=subscription, subscription_status=status
        )


def create_test_gateway() -> StripeTestGateway:
    """Import stripe lazily so NBA production isn't coupled to billing."""
    import stripe
    return StripeTestGateway(TestBillingConfig.from_env(), stripe)
