"""Signed Stripe sandbox event intake, independent WSGI endpoint.

This is an audit inbox, NOT an entitlement grant or reconciliation worker.
No event body, email, raw charge or card data is stored. On-demand sandbox
decision reads canonical API objects; webhook arrival alone never grants access.
"""
import os
from billing_sandbox_adapter import VERSION,ident
from billing_sandbox_store import db

EVENTS=frozenset(("checkout.session.completed","checkout.session.async_payment_succeeded",
 "checkout.session.async_payment_failed","invoice.paid","invoice.payment_failed",
 "customer.subscription.created","customer.subscription.updated","customer.subscription.deleted",
 "charge.refunded","charge.dispute.created","charge.dispute.closed"))
MAX_BYTES=262144

def receive(raw,signature,secret,account_id,record):
    import stripe
    if not isinstance(raw,bytes) or not 0<len(raw)<=MAX_BYTES or not isinstance(signature,str) or not 0<len(signature)<=4096:
        return 400
    if not isinstance(secret,str) or not secret.startswith("whsec_"):
        return 503
    try:
        event=stripe.Webhook.construct_event(raw,signature,secret,tolerance=300)
        if event.get("livemode") is not False or event.get("api_version")!=VERSION:
            return 400
        if event.get("account") not in (None,account_id):
            return 400
        event_id=ident(event.get("id"),"evt_")
        event_type=event.get("type")
        if not isinstance(event_type,str):
            return 400
    except Exception:
        return 400
    if event_type not in EVENTS:
        return 204
    try:
        record(event_id,event_type)
    except Exception:
        return 503
    return 204

def record_event(event_id,event_type):
    with db(os.environ["HOOPZARO_BILLING_SANDBOX_WEBHOOK_DATABASE_URL"]) as cur:
        cur.execute("""INSERT INTO public.hz_sandbox_webhook_events(event_id,event_type)
                      VALUES (%s,%s) ON CONFLICT(event_id) DO NOTHING""",(event_id,event_type))

def application(environ,start_response):
    status=503
    if environ.get("REQUEST_METHOD")!="POST" or environ.get("PATH_INFO")!="/stripe/sandbox":
        status=404
    elif os.environ.get("HOOPZARO_BILLING_SANDBOX_WEBHOOK_ENABLED")=="true":
        try:
            length=int(environ.get("CONTENT_LENGTH") or "0")
            if not 0<length<=MAX_BYTES:
                status=400
            else:
                body=environ["wsgi.input"].read(length)
                if len(body)!=length:
                    status=400
                else:
                    status=receive(body,environ.get("HTTP_STRIPE_SIGNATURE",""),
                            os.environ.get("HOOPZARO_BILLING_SANDBOX_WEBHOOK_SECRET",""),
                            os.environ.get("HOOPZARO_BILLING_SANDBOX_STRIPE_ACCOUNT",""),record_event)
        except Exception:
            status=503
    reason={204:"No Content",400:"Bad Request",404:"Not Found",503:"Service Unavailable"}[status]
    start_response(f"{status} {reason}",[("Content-Length","0"),("Cache-Control","no-store")])
    return [b""]
