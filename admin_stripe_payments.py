"""Read-only Stripe sandbox charge aggregates. Never expose individual records."""
import os
import re
from datetime import datetime, timezone, timedelta
from collections import defaultdict
from decimal import Decimal

def stripe_payment_summary(get=None, now=None):
    from access_control import current_role
    if current_role()!="admin":
        return {"status":"denied"}
    key=os.environ.get("HOOPZARO_STRIPE_TEST_READ_KEY","").strip()
    if not key:
        return {"status":"setup_required"}
    if not key.startswith("rk_test_"):
        return {"status":"test_restricted_key_required"}
    try:
        if get is None:
            import requests
            get=requests.get
        now=now or datetime.now(timezone.utc)
        end=int(now.timestamp())
        start=int((now-timedelta(days=30)).timestamp())
        totals=defaultdict(lambda:{"captured_minor":0,"refunded_minor":0,"successful":0,"failed":0,"other":0})
        seen=set()
        cursor=None
        for _ in range(5):
            params={"limit":100,"created[gte]":start,"created[lt]":end}
            if cursor:
                params["starting_after"]=cursor
            response=get("https://api.stripe.com/v1/charges",params=params,
                         auth=(key,""),timeout=(3,5),allow_redirects=False)
            if response.status_code!=200:
                return {"status":"unavailable"}
            payload=response.json()
            rows=payload.get("data")
            if not isinstance(rows,list) or type(payload.get("has_more")) is not bool:
                return {"status":"unavailable"}
            for row in rows:
                ident=row.get("id")
                currency=row.get("currency")
                captured=row.get("amount_captured")
                refunded=row.get("amount_refunded")
                stamp=row.get("created")
                status=row.get("status")
                if (row.get("livemode") is not False or not isinstance(ident,str) or not ident.startswith("ch_")
                    or ident in seen or not isinstance(currency,str) or not re.fullmatch("[a-z]{3}",currency)
                    or type(stamp) is not int or not start<=stamp<end
                    or type(captured) is not int or type(refunded) is not int or not 0<=refunded<=captured
                    or status not in ("succeeded","failed","pending")
                    or type(row.get("paid")) is not bool or type(row.get("captured")) is not bool):
                    return {"status":"unavailable"}
                seen.add(ident)
                bucket=totals[currency]
                if status=="succeeded" and row["paid"] and row["captured"]:
                    bucket["successful"]+=1
                    bucket["captured_minor"]+=captured
                    bucket["refunded_minor"]+=refunded
                elif status=="failed":
                    bucket["failed"]+=1
                else:
                    bucket["other"]+=1
            if not payload["has_more"]:
                return {"status":"ok","mode":"test","currencies":dict(totals),
                        "checked_utc":now.isoformat(),"days":30}
            if not rows:
                return {"status":"unavailable"}
            cursor=rows[-1]["id"]
        return {"status":"page_limit_reached"}
    except Exception:
        return {"status":"unavailable"}

def money_label(amount,currency):
    # Explicitly supported display denominations. Other currencies stay in
    # Stripe API units rather than assuming all currencies have two decimals.
    code=str(currency).upper()
    if code in ("USD","EUR","PLN","GBP","CAD","AUD","CHF"):
        return f"{Decimal(amount)/100:,.2f} {code}"
    return f"{amount:,} jedn. API ({code})"

def payment_rows(report):
    if report.get("status")!="ok":
        return []
    return [{"Waluta":c.upper(),"Pobrano (test)":money_label(v["captured_minor"],c),
             "Zwroty (test)":money_label(v["refunded_minor"],c),
             "Udane":v["successful"],"Nieudane":v["failed"],"Pozostałe":v["other"]}
             for c,v in sorted(report.get("currencies",{}).items())]
