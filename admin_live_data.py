"""Production-shaped, bounded read-only aggregates for Control Center.
No secrets, account identifiers, raw forecasts or Stripe customer details returned.
"""
from datetime import datetime, timezone
import os

def _read(url, queries):
    if not url:
        return {"status":"setup_required"}
    try:
        import psycopg
        from psycopg.rows import dict_row
        with psycopg.connect(url, connect_timeout=5, row_factory=dict_row,
                options="-c statement_timeout=5000 -c default_transaction_read_only=on") as conn:
            with conn.cursor() as cur:
                result={"status":"ok"}
                for name,sql,params in queries:
                    cur.execute(sql,params)
                    result[name]=[dict(row) for row in cur.fetchall()]
        return result
    except Exception:
        return {"status":"unavailable"}

def tracker_summary(url,season):
    return _read(url,[
        ("players","""SELECT model_id, count(*) AS archived,
            count(*) FILTER (WHERE settled_at_utc >= start_utc AND forecast_time_utc < start_utc
                AND pts_actual IS NOT NULL AND reb_actual IS NOT NULL AND ast_actual IS NOT NULL) AS settled,
            round(avg(abs(pts_pred-pts_actual)) FILTER (WHERE settled_at_utc >= start_utc AND forecast_time_utc < start_utc)::numeric,2) AS pts_mae,
            round(avg(abs(reb_pred-reb_actual)) FILTER (WHERE settled_at_utc >= start_utc AND forecast_time_utc < start_utc)::numeric,2) AS reb_mae,
            round(avg(abs(ast_pred-ast_actual)) FILTER (WHERE settled_at_utc >= start_utc AND forecast_time_utc < start_utc)::numeric,2) AS ast_mae
            FROM bestbets_player_forecasts WHERE season=%s GROUP BY model_id ORDER BY model_id""",(season,)),
        ("quarters","""SELECT model_id,count(*) AS archived,
            count(*) FILTER (WHERE settled_at_utc >= start_utc AND forecast_time_utc < start_utc
                AND home_actual IS NOT NULL AND away_actual IS NOT NULL) AS settled,
            round(avg((abs(home_points-home_actual)+abs(away_points-away_actual))/2.0)
                FILTER (WHERE settled_at_utc >= start_utc AND forecast_time_utc < start_utc)::numeric,2) AS team_points_mae
            FROM bestbets_quarter_forecasts WHERE season=%s GROUP BY model_id ORDER BY model_id""",(season,)),
        ("last_run","""SELECT finished_at_utc,team_new,team_settled,player_new,player_settled,player_status
            FROM bestbets_tracker_runs WHERE season=%s ORDER BY finished_at_utc DESC LIMIT 1""",(season,))
    ])

def account_summary():
    from access_control import current_role
    if current_role()!="admin":
        return {"status":"denied"}
    url=os.environ.get("HOOPZARO_ACCOUNT_DATABASE_URL","").strip()
    return _read(url,[
        ("accounts","""SELECT last_observed_role,count(*) AS observed_accounts,
            count(*) FILTER (WHERE last_seen_at >= now()-interval '30 days') AS seen_last_30_days
            FROM hoopzaro_accounts GROUP BY last_observed_role ORDER BY last_observed_role""",()),
        ("quota","""SELECT count(*) AS reservations_today FROM hoopzaro_props_daily
            WHERE quota_day=(now() AT TIME ZONE 'UTC')::date""",())
    ])

def stripe_test_summary(get=None):
    """Opt-in restricted TEST key only. Counts are test records, not revenue.
    Bounded pagination; incomplete result never presented as account totals.
    """
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
        counts={}
        cursor=None
        for _ in range(5):
            params={"limit":100,"status":"all"}
            if cursor:
                params["starting_after"]=cursor
            response=get("https://api.stripe.com/v1/subscriptions",params=params,
                         auth=(key,""),timeout=(3,5),allow_redirects=False)
            if response.status_code!=200:
                return {"status":"unavailable"}
            payload=response.json()
            data=payload.get("data")
            if not isinstance(data,list) or type(payload.get("has_more")) is not bool:
                return {"status":"unavailable"}
            for row in data:
                if row.get("livemode") is not False or not isinstance(row.get("id"),str):
                    return {"status":"unavailable"}
                status=row.get("status")
                if status not in {"active","trialing","past_due","canceled","unpaid","incomplete","incomplete_expired","paused"}:
                    return {"status":"unavailable"}
                counts[status]=counts.get(status,0)+1
            if not payload["has_more"]:
                return {"status":"ok","mode":"test","subscription_counts":counts,
                        "checked_utc":datetime.now(timezone.utc).isoformat()}
            if not data or data[-1]["id"]==cursor:
                return {"status":"unavailable"}
            cursor=data[-1]["id"]
        return {"status":"page_limit_reached"}
    except Exception:
        return {"status":"unavailable"}
