"""Test-only Stripe transport and canonical evidence adapter.

Pinned API 2024-06-20 uses invoice.charge/payment_intent and legacy line.price.
Never called by the public app. No client-supplied identity or payment evidence.
"""
import base64
import json
import re
import time
from datetime import datetime,timezone
from urllib.parse import urlencode,urlsplit,unquote
from urllib.request import Request,build_opener,HTTPRedirectHandler
from urllib.error import HTTPError
from billing_sandbox_policy import CheckoutBinding,SandboxEvidence,decide_sandbox_access,Decision

VERSION="2024-06-20"
# Managed Payments opt-out is supported by the newer Checkout API.
# Keep reads pinned to the legacy invoice/charge schema.
CHECKOUT_CREATE_VERSION="2026-07-29.dahlia"
PRICE=999
CURRENCY="usd"
class BillingError(Exception): pass

class StripeRequestError(BillingError):
    """Only allowlisted metadata. Never expose raw Stripe errors or URL secrets."""
    def __init__(self,status,kind="",code="",request_id=""):
        self.status=status if type(status) is int and 100<=status<=599 else 0
        self.kind=kind if kind in ("invalid_request_error","authentication_error","api_error","idempotency_error","rate_limit_error","card_error","permission_error") else "other"
        self.code=code if code in ("api_key_expired","secret_key_required","resource_missing","parameter_missing","parameter_unknown","parameter_invalid_empty","parameter_invalid_string_blank","parameter_invalid_integer","url_invalid","payment_method_unactivated","account_invalid","account_country_invalid","idempotency_key_in_use","rate_limit","permission_denied") else "other"
        self.request_id=request_id if isinstance(request_id,str) and re.fullmatch(r"req_[A-Za-z0-9]{1,100}",request_id) else ""
        super().__init__("Stripe HTTP "+str(self.status)+" / "+self.kind+" / "+self.code
                         + (" / "+self.request_id if self.request_id else ""))

class CheckoutStageError(BillingError):
    def __init__(self,stage):
        super().__init__("Checkout: "+stage)
class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):
        return None

def require(ok):
    if not ok:
        raise BillingError("Sandbox evidence invalid")

def ident(value,prefix):
    require(isinstance(value,str) and re.fullmatch(re.escape(prefix)+r"[A-Za-z0-9_]{1,200}",value))
    return value

def one(data):
    require(isinstance(data,dict) and data.get("has_more") is False)
    items=data.get("data")
    require(isinstance(items,list) and len(items)==1 and isinstance(items[0],dict))
    return items[0]

def test_object(obj,expected_id):
    require(isinstance(obj,dict) and obj.get("id")==expected_id and obj.get("livemode") is False)
    return obj

def stripe_price(p,price_id,product_id):
    test_object(p,price_id)
    require(p.get("product")==product_id and p.get("active") is True and p.get("type")=="recurring"
            and p.get("unit_amount")==PRICE and p.get("currency")==CURRENCY
            and p.get("billing_scheme")=="per_unit" and p.get("transform_quantity") is None
            and p.get("recurring",{}).get("interval")=="month"
            and p.get("recurring",{}).get("interval_count")==1
            and p.get("recurring",{}).get("usage_type")=="licensed")

def approved_return_url(url):
    u=urlsplit(url)
    # Exact isolated deployment target; never a browser-provided redirect.
    require(u.scheme=="https" and u.netloc=="hoopzaro-billing-sandbox.streamlit.app"
            and u.path in ("","/") and not u.query and not u.fragment)
    return url

def checkout_url(url,session_id):
    # Stripe returns an opaque hosted URL from its authenticated API.
    # Do not reconstruct it or reject its optional query/fragment. Restrict
    # origin and bind its final path component to the verified test session.
    ident(session_id,"cs_test_")
    require(isinstance(url,str) and 0<len(url)<=16384
            and not re.search(r"[\\\x00-\x20\x7f]",url))
    try:
        u=urlsplit(url)
        segments=u.path.split("/")
        decoded=unquote(segments[-1],errors="strict")
    except (ValueError,UnicodeError):
        raise BillingError("Sandbox evidence invalid") from None
    require(u.scheme=="https" and u.netloc=="checkout.stripe.com"
            and segments[0]=="" and 3<=len(segments)<=5
            and all(re.fullmatch(r"[a-zA-Z0-9_-]+",s) for s in segments[1:-1])
            and decoded==session_id)
    return url

class StripeTestAPI:
    def __init__(self,key,account_id):
        require(isinstance(key,str) and key.startswith(("sk_test_","rk_test_")) and len(key)>16)
        self.key=key
        self.account_id=ident(account_id,"acct_")
        self.opener=build_opener(NoRedirect())
    def request(self,path,params=None,idempotency=None):
        require(re.fullmatch(r"/v1/[A-Za-z0-9_/]+",path) is not None)
        body=urlencode(params).encode() if params is not None else None
        headers={"Authorization":"Basic "+base64.b64encode((self.key+":").encode()).decode(),
                 "Stripe-Version":CHECKOUT_CREATE_VERSION if path=="/v1/checkout/sessions" and params is not None else VERSION,"Content-Type":"application/x-www-form-urlencoded"}
        if idempotency:
            headers["Idempotency-Key"]=idempotency
        try:
            with self.opener.open(Request("https://api.stripe.com"+path,data=body,headers=headers),timeout=8) as resp:
                raw=resp.read(1048577)
            require(len(raw)<=1048576)
            obj=json.loads(raw)
            require(isinstance(obj,dict))
            return obj
        except HTTPError as exc:
            details={}
            try:
                parsed=json.loads(exc.read(65536))
                if isinstance(parsed,dict) and isinstance(parsed.get("error"),dict):
                    details=parsed["error"]
            except Exception:
                pass
            raise StripeRequestError(exc.code,details.get("type"),details.get("code"),
                                     exc.headers.get("Request-Id","") if exc.headers else "") from None
        except Exception:
            raise BillingError("Sandbox API unavailable or unexpected") from None
    def verify_account(self):
        require(self.request("/v1/account").get("id")==self.account_id)
    def get(self,kind,id,prefix):
        return test_object(self.request("/v1/"+kind+"/"+ident(id,prefix)),id)

def create_checkout(api,attempt_id,price_id,product_id,return_url,save_session=None):
    require(re.fullmatch(r"[0-9a-f-]{36}",attempt_id) is not None)
    ident(price_id,"price_");ident(product_id,"prod_")
    approved_return_url(return_url)
    api.verify_account()
    stripe_price(api.get("prices",price_id,"price_"),price_id,product_id)
    params={"mode":"subscription","line_items[0][price]":price_id,"line_items[0][quantity]":"1",
            "payment_method_types[0]":"card","client_reference_id":attempt_id,
            "success_url":return_url,"cancel_url":return_url,
            "allow_promotion_codes":"false","automatic_tax[enabled]":"false",
            "managed_payments[enabled]":"false","adaptive_pricing[enabled]":"false",
            "subscription_data[billing_mode][type]":"classic"}
    # v2 cutover: the only v1 attempt was explicitly rejected (HTTP 400),
    # confirmed in Stripe logs; no session or subscription was bound.
    # Keep a single stable v2 key for every retry; never auto-rotate.
    s=api.request("/v1/checkout/sessions",params,idempotency="hz-sandbox-standard-v2-"+attempt_id)
    try:
        sid=ident(s.get("id"),"cs_test_")
        validate_session(s,sid,attempt_id)
    except BillingError:
        raise CheckoutStageError("session_identity_or_mode") from None
    if s.get("status")!="open":
        raise CheckoutStageError("session_not_open")
    if s.get("currency")!=CURRENCY or s.get("amount_total")!=PRICE:
        raise CheckoutStageError("session_currency_or_amount")
    # Persist the verified session before inspecting its URL, so a URL error
    # can never force a new checkout or lose the existing session binding.
    if save_session is not None:
        save_session(sid)
    try:
        url=checkout_url(s.get("url"),sid)
    except BillingError:
        raise CheckoutStageError("session_url_format") from None
    return sid,url

def validate_session(s,sid,attempt_id):
    test_object(s,ident(sid,"cs_test_"))
    require(s.get("client_reference_id")==attempt_id and s.get("mode")=="subscription"
            and not s.get("payment_link"))

def retrieve_checkout(api,sid,attempt_id):
    api.verify_account()
    s=api.get("checkout/sessions",sid,"cs_test_")
    validate_session(s,sid,attempt_id)
    return s

def timestamp(value):
    require(type(value) is int and 0<value<4102444800)
    return datetime.fromtimestamp(value,timezone.utc)

def canonical_evidence(api,session,attempt_id,account_id,price_id,product_id,now=None):
    sid=ident(session.get("id"),"cs_test_")
    validate_session(session,sid,attempt_id)
    require(session.get("status")=="complete" and session.get("payment_status")=="paid")
    cus=ident(session.get("customer"),"cus_")
    subid=ident(session.get("subscription"),"sub_")
    sub=api.get("subscriptions",subid,"sub_")
    require(sub.get("customer")==cus and sub.get("status")=="active"
            and sub.get("collection_method")=="charge_automatically"
            and not sub.get("pause_collection") and not sub.get("pending_update"))
    item=one(sub.get("items"))
    stripe_price(item.get("price"),price_id,product_id)
    itemid=ident(item.get("id"),"si_")
    require(item.get("quantity")==1 and item.get("subscription")==subid)
    invoiceid=ident(sub.get("latest_invoice"),"in_")
    invoice=api.get("invoices",invoiceid,"in_")
    require(invoice.get("customer")==cus and invoice.get("subscription")==subid
            and invoice.get("status")=="paid" and invoice.get("paid") is True
            and invoice.get("paid_out_of_band") is False
            and invoice.get("billing_reason") in ("subscription_create","subscription_cycle")
            and invoice.get("collection_method")=="charge_automatically"
            and invoice.get("amount_paid")==PRICE and invoice.get("amount_due")==PRICE
            and invoice.get("amount_remaining")==0 and invoice.get("currency")==CURRENCY
            and invoice.get("total")==PRICE and invoice.get("subtotal")==PRICE
            and invoice.get("post_payment_credit_notes_amount")==0
            and invoice.get("pre_payment_credit_notes_amount")==0
            and not invoice.get("total_discount_amounts") and not invoice.get("total_tax_amounts"))
    line=one(invoice.get("lines"))
    require(line.get("type")=="subscription" and line.get("subscription_item")==itemid
            and line.get("proration") is False and line.get("quantity")==1
            and line.get("amount")==PRICE and line.get("currency")==CURRENCY
            and isinstance(line.get("price"),dict) and line["price"].get("id")==price_id)
    start=timestamp(line.get("period",{}).get("start"))
    end=timestamp(line.get("period",{}).get("end"))
    require(start==timestamp(sub.get("current_period_start")) and end==timestamp(sub.get("current_period_end")))
    piid=ident(invoice.get("payment_intent"),"pi_")
    chargeid=ident(invoice.get("charge"),"ch_")
    pi=api.get("payment_intents",piid,"pi_")
    require(pi.get("customer")==cus and pi.get("latest_charge")==chargeid
            and pi.get("status")=="succeeded" and pi.get("amount_received")==PRICE and pi.get("currency")==CURRENCY)
    charge=api.get("charges",chargeid,"ch_")
    require(charge.get("customer")==cus and charge.get("payment_intent")==piid
            and charge.get("invoice")==invoiceid and charge.get("status")=="succeeded"
            and charge.get("paid") is True and charge.get("captured") is True
            and charge.get("refunded") is False and charge.get("disputed") is False
            and charge.get("amount_refunded")==0 and charge.get("amount")==PRICE
            and charge.get("amount_captured")==PRICE and charge.get("currency")==CURRENCY
            and charge.get("payment_method_details",{}).get("type")=="card")
    binding=CheckoutBinding(account_id,sid,cus,subid,price_id)
    evidence=SandboxEvidence(False,sid,cus,subid,price_id,"active",invoiceid,True,True,True,PRICE,CURRENCY,True,start,end,now or datetime.now(timezone.utc))
    return binding,evidence
