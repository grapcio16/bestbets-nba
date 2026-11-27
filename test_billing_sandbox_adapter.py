import copy
import hashlib
import importlib.util
import hmac
import json
import os
import time
import unittest
from datetime import datetime,timezone,timedelta
from unittest.mock import patch
from billing_sandbox_adapter import (BillingError,StripeTestAPI,canonical_evidence,create_checkout,VERSION)
from billing_sandbox_policy import decide_sandbox_access
from billing_sandbox_store import Attempt,SandboxService,tester_identity
from billing_sandbox_webhook import receive

A="00000000-0000-4000-8000-000000000001"
URL="https://hoopzaro-billing-sandbox.streamlit.app/"
ACCOUNT="a"*64
NOW=datetime.now(timezone.utc)
START=int((NOW-timedelta(days=1)).timestamp())
END=int((NOW+timedelta(days=29)).timestamp())
def obj(id,**fields):
    return {"id":id,"livemode":False,**fields}
PRICE=obj("price_fixture",product="prod_fixture",active=True,type="recurring",unit_amount=999,currency="usd",
          billing_scheme="per_unit",transform_quantity=None,recurring={"interval":"month","interval_count":1,"usage_type":"licensed"})
SESSION=obj("cs_test_fixture",client_reference_id=A,mode="subscription",status="complete",payment_status="paid",
            customer="cus_fixture",subscription="sub_fixture")
OBJECTS={
"price_fixture":PRICE,
"sub_fixture":obj("sub_fixture",customer="cus_fixture",status="active",collection_method="charge_automatically",
    items={"has_more":False,"data":[{"id":"si_fixture","subscription":"sub_fixture","quantity":1,"price":PRICE}]},
    latest_invoice="in_fixture",current_period_start=START,current_period_end=END),
"in_fixture":obj("in_fixture",customer="cus_fixture",subscription="sub_fixture",status="paid",paid=True,paid_out_of_band=False,
    billing_reason="subscription_create",collection_method="charge_automatically",amount_paid=999,amount_due=999,amount_remaining=0,
    currency="usd",total=999,subtotal=999,post_payment_credit_notes_amount=0,pre_payment_credit_notes_amount=0,
    total_discount_amounts=[],total_tax_amounts=[],payment_intent="pi_fixture",charge="ch_fixture",
    lines={"has_more":False,"data":[{"type":"subscription","subscription_item":"si_fixture","proration":False,"quantity":1,
    "amount":999,"currency":"usd","price":{"id":"price_fixture"},"period":{"start":START,"end":END}}]}),
"pi_fixture":obj("pi_fixture",customer="cus_fixture",latest_charge="ch_fixture",status="succeeded",amount_received=999,currency="usd"),
"ch_fixture":obj("ch_fixture",customer="cus_fixture",payment_intent="pi_fixture",invoice="in_fixture",status="succeeded",paid=True,captured=True,
    refunded=False,disputed=False,amount_refunded=0,amount=999,amount_captured=999,currency="usd",payment_method_details={"type":"card"}),
}
class API:
    def __init__(self):
        self.objects=copy.deepcopy(OBJECTS)
        self.session=copy.deepcopy(SESSION)
        self.requests=[]
    def verify_account(self): pass
    def get(self,kind,id,prefix):
        from billing_sandbox_adapter import test_object
        return test_object(self.session if id=="cs_test_fixture" else self.objects[id],id)
    def request(self,path,params,idempotency):
        self.requests.append((path,params,idempotency))
        return {**self.session,"status":"open","currency":"usd","amount_total":999,"url":"https://checkout.stripe.com/c/pay/cs_test_fixture#fixture"}
class AdapterTests(unittest.TestCase):
    def setUp(self): self.api=API()
    def evidence(self):
        return canonical_evidence(self.api,self.api.session,A,ACCOUNT,"price_fixture","prod_fixture",NOW)
    def test_canonical_payment(self):
        b,e=self.evidence()
        self.assertTrue(decide_sandbox_access(b,e,principal_hmac=ACCOUNT,configured_price_id="price_fixture",pilot_enabled=True,tester_allowed=True,now=NOW).allowed)
    def test_renewal_uses_latest_paid_invoice(self):
        # Simulated monthly renewal: original checkout stays bound, but the
        # subscription points to a new invoice and its own card payment.
        sub=self.api.objects["sub_fixture"]
        old=self.api.objects["in_fixture"]
        sub.update(latest_invoice="in_renewal",current_period_start=START,current_period_end=END)
        invoice=copy.deepcopy(old)
        invoice.update(id="in_renewal",billing_reason="subscription_cycle",payment_intent="pi_renewal",charge="ch_renewal")
        self.api.objects["in_renewal"]=invoice
        pi=copy.deepcopy(self.api.objects["pi_fixture"])
        pi.update(id="pi_renewal",latest_charge="ch_renewal")
        self.api.objects["pi_renewal"]=pi
        charge=copy.deepcopy(self.api.objects["ch_fixture"])
        charge.update(id="ch_renewal",payment_intent="pi_renewal",invoice="in_renewal")
        self.api.objects["ch_renewal"]=charge
        b,e=self.evidence()
        self.assertEqual(e.invoice_id,"in_renewal")
        self.assertTrue(decide_sandbox_access(b,e,principal_hmac=ACCOUNT,configured_price_id="price_fixture",pilot_enabled=True,tester_allowed=True,now=NOW).allowed)
        invoice["paid"]=False
        with self.assertRaises(BillingError):
            self.evidence()
    def test_deny_corrupt_objects(self):
        for id,fields in [("sub_fixture",{"status":"past_due"}),("sub_fixture",{"customer":"cus_other"}),("in_fixture",{"paid_out_of_band":True}),("in_fixture",{"amount_paid":0}),("in_fixture",{"post_payment_credit_notes_amount":1}),("in_fixture",{"livemode":True}),("pi_fixture",{"latest_charge":"ch_other"}),("ch_fixture",{"refunded":True}),("ch_fixture",{"disputed":True}),("ch_fixture",{"amount_refunded":1}),("ch_fixture",{"invoice":"in_other"})]:
            with self.subTest(id=id,fields=fields):
                self.api=API()
                self.api.objects[id].update(fields)
                with self.assertRaises(BillingError): self.evidence()
    def test_deny_forged_session(self):
        self.api.session["client_reference_id"]="other"
        with self.assertRaises(BillingError): self.evidence()
    def test_checkout_server_parameters(self):
        sid,url=create_checkout(self.api,A,"price_fixture","prod_fixture",URL)
        self.assertEqual(sid,"cs_test_fixture")
        path,params,key=self.api.requests[0]
        self.assertEqual(path,"/v1/checkout/sessions")
        self.assertEqual(params["line_items[0][price]"],"price_fixture")
        self.assertEqual(params["client_reference_id"],A)
        self.assertEqual(key,"hz-sandbox-standard-v2-"+A)
        self.assertEqual(params["managed_payments[enabled]"],"false")
        self.assertEqual(params["adaptive_pricing[enabled]"],"false")
        self.assertEqual(params["payment_method_types[0]"],"card")
        self.assertEqual(params["subscription_data[billing_mode][type]"],"classic")
        create_checkout(self.api,A,"price_fixture","prod_fixture",URL)
        self.assertEqual(self.api.requests[0],self.api.requests[1])
        self.assertNotIn("customer_email",params)
        with self.assertRaises(BillingError): create_checkout(self.api,A,"price_fixture","prod_fixture","https://example.org")
    def test_safe_http_diagnostics(self):
        from billing_sandbox_adapter import StripeRequestError
        from urllib.error import HTTPError
        from io import BytesIO
        api=StripeTestAPI("rk_test_fixture0123456789","acct_fixture")
        raw=b'{"error":{"type":"invalid_request_error","code":"parameter_unknown","message":"private_fixture"}}'
        with patch.object(api.opener,"open",side_effect=HTTPError("https://api.stripe.com",400,"private_fixture",{"Request-Id":"req_fixture"},BytesIO(raw))):
            with self.assertRaises(StripeRequestError) as caught:
                api.request("/v1/checkout/sessions",{})
        self.assertEqual(str(caught.exception),"Stripe HTTP 400 / invalid_request_error / parameter_unknown / req_fixture")
        self.assertNotIn("private_fixture",str(caught.exception))
    def test_unsafe_checkout_url_reports_stage(self):
        from billing_sandbox_adapter import CheckoutStageError
        original=self.api.request
        def bad(*args,**kwargs):
            return {**original(*args,**kwargs),"url":"https://evil.invalid/private_fixture"}
        with patch.object(self.api,"request",side_effect=bad):
            with self.assertRaisesRegex(CheckoutStageError,"session_url_format") as caught:
                create_checkout(self.api,A,"price_fixture","prod_fixture",URL)
        self.assertNotIn("private_fixture",str(caught.exception))
    def test_checkout_create_version_does_not_change_reads(self):
        from billing_sandbox_adapter import CHECKOUT_CREATE_VERSION
        from unittest.mock import MagicMock
        api=StripeTestAPI("rk_test_fixture0123456789","acct_fixture")
        response=MagicMock()
        response.__enter__.return_value.read.return_value=b'{}'
        with patch.object(api.opener,"open",return_value=response) as op:
            api.request("/v1/checkout/sessions",{},idempotency="fixture")
            api.request("/v1/invoices/in_fixture")
        self.assertEqual(op.call_args_list[0].args[0].get_header("Stripe-version"),CHECKOUT_CREATE_VERSION)
        self.assertEqual(op.call_args_list[1].args[0].get_header("Stripe-version"),VERSION)
    def test_checkout_hosted_url_variants(self):
        from billing_sandbox_adapter import checkout_url
        sid="cs_test_fixture"
        for route in ("/c/pay/","/pay/","/c/subscribe/","/subscribe/"):
            url="https://checkout.stripe.com"+route+sid+"?locale=pl#opaque%2Ftoken"
            self.assertEqual(checkout_url(url,sid),url)
        for url in ("http://checkout.stripe.com/c/pay/"+sid,
                    "https://checkout.stripe.com.evil.invalid/c/pay/"+sid,
                    "https://checkout.stripe.com@evil.invalid/c/pay/"+sid,
                    "https://evil.invalid@checkout.stripe.com/c/pay/"+sid,
                    "https://checkout.stripe.com/c/pay/cs_test_other",
                    "https://checkout.stripe.com/c/../"+sid,
                    "https://checkout.stripe.com/c/pay/"+sid+"%2Fother",
                    "https://checkout.stripe.com/c/pay/"+sid+"\n"):
            with self.subTest(url=url),self.assertRaises(BillingError):
                checkout_url(url,sid)
    def test_live_secret_rejected(self):
        with self.assertRaises(BillingError): StripeTestAPI("sk_live_not_a_real_secret","acct_fixture")
    def test_wrong_price_rejected_before_creation(self):
        self.api.objects["price_fixture"]["unit_amount"]=1000
        with self.assertRaises(BillingError): create_checkout(self.api,A,"price_fixture","prod_fixture",URL)
        self.assertEqual(self.api.requests,[])

class FakeStore:
    def __init__(self,account):
        self.attempt=Attempt(account,A,NOW,None,None,None)
        self.bound=None
        self.verifications=[]
    def reserve(self,account):
        assert self.attempt.account_id==account
        return self.attempt
    def get(self,account):
        return self.attempt if account==self.attempt.account_id else None
    def save_checkout(self,a,sid):
        from dataclasses import replace
        self.attempt=replace(a,checkout_id=sid)
    def bind_subscription(self,a,b):
        self.bound=b
    def prepare_retry(self,a):
        self.prepared=a
        return True
    def record_verification(self,aid,checked_at,result,attempt_id=None):
        self.verifications.append((aid,checked_at,result))
        return True

class ServiceTests(unittest.TestCase):
    def test_retry_requires_terminal_bound_subscription(self):
        from dataclasses import replace
        principal="issuer|subject"
        key="x"*32
        aid=hmac.new(key.encode(),principal.encode(),hashlib.sha256).hexdigest()
        env={"HOOPZARO_BILLING_SANDBOX_ENABLED":"true","HOOPZARO_BILLING_SANDBOX_HMAC_KEY":key,"HOOPZARO_BILLING_SANDBOX_TESTERS":aid}
        with patch.dict(os.environ,env,clear=True):
            store=FakeStore(aid);api=API()
            service=SandboxService(store,api,"price_fixture","prod_fixture",URL)
            store.attempt=replace(store.attempt,checkout_id="cs_test_fixture",customer_id="cus_fixture",subscription_id="sub_fixture")
            for status in ("active","past_due","paused","incomplete","unpaid"):
                api.objects["sub_fixture"]["status"]=status
                with self.assertRaises(BillingError): service.prepare_retry(principal)
            api.objects["sub_fixture"]["status"]="canceled"
            with self.assertRaises(BillingError): service.prepare_retry("issuer|other")
            api.objects["sub_fixture"]["customer"]="cus_other"
            with self.assertRaises(BillingError): service.prepare_retry(principal)
            api.objects["sub_fixture"]["customer"]="cus_fixture"
            self.assertTrue(service.prepare_retry(principal))
            self.assertEqual(store.prepared,store.attempt)
            self.assertEqual(api.requests,[])

    def test_url_failure_saves_session_and_resume_never_creates_again(self):
        from billing_sandbox_adapter import CheckoutStageError
        principal="issuer|subject"
        key="x"*32
        aid=hmac.new(key.encode(),principal.encode(),hashlib.sha256).hexdigest()
        env={"HOOPZARO_BILLING_SANDBOX_ENABLED":"true","HOOPZARO_BILLING_SANDBOX_HMAC_KEY":key,"HOOPZARO_BILLING_SANDBOX_TESTERS":aid}
        with patch.dict(os.environ,env,clear=True):
            store=FakeStore(aid);api=API();service=SandboxService(store,api,"price_fixture","prod_fixture",URL)
            original=api.request
            def bad(*args,**kwargs):
                return {**original(*args,**kwargs),"url":"https://evil.invalid/private_fixture"}
            with patch.object(api,"request",side_effect=bad):
                with self.assertRaises(CheckoutStageError):
                    service.start(principal)
            self.assertEqual(store.attempt.checkout_id,"cs_test_fixture")
            self.assertEqual(len(api.requests),1)
            valid="https://checkout.stripe.com/c/subscribe/cs_test_fixture?locale=pl#opaque"
            api.session.update(status="open",currency="usd",amount_total=999,url=valid)
            self.assertEqual(service.start(principal),valid)
            self.assertEqual(len(api.requests),1)
            api.session["amount_total"]=1000
            with self.assertRaises(BillingError):
                service.start(principal)
            self.assertEqual(len(api.requests),1)

    def test_testers_only_and_fresh_api_evidence(self):
        key="x"*32
        principal="issuer|subject"
        aid=hmac.new(key.encode(),principal.encode(),hashlib.sha256).hexdigest()
        env={"HOOPZARO_BILLING_SANDBOX_ENABLED":"true","HOOPZARO_BILLING_SANDBOX_HMAC_KEY":key,"HOOPZARO_BILLING_SANDBOX_TESTERS":aid}
        with patch.dict(os.environ,env,clear=True):
            store=FakeStore(aid);api=API();service=SandboxService(store,api,"price_fixture","prod_fixture",URL)
            self.assertIsNone(tester_identity("issuer|other"))
            self.assertFalse(service.decision("issuer|other").allowed)
            self.assertFalse(service.decision(principal).allowed)
            service.start(principal)
            self.assertTrue(service.decision(principal).allowed)
            api.objects["ch_fixture"]["refunded"]=True
            result=service.decision(principal)
            self.assertFalse(result.allowed)
            self.assertEqual(result.reason,"refund_or_dispute")
            self.assertEqual(store.verifications[-1][2],result)
            api.objects["ch_fixture"]["refunded"]=False
            api.objects["sub_fixture"]["status"]="canceled"
            self.assertEqual(service.decision(principal).reason,"subscription_not_active")
            api.objects["sub_fixture"]["status"]="active"
            with patch.object(store,"record_verification",return_value=False):
                self.assertFalse(service.decision(principal).allowed)
            with patch.object(store,"record_verification",side_effect=RuntimeError("offline")):
                self.assertFalse(service.decision(principal).allowed)
            with self.assertRaises(BillingError): service.start("issuer|other")

@unittest.skipUnless(importlib.util.find_spec('stripe') is not None,'Stripe SDK installed by dedicated billing QA')
class WebhookTests(unittest.TestCase):
    def test_signature_mode_version_and_storage(self):
        secret="whsec_fixture"
        ev={"id":"evt_fixture","object":"event","type":"invoice.paid","livemode":False,"api_version":VERSION,"data":{"object":{"id":"in_fixture"}}}
        seen=set()
        def call(payload,sign=True,record=lambda i,t:seen.add((i,t)),age=0):
            raw=json.dumps(payload).encode();ts=int(time.time())-age
            sig=hmac.new(secret.encode(),str(ts).encode()+b"."+raw,hashlib.sha256).hexdigest()
            return receive(raw,f"t={ts},v1={sig if sign else '0'*64}",secret,"acct_fixture",record)
        self.assertEqual(call(ev),204)
        self.assertEqual(call(ev),204)
        self.assertEqual(len(seen),1)
        self.assertEqual(call(ev,False),400)
        self.assertEqual(call({**ev,"livemode":True}),400)
        self.assertEqual(call({**ev,"api_version":"other"}),400)
        self.assertEqual(call(ev,age=600),400)
        def unavailable(*args): raise RuntimeError("offline")
        self.assertEqual(call(ev,record=unavailable),503)
if __name__=="__main__": unittest.main()
