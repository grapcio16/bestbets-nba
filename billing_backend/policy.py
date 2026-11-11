"""Fail-closed, paid-period entitlement policy. No trial or past-due grace."""
from dataclasses import dataclass

FREE_FEATURES = frozenset({'schedule', 'teams', 'players', 'injuries'})
PREMIUM_FEATURES = frozenset({'player-props', 'calculator', 'simulations'})


@dataclass(frozen=True)
class Decision:
    granted: bool = False
    status: str = 'free'
    paid_until: int = 0
    subscription_id: str | None = None
    cancel_at_period_end: bool = False


def expected_price(price, settings):
    recurring = price.get('recurring') or {}
    return (price.get('id') == settings.billing.price_id
        and price.get('livemode') is False and price.get('active') is True
        and price.get('currency') == 'usd' and price.get('unit_amount') == 1000
        and price.get('type') == 'recurring' and price.get('product') == settings.product_id
        and recurring.get('interval') == 'month' and recurring.get('interval_count') == 1
        and recurring.get('usage_type') == 'licensed')


def evaluate(sub, invoice, payment, charge, settings, user_id, customer_id, now):
    denied = Decision(status=str(sub.get('status') or 'invalid'))
    items = (sub.get('items') or {}).get('data') or []
    if (sub.get('livemode') is not False or sub.get('customer') != customer_id
        or sub.get('status') != 'active' or len(items) != 1
        or items[0].get('quantity') != 1 or not expected_price(items[0].get('price') or {}, settings)
        or (sub.get('metadata') or {}).get('internal_user_id') != user_id
        or sub.get('pause_collection')):
        return denied
    if (invoice.get('livemode') is not False or invoice.get('id') != sub.get('latest_invoice')
        or invoice.get('subscription') != sub.get('id') or invoice.get('customer') != customer_id
        or invoice.get('status') != 'paid' or invoice.get('currency') != 'usd'
        or invoice.get('amount_paid', 0) < 1000 or invoice.get('payment_intent') != payment.get('id')):
        return denied
    if (payment.get('livemode') is not False or payment.get('status') != 'succeeded'
        or payment.get('customer') != customer_id or payment.get('currency') != 'usd'
        or payment.get('invoice') != invoice.get('id')
        or payment.get('amount_received', 0) < 1000 or payment.get('latest_charge') != charge.get('id')):
        return denied
    if (charge.get('livemode') is not False or charge.get('customer') != customer_id
        or charge.get('payment_intent') != payment.get('id')
        or charge.get('currency') != 'usd' or charge.get('amount', 0) < 1000
        or charge.get('paid') is not True or charge.get('captured') is not True
        or charge.get('refunded') is not False or charge.get('amount_refunded') != 0
        or charge.get('disputed') is not False):
        return denied
    start, end = sub.get('current_period_start'), sub.get('current_period_end')
    if not isinstance(start, int) or not isinstance(end, int) or not start <= now < end:
        return denied
    lines = (invoice.get('lines') or {}).get('data') or []
    if (invoice.get('lines') or {}).get('has_more'):
        return denied
    matching = [line for line in lines if line.get('subscription') == sub.get('id')
        and (line.get('price') or {}).get('id') == settings.billing.price_id
        and line.get('quantity') == 1 and line.get('proration') is False
        and (line.get('period') or {}).get('start') == start
        and (line.get('period') or {}).get('end') == end]
    if len(matching) != 1:
        return denied
    cancel_at = sub.get('cancel_at')
    if isinstance(cancel_at, int):
        end = min(end, cancel_at)
    if end <= now:
        return denied
    return Decision(True, 'active', end, sub['id'], bool(sub.get('cancel_at_period_end')))
