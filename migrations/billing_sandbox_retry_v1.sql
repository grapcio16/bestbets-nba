-- Only for the isolated billing sandbox. No production access.
BEGIN;
DO $guard$
BEGIN
  IF current_database() <> 'hoopzaro_billing_sandbox' THEN
    RAISE EXCEPTION 'Wrong billing database';
  END IF;
END $guard$;
CREATE TABLE public.hz_sandbox_checkout_history (
  account_id text NOT NULL REFERENCES public.hz_sandbox_checkout(account_id),
  attempt_id uuid PRIMARY KEY,
  created_at timestamptz NOT NULL,
  checkout_id text UNIQUE NOT NULL CHECK (checkout_id ~ '^cs_test_[A-Za-z0-9_]{1,200}$'),
  customer_id text UNIQUE NOT NULL,
  subscription_id text UNIQUE NOT NULL,
  archived_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  final_reason text NOT NULL CHECK (final_reason='subscription_not_active')
);
REVOKE ALL ON public.hz_sandbox_checkout_history FROM PUBLIC,hz_billing_sandbox_app,hz_billing_sandbox_reconcile,hz_billing_sandbox_webhook;
CREATE FUNCTION public.hz_sandbox_prepare_retry(p_account text,p_old uuid,p_new uuid)
RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $fn$
DECLARE old_row public.hz_sandbox_checkout%ROWTYPE;
BEGIN
  IF current_database()<>'hoopzaro_billing_sandbox' OR p_old=p_new THEN RETURN false; END IF;
  SELECT * INTO old_row FROM public.hz_sandbox_checkout
    WHERE account_id=p_account AND attempt_id=p_old FOR UPDATE;
  IF NOT FOUND OR old_row.checkout_id IS NULL OR old_row.customer_id IS NULL OR old_row.subscription_id IS NULL THEN
    RETURN false;
  END IF;
  -- The trusted app separately verifies canonical Stripe status=canceled or
  -- incomplete_expired; a generic denied result alone is not sufficient.
  PERFORM 1 FROM public.hz_sandbox_verification WHERE account_id=p_account
    AND NOT allowed AND reason='subscription_not_active' AND expires_at IS NULL
    AND checked_at >= clock_timestamp()-interval '2 minutes' FOR UPDATE;
  IF NOT FOUND THEN RETURN false; END IF;
  IF EXISTS (SELECT 1 FROM public.hz_sandbox_checkout_history WHERE attempt_id=p_new) THEN RETURN false; END IF;
  INSERT INTO public.hz_sandbox_checkout_history(account_id,attempt_id,created_at,checkout_id,customer_id,subscription_id,final_reason)
    VALUES(old_row.account_id,old_row.attempt_id,old_row.created_at,old_row.checkout_id,old_row.customer_id,old_row.subscription_id,'subscription_not_active');
  UPDATE public.hz_sandbox_checkout SET attempt_id=p_new,created_at=clock_timestamp(),
    checkout_id=NULL,customer_id=NULL,subscription_id=NULL WHERE account_id=p_account;
  UPDATE public.hz_sandbox_verification SET checked_at=clock_timestamp(),allowed=false,
    reason='checkout_incomplete',expires_at=NULL WHERE account_id=p_account;
  RETURN true;
END $fn$;
REVOKE ALL ON FUNCTION public.hz_sandbox_prepare_retry(text,uuid,uuid) FROM PUBLIC,hz_billing_sandbox_reconcile,hz_billing_sandbox_webhook;
GRANT EXECUTE ON FUNCTION public.hz_sandbox_prepare_retry(text,uuid,uuid) TO hz_billing_sandbox_app;
COMMIT;
