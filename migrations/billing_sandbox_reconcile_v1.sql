-- Additive grants only. Pre-create a dedicated LOGIN role with no other grants.
BEGIN;
DO $guard$
BEGIN
  IF current_database() <> 'hoopzaro_billing_sandbox' THEN
    RAISE EXCEPTION 'Wrong billing database';
  END IF;
END $guard$;
REVOKE ALL ON public.hz_sandbox_checkout,public.hz_sandbox_verification,
  public.hz_sandbox_webhook_events FROM hz_billing_sandbox_reconcile;
GRANT SELECT ON public.hz_sandbox_checkout TO hz_billing_sandbox_reconcile;
GRANT UPDATE(customer_id,subscription_id) ON public.hz_sandbox_checkout TO hz_billing_sandbox_reconcile;
GRANT SELECT,INSERT ON public.hz_sandbox_verification TO hz_billing_sandbox_reconcile;
GRANT UPDATE(checked_at,allowed,reason,expires_at) ON public.hz_sandbox_verification TO hz_billing_sandbox_reconcile;
COMMIT;
