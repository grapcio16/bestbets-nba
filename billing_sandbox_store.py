"""Persistent checkout ownership for isolated sandbox. No production grants."""
from dataclasses import dataclass
from datetime import datetime,timezone,timedelta
from uuid import uuid4
from contextlib import contextmanager
import hmac
import hashlib
import os
import re
from billing_sandbox_policy import Decision,decide_sandbox_access
from billing_sandbox_adapter import (BillingError,LifecycleError,require,create_checkout,retrieve_checkout,
                                     checkout_url,canonical_evidence,ident)

@dataclass(frozen=True)
class Attempt:
    account_id: str
    attempt_id: str
    created_at: datetime
    checkout_id: str | None
    customer_id: str | None
    subscription_id: str | None

def tester_identity(principal):
    # Must be invoked with verified server-side OIDC principal, never email or URL.
    key=os.environ.get("HOOPZARO_BILLING_SANDBOX_HMAC_KEY","").encode()
    if (os.environ.get("HOOPZARO_BILLING_SANDBOX_ENABLED","")!="true"
        or len(key)<32 or not isinstance(principal,str) or principal=="guest" or "|" not in principal):
        return None
    aid=hmac.new(key,principal.encode(),hashlib.sha256).hexdigest()
    allowed={x.strip() for x in os.environ.get("HOOPZARO_BILLING_SANDBOX_TESTERS","").split(",")
             if re.fullmatch("[0-9a-f]{64}",x.strip())}
    return aid if aid in allowed else None

@contextmanager
def db(url):
    import psycopg
    with psycopg.connect(url,connect_timeout=4) as conn,conn.cursor() as cur:
        cur.execute("SELECT current_database()")
        require(cur.fetchone()[0]=="hoopzaro_billing_sandbox")
        cur.execute("SET LOCAL statement_timeout='6s'")
        cur.execute("SET LOCAL lock_timeout='2s'")
        yield cur

class Store:
    def __init__(self,url):
        self.url=url
    @staticmethod
    def _row(row):
        return Attempt(row[0],str(row[1]),*row[2:]) if row else None
    def get(self,aid):
        with db(self.url) as cur:
            cur.execute("""SELECT account_id,attempt_id,created_at,checkout_id,customer_id,subscription_id
                           FROM public.hz_sandbox_checkout WHERE account_id=%s""",(aid,))
            return self._row(cur.fetchone())
    def reserve(self,aid):
        with db(self.url) as cur:
            cur.execute("""INSERT INTO public.hz_sandbox_checkout(account_id,attempt_id)
                           VALUES (%s,%s) ON CONFLICT(account_id) DO NOTHING""",(aid,str(uuid4())))
            cur.execute("""SELECT account_id,attempt_id,created_at,checkout_id,customer_id,subscription_id
                           FROM public.hz_sandbox_checkout WHERE account_id=%s""",(aid,))
            row=self._row(cur.fetchone())
            require(row is not None)
            return row
    def save_checkout(self,a,sid):
        ident(sid,"cs_test_")
        with db(self.url) as cur:
            cur.execute("""UPDATE public.hz_sandbox_checkout SET checkout_id=%s
                 WHERE account_id=%s AND attempt_id=%s AND (checkout_id IS NULL OR checkout_id=%s)""",
                 (sid,a.account_id,a.attempt_id,sid))
            require(cur.rowcount==1)
    def bind_subscription(self,a,b):
        require(a.account_id==b.account_id and a.checkout_id==b.checkout_id)
        with db(self.url) as cur:
            cur.execute("""UPDATE public.hz_sandbox_checkout SET customer_id=%s,subscription_id=%s
                 WHERE account_id=%s AND attempt_id=%s AND checkout_id=%s
                 AND (customer_id IS NULL OR (customer_id=%s AND subscription_id=%s))""",
                 (b.customer_id,b.subscription_id,a.account_id,a.attempt_id,b.checkout_id,b.customer_id,b.subscription_id))
            require(cur.rowcount==1)

    def prepare_retry(self,a):
        with db(self.url) as cur:
            cur.execute("SELECT public.hz_sandbox_prepare_retry(%s,%s,%s)",
                        (a.account_id,a.attempt_id,str(uuid4())))
            return cur.fetchone()[0] is True

    def record_verification(self,aid,checked_at,result,attempt_id=None):
        # Display/audit snapshot only, never an authorization cache.
        # An older concurrent check may not overwrite a newer check.
        with db(self.url) as cur:
            if attempt_id is not None:
                cur.execute("SELECT attempt_id FROM public.hz_sandbox_checkout WHERE account_id=%s FOR UPDATE",(aid,))
                row=cur.fetchone()
                if not row or str(row[0])!=attempt_id:
                    return False
            cur.execute("""INSERT INTO public.hz_sandbox_verification
               (account_id,checked_at,allowed,reason,expires_at)
               VALUES (%s,%s,%s,%s,%s)
               ON CONFLICT(account_id) DO UPDATE SET checked_at=EXCLUDED.checked_at,
                 allowed=EXCLUDED.allowed,reason=EXCLUDED.reason,expires_at=EXCLUDED.expires_at
               WHERE hz_sandbox_verification.checked_at<=EXCLUDED.checked_at""",
               (aid,checked_at,result.allowed,result.reason,result.expires_at))
            return cur.rowcount==1

class SandboxService:
    def __init__(self,store,api,price_id,product_id,return_url):
        self.store,self.api=store,api
        self.price_id,self.product_id,self.return_url=price_id,product_id,return_url
    def start(self,principal):
        aid=tester_identity(principal)
        require(aid is not None)
        a=self.store.reserve(aid)
        if a.checkout_id:
            s=retrieve_checkout(self.api,a.checkout_id,a.attempt_id)
            require(s.get("status")=="open" and s.get("currency")=="usd" and s.get("amount_total")==999)
            return checkout_url(s.get("url"),a.checkout_id)
        # Never create another checkout on an uncertain retry after this window.
        # Stripe idempotency retention is finite; manual sandbox review is required.
        require(timedelta(0)<=datetime.now(timezone.utc)-a.created_at<timedelta(hours=1))
        sid,url=create_checkout(self.api,a.attempt_id,self.price_id,self.product_id,self.return_url,
                                save_session=lambda sid:self.store.save_checkout(a,sid))
        return url
    def prepare_retry(self,principal):
        aid=tester_identity(principal)
        require(aid is not None)
        a=self.store.get(aid)
        require(a is not None and a.checkout_id and a.customer_id and a.subscription_id)
        s=retrieve_checkout(self.api,a.checkout_id,a.attempt_id)
        require(s.get("status")=="complete" and s.get("customer")==a.customer_id
                and s.get("subscription")==a.subscription_id)
        sub=self.api.get("subscriptions",a.subscription_id,"sub_")
        # An active, scheduled-to-cancel, paused, unpaid or unknown state
        # must never unlock a second purchase. Only terminal cancellation.
        require(sub.get("customer")==a.customer_id and sub.get("status")=="canceled")
        result=self.reconcile_account(aid)
        require(not result.allowed and result.reason=="subscription_not_active")
        return self.store.prepare_retry(a)

    def decision(self,principal):
        aid=tester_identity(principal)
        if aid is None:
            return Decision(False,"pilot_disabled")
        return self.reconcile_account(aid)

    def reconcile_account(self,aid):
        """Internal server-only verifier; caller must authorize the account.
        For the worker this is an explicit sandbox-only tester allowlist.
        Never expose as a browser route or production access gate.
        """
        if not isinstance(aid,str) or not re.fullmatch("[0-9a-f]{64}",aid):
            return Decision(False,"account_mismatch")
        try:
            a=self.store.get(aid)
        except Exception:
            return Decision(False,"verification_unavailable_or_invalid")
        if a is None or a.checkout_id is None:
            return Decision(False,"missing_checkout")
        checked_at=datetime.now(timezone.utc)
        try:
            s=retrieve_checkout(self.api,a.checkout_id,a.attempt_id)
            binding,evidence=canonical_evidence(self.api,s,a.attempt_id,aid,self.price_id,self.product_id)
            self.store.bind_subscription(a,binding)
            result=decide_sandbox_access(binding,evidence,principal_hmac=aid,
                     configured_price_id=self.price_id,pilot_enabled=True,tester_allowed=True)
        except LifecycleError as exc:
            result=Decision(False,exc.reason)
        except Exception:
            result=Decision(False,"verification_unavailable_or_invalid")
        # Do not publish an affirmative result after a slow verification or
        # failed/stale database write. Never reuse an earlier affirmative row.
        now=datetime.now(timezone.utc)
        if result.allowed and (now-checked_at>timedelta(seconds=45) or result.expires_at<=now):
            result=Decision(False,"stale_evidence")
        try:
            if not self.store.record_verification(aid,checked_at,result,a.attempt_id):
                return Decision(False,"stale_evidence")
        except Exception:
            return Decision(False,"verification_unavailable_or_invalid")
        return result
