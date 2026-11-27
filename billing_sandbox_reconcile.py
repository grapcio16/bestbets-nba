"""Scheduled sandbox-only reconciliation. Never creates a Checkout or grants public Premium."""
import json
import os
import re
from collections import Counter
from urllib.parse import urlsplit,unquote
from billing_sandbox_adapter import StripeTestAPI,BillingError,ident,stripe_price
from billing_sandbox_store import Store,SandboxService,db

class ReadOnlyStripe(StripeTestAPI):
    def request(self,path,params=None,idempotency=None):
        if params is not None or idempotency is not None:
            raise BillingError("Worker cannot mutate Stripe")
        return super().request(path)

def parse_config(raw):
    cfg=json.loads(raw)
    expected={"database_url","stripe_key","stripe_account","price_id","product_id","testers"}
    if not isinstance(cfg,dict) or set(cfg)!=expected:
        raise ValueError("Invalid config")
    u=urlsplit(cfg["database_url"])
    if (u.scheme not in ("postgres","postgresql") or not u.hostname
            or unquote(u.username or "")!="hz_billing_sandbox_reconcile"
            or u.path!="/hoopzaro_billing_sandbox" or not u.password):
        raise ValueError("Invalid database role")
    if not re.fullmatch(r"rk_test_[A-Za-z0-9_]{10,}",cfg["stripe_key"]):
        raise ValueError("Restricted test key required")
    for key,prefix in (("stripe_account","acct_"),("price_id","price_"),("product_id","prod_")):
        ident(cfg[key],prefix)
    testers=cfg["testers"]
    if (not isinstance(testers,list) or not 1<=len(testers)<=10
            or any(not isinstance(v,str) or not re.fullmatch("[0-9a-f]{64}",v) for v in testers)
            or len(set(testers))!=len(testers)):
        raise ValueError("Invalid tester allowlist")
    return cfg

def verify_role(url):
    with db(url) as cur:
        cur.execute("""SELECT current_user,
          has_table_privilege(current_user,'public.hz_sandbox_checkout','SELECT'),
          has_table_privilege(current_user,'public.hz_sandbox_checkout','INSERT'),
          has_column_privilege(current_user,'public.hz_sandbox_checkout','checkout_id','UPDATE'),
          has_table_privilege(current_user,'public.hz_sandbox_checkout','DELETE'),
          has_table_privilege(current_user,'public.hz_sandbox_verification','INSERT'),
          has_table_privilege(current_user,'public.hz_sandbox_verification','DELETE'),
          has_table_privilege(current_user,'public.hz_sandbox_webhook_events','SELECT')""")
        if cur.fetchone()!=("hz_billing_sandbox_reconcile",True,False,False,False,True,False,False):
            raise ValueError("Unexpected worker privileges")

def reconcile(config):
    verify_role(config["database_url"])
    api=ReadOnlyStripe(config["stripe_key"],config["stripe_account"])
    api.verify_account()
    stripe_price(api.get("prices",config["price_id"],"price_"),config["price_id"],config["product_id"])
    service=SandboxService(Store(config["database_url"]),api,config["price_id"],
                           config["product_id"],"https://hoopzaro-billing-sandbox.streamlit.app/")
    counts=Counter()
    for aid in config["testers"]:
        result=service.reconcile_account(aid)
        counts["verified" if result.allowed else "denied"]+=1
        if result.reason in ("verification_unavailable_or_invalid","stale_evidence"):
            counts["verification_errors"]+=1
        elif result.reason=="missing_checkout":
            counts["missing_checkout"]+=1
    return dict(counts)

def main():
    if os.environ.get("HOOPZARO_BILLING_RECONCILE_ENABLED")!="true":
        print("Sandbox reconciliation disabled")
        return 0
    try:
        counts=reconcile(parse_config(os.environ["HOOPZARO_BILLING_RECONCILE_CONFIG"]))
        print(json.dumps({"sandbox_only":True,"counts":counts},sort_keys=True))
        return 1 if counts.get("verification_errors") else 0
    except Exception:
        # Never print secrets, URLs, account IDs, or arbitrary API errors.
        print("Sandbox reconciliation failed: configuration, privileges, or API unavailable")
        return 1

if __name__=="__main__":
    raise SystemExit(main())
