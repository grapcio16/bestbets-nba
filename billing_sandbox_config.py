"""Safe, tester-only configuration diagnostics. Never return secret values."""
from urllib.parse import urlsplit,unquote
from billing_sandbox_adapter import ident,approved_return_url,StripeTestAPI,stripe_price
import re

PREFIX="HOOPZARO_BILLING_SANDBOX_"
FIELDS=("STRIPE_KEY","STRIPE_ACCOUNT","DATABASE_URL","PRICE_ID","PRODUCT_ID","RETURN_URL")

def load_config(env):
    values={}
    problems={}
    for name in FIELDS:
        full=PREFIX+name
        raw=env.get(full)
        if not isinstance(raw,str) or not raw.strip():
            problems[full]="Brak wartości."
            continue
        value=raw.strip()
        try:
            if name=="STRIPE_KEY":
                if not re.fullmatch(r"(?:rk|sk)_test_[A-Za-z0-9_]{10,}",value):
                    raise ValueError()
            elif name in ("STRIPE_ACCOUNT","PRICE_ID","PRODUCT_ID"):
                ident(value,{"STRIPE_ACCOUNT":"acct_","PRICE_ID":"price_","PRODUCT_ID":"prod_"}[name])
            elif name=="RETURN_URL":
                approved_return_url(value)
            elif name=="DATABASE_URL":
                u=urlsplit(value)
                if (u.scheme not in ("postgresql","postgres") or not u.hostname
                    or unquote(u.username or "")!="hz_billing_sandbox_app"
                    or u.path!="/hoopzaro_billing_sandbox" or not u.password):
                    raise ValueError()
        except Exception:
            problems[full]={
                "STRIPE_KEY":"Oczekiwany pełny klucz testowy rk_test_ lub sk_test_. Nie używaj klucza live ani pk_test_.",
                "STRIPE_ACCOUNT":"Oczekiwany sam identyfikator acct_, bez adresu URL, ukośnika i /test/.",
                "DATABASE_URL":"Oczekiwane połączenie PostgreSQL do hoopzaro_billing_sandbox jako hz_billing_sandbox_app.",
                "PRICE_ID":"Oczekiwany sam identyfikator price_.",
                "PRODUCT_ID":"Oczekiwany sam identyfikator prod_.",
                "RETURN_URL":"Oczekiwany adres https://hoopzaro-billing-sandbox.streamlit.app/."
            }[name]
            continue
        values[name]=value
    return values,problems

def check_connections(config):
    """No writes, no Checkout session creation, no payment."""
    checks={}
    try:
        import psycopg
        with psycopg.connect(config["DATABASE_URL"],connect_timeout=4) as conn,conn.cursor() as cur:
            cur.execute("SET TRANSACTION READ ONLY")
            cur.execute("SET LOCAL statement_timeout=\x275s\x27")
            cur.execute("""SELECT current_database(),current_user,
                has_table_privilege(current_user,'public.hz_sandbox_checkout','SELECT'),
                has_table_privilege(current_user,'public.hz_sandbox_checkout','INSERT'),
                has_column_privilege(current_user,'public.hz_sandbox_checkout','checkout_id','UPDATE'),
                has_table_privilege(current_user,'public.hz_sandbox_checkout','DELETE')""")
            if cur.fetchone()!=("hoopzaro_billing_sandbox","hz_billing_sandbox_app",True,True,True,False):
                raise ValueError()
        checks["Neon"]="OK"
    except Exception:
        checks["Neon"]="Błąd połączenia lub uprawnień. Sprawdź DATABASE_URL."
    try:
        api=StripeTestAPI(config["STRIPE_KEY"],config["STRIPE_ACCOUNT"])
        api.verify_account()
        checks["Stripe / konto"]="OK"
    except Exception:
        checks["Stripe / konto"]="Błąd klucza, uprawnienia Accounts Read lub niezgodny STRIPE_ACCOUNT."
        return checks
    try:
        product=api.get("products",config["PRODUCT_ID"],"prod_")
        if product.get("active") is not True:
            raise ValueError()
        checks["Stripe / produkt"]="OK"
    except Exception:
        checks["Stripe / produkt"]="Błąd PRODUCT_ID, Products Read lub nieaktywny produkt testowy."
    try:
        stripe_price(api.get("prices",config["PRICE_ID"],"price_"),config["PRICE_ID"],config["PRODUCT_ID"])
        checks["Stripe / cena"]="OK"
    except Exception:
        checks["Stripe / cena"]="Sprawdź PRICE_ID, Prices Read i aktywną cenę 9.99 USD co miesiąc."
    return checks
