"""Revenue planning and checkout configuration diagnostics. No Stripe mutations."""
from decimal import Decimal, InvalidOperation, ROUND_CEILING, ROUND_HALF_UP
from checkout_links import validated_checkout_url, is_test_checkout_url

CENT = Decimal("0.01")
DEFAULT_PRICE = Decimal("9.99")

def _decimal(value):
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        raise ValueError("Invalid financial input") from None
    if not number.is_finite() or number < 0:
        raise ValueError("Financial inputs must be finite and nonnegative")
    return number

def project_revenue(subscribers, price=DEFAULT_PRICE, fixed_cost=0, fee_pct=0,
                    fee_per_payment=0, variable_cost=0):
    """Hypothetical USD monthly model, one successful payment per subscriber."""
    n = _decimal(subscribers)
    price, fixed, pct, fee, variable = map(_decimal, (price, fixed_cost, fee_pct, fee_per_payment, variable_cost))
    if n != n.to_integral_value() or n > 10_000_000 or pct > 100:
        raise ValueError("Invalid subscriber count or fee percentage")
    if any(x > 1_000_000_000 for x in (price, fixed, fee, variable)):
        raise ValueError("Input exceeds supported range")
    gross = n * price
    fees = n * (price * pct / 100 + fee)
    contribution = price - (price * pct / 100 + fee + variable)
    operating = n * contribution - fixed
    minimum = (int((fixed / contribution).to_integral_value(rounding=ROUND_CEILING))
               if contribution > 0 else None)
    money = lambda x: x.quantize(CENT, rounding=ROUND_HALF_UP)
    return {"monthly_gross": money(gross), "annualized_gross": money(gross * 12),
            "monthly_payment_fees": money(fees), "monthly_variable_cost": money(n * variable),
            "monthly_fixed_cost": money(fixed), "monthly_operating_result": money(operating),
            "contribution_per_subscriber": money(contribution), "break_even_subscribers": minimum}

def checkout_diagnostics(url, fulfillment_flag):
    safe = validated_checkout_url(url)
    mode = ("missing" if not str(url or "").strip() else "invalid") if not safe else (
        "test" if is_test_checkout_url(safe) else "non_test")
    declared_ready = str(fulfillment_flag or "").strip().lower() in ("true", "1", "yes")
    return {"checkout_mode": mode, "fulfillment_declared_ready": declared_ready,
            "stripe_verified": False, "actual_revenue": None, "active_subscriptions": None}

def revenue_snapshot():
    import os
    from access_control import current_role
    if current_role() != "admin":
        return {"status": "denied"}
    import streamlit as st
    def setting(key):
        value = os.environ.get(key, "")
        if value.strip():
            return value
        try:
            return str(st.secrets.get(key, ""))
        except (FileNotFoundError, KeyError, AttributeError, RuntimeError):
            return ""
    return {"status":"ok", **checkout_diagnostics(setting("HOOPZARO_PREMIUM_CHECKOUT_URL"),
                  setting("HOOPZARO_PREMIUM_FULFILLMENT_READY"))}
