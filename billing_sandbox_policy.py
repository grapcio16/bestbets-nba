"""Offline decision policy for a deliberately limited Stripe sandbox pilot.

Not wired to access_control. Inputs must be constructed ONLY by a future
server-side adapter from persisted checkout binding and canonical Stripe API
responses. This module does not authenticate a user, verify a webhook, fetch
Stripe, write to a database, or grant production access.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import re

PRICE_MINOR = 999
CURRENCY = "usd"
MAX_EVIDENCE_AGE = timedelta(minutes=5)

@dataclass(frozen=True)
class CheckoutBinding:
    account_id: str              # dedicated billing HMAC, not analytics ID
    checkout_id: str             # verified server-created cs_test_ identifier
    customer_id: str
    subscription_id: str
    price_id: str

@dataclass(frozen=True)
class SandboxEvidence:
    livemode: bool
    checkout_id: str
    customer_id: str
    subscription_id: str
    price_id: str
    subscription_status: str
    invoice_id: str
    invoice_paid: bool
    captured_card_payment: bool
    no_refund_or_dispute: bool
    amount_minor: int
    currency: str
    exact_single_monthly_item: bool
    paid_from: datetime
    paid_through: datetime
    verified_at: datetime

@dataclass(frozen=True)
class Decision:
    allowed: bool
    reason: str
    expires_at: datetime | None = None

def _identifier(value, prefix):
    return isinstance(value,str) and bool(re.fullmatch(re.escape(prefix)+r"[A-Za-z0-9_]{1,200}",value))

def _aware(value):
    return isinstance(value,datetime) and value.tzinfo is not None and value.utcoffset() is not None

def decide_sandbox_access(binding, evidence, *, principal_hmac, configured_price_id,
                          pilot_enabled=False, tester_allowed=False, now=None):
    """Conservative sandbox-only policy; reject ambiguity, trial and grace.
    
    Future adapter must separately verify the sandbox account, invoice line,
    charge relationship, subscription/checkout mapping and actual Stripe API
    responses. No client-supplied input or success URL qualifies as evidence.
    """
    deny=lambda reason: Decision(False,reason)
    if pilot_enabled is not True or tester_allowed is not True:
        return deny("pilot_disabled")
    if not isinstance(binding,CheckoutBinding) or not isinstance(evidence,SandboxEvidence):
        return deny("missing_evidence")
    if not isinstance(principal_hmac,str) or not re.fullmatch("[0-9a-f]{64}",principal_hmac) or binding.account_id!=principal_hmac:
        return deny("account_mismatch")
    if evidence.livemode is not False or not _identifier(binding.checkout_id,"cs_test_"):
        return deny("environment_mismatch")
    if not (_identifier(binding.customer_id,"cus_") and _identifier(binding.subscription_id,"sub_") and _identifier(configured_price_id,"price_")):
        return deny("invalid_binding")
    if (binding.checkout_id,binding.customer_id,binding.subscription_id,binding.price_id)!=(
        evidence.checkout_id,evidence.customer_id,evidence.subscription_id,evidence.price_id):
        return deny("binding_mismatch")
    if binding.price_id!=configured_price_id or evidence.exact_single_monthly_item is not True:
        return deny("price_mismatch")
    if evidence.subscription_status!="active":
        return deny("subscription_not_active")
    if not _identifier(evidence.invoice_id,"in_") or evidence.invoice_paid is not True or evidence.captured_card_payment is not True:
        return deny("payment_not_confirmed")
    if evidence.no_refund_or_dispute is not True:
        return deny("refund_or_dispute")
    # Sandbox pilot intentionally excludes discounts, partial payments, credits,
    # manual/out-of-band payments, multi-item invoices, taxes and prorations.
    if type(evidence.amount_minor) is not int or evidence.amount_minor!=PRICE_MINOR or evidence.currency!=CURRENCY:
        return deny("unsupported_amount")
    now=now if now is not None else datetime.now(timezone.utc)
    if not all(_aware(t) for t in (now,evidence.verified_at,evidence.paid_from,evidence.paid_through)):
        return deny("invalid_time")
    if not timedelta(0)<=now-evidence.verified_at<=MAX_EVIDENCE_AGE:
        return deny("stale_evidence")
    if not evidence.paid_from<=now<evidence.paid_through or evidence.paid_through-evidence.paid_from>timedelta(days=32):
        return deny("invalid_paid_period")
    return Decision(True,"verified_sandbox_payment",min(evidence.paid_through,evidence.verified_at+MAX_EVIDENCE_AGE))
