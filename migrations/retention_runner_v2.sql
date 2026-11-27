-- Review separately; never apply to a production DB automatically.
-- Requires a dedicated LOGIN role hz_retention_runner with no other grants.
-- Create the role out-of-band and keep its credentials in GitHub Actions.
BEGIN;
DO $guard$
BEGIN
  IF current_database() <> 'hoopzaro_analytics' THEN
    RAISE EXCEPTION 'Wrong database';
  END IF;
END $guard$;
CREATE SCHEMA hz_retention;
REVOKE ALL ON SCHEMA hz_retention FROM PUBLIC;
CREATE FUNCTION hz_retention.cleanup()
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
SET lock_timeout = '2s'
SET statement_timeout = '15s'
AS $body$
DECLARE
  pages integer;
  sessions integer;
  features integer;
  accounts integer;
  locked_accounts text[];
BEGIN
  IF current_database() <> 'hoopzaro_analytics' THEN
    RAISE EXCEPTION 'Wrong database';
  END IF;
  -- Same order as telemetry writes. Protect against orphan pages since the
  -- deployed usage_daily table does not have a session foreign key.
  LOCK TABLE public.hz_usage_sessions, public.hz_usage_daily IN SHARE ROW EXCLUSIVE MODE;
  DELETE FROM public.hz_usage_daily d
  WHERE d.ctid IN (
    SELECT x.ctid FROM public.hz_usage_daily x
    WHERE x.day < (now() AT TIME ZONE 'UTC')::date - 29
    ORDER BY x.day LIMIT 5000
  );
  GET DIAGNOSTICS pages = ROW_COUNT;
  DELETE FROM public.hz_usage_sessions s
  WHERE s.session_id IN (
    SELECT x.session_id FROM public.hz_usage_sessions x
    WHERE x.last_seen < now()-interval '30 days'
    AND NOT EXISTS (SELECT 1 FROM public.hz_usage_daily d WHERE d.session_id=x.session_id)
    ORDER BY x.last_seen LIMIT 5000
  );
  GET DIAGNOSTICS sessions = ROW_COUNT;
  DELETE FROM public.hz_feature_daily d
  WHERE d.ctid IN (
    SELECT x.ctid FROM public.hz_feature_daily x
    WHERE x.day < (now() AT TIME ZONE 'UTC')::date - 89
    ORDER BY x.day LIMIT 5000
  );
  GET DIAGNOSTICS features = ROW_COUNT;
  -- A table lock on the quota table would invert the FK insertion lock order.
  -- Instead lock at most 5000 eligible parent rows, then re-check the FK in
  -- a new statement snapshot before deleting. Never delete quota rows.
  SELECT array_agg(account_id::text) INTO locked_accounts FROM (
    SELECT x.account_id FROM public.hoopzaro_accounts x
    WHERE x.last_seen_at < now()-interval '90 days'
    AND NOT EXISTS (SELECT 1 FROM public.hoopzaro_props_daily q WHERE q.account_id=x.account_id)
    ORDER BY x.last_seen_at,x.account_id LIMIT 5000 FOR UPDATE
  ) locked;
  DELETE FROM public.hoopzaro_accounts a
  WHERE a.account_id = ANY(locked_accounts)
    AND a.last_seen_at < now()-interval '90 days'
    AND NOT EXISTS (SELECT 1 FROM public.hoopzaro_props_daily q WHERE q.account_id=a.account_id);
  GET DIAGNOSTICS accounts = ROW_COUNT;
  RETURN jsonb_build_object('page_samples',pages,'sessions',sessions,
    'feature_aggregates',features,'inactive_accounts',accounts);
END;
$body$;
REVOKE ALL ON FUNCTION hz_retention.cleanup() FROM PUBLIC;
GRANT USAGE ON SCHEMA hz_retention TO hz_retention_runner;
GRANT EXECUTE ON FUNCTION hz_retention.cleanup() TO hz_retention_runner;
COMMIT;
