BEGIN;
DO $guard$
BEGIN
  IF current_database() <> 'hoopzaro_billing_sandbox' THEN
    RAISE EXCEPTION 'Wrong billing database';
  END IF;
END $guard$;
CREATE TABLE public.hz_sandbox_verification (
  account_id text PRIMARY KEY REFERENCES public.hz_sandbox_checkout(account_id),
  checked_at timestamptz NOT NULL,
  allowed boolean NOT NULL,
  reason text NOT NULL CHECK (reason IN ('verified_sandbox_payment','checkout_incomplete','subscription_not_active','refund_or_dispute','payment_not_confirmed','verification_unavailable_or_invalid','account_mismatch','environment_mismatch','invalid_binding','binding_mismatch','price_mismatch','unsupported_amount','invalid_time','stale_evidence','invalid_paid_period','missing_evidence','pilot_disabled')),
  expires_at timestamptz,
  CHECK ((allowed AND reason='verified_sandbox_payment' AND expires_at>checked_at AND expires_at<=checked_at+interval '6 minutes') OR
         (NOT allowed AND reason<>'verified_sandbox_payment' AND expires_at IS NULL))
);
REVOKE ALL ON public.hz_sandbox_verification FROM PUBLIC,hz_billing_sandbox_app,hz_billing_sandbox_webhook;
GRANT SELECT,INSERT ON public.hz_sandbox_verification TO hz_billing_sandbox_app;
GRANT UPDATE(checked_at,allowed,reason,expires_at) ON public.hz_sandbox_verification TO hz_billing_sandbox_app;
COMMIT;
