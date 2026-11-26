-- Apply ONLY to a dedicated test database. Not hoopzaro_analytics/neondb.
BEGIN;
DO $guard$
BEGIN
  IF current_database() <> 'hoopzaro_billing_sandbox' THEN
    RAISE EXCEPTION 'Unexpected sandbox billing database';
  END IF;
END $guard$;
CREATE TABLE public.hz_sandbox_checkout (
  account_id text PRIMARY KEY CHECK (account_id ~ '^[0-9a-f]{64}$'),
  attempt_id uuid UNIQUE NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  checkout_id text UNIQUE CHECK (checkout_id ~ '^cs_test_[A-Za-z0-9_]{1,200}$'),
  customer_id text UNIQUE CHECK (customer_id ~ '^cus_[A-Za-z0-9_]{1,200}$'),
  subscription_id text UNIQUE CHECK (subscription_id ~ '^sub_[A-Za-z0-9_]{1,200}$'),
  CHECK ((customer_id IS NULL)=(subscription_id IS NULL)),
  CHECK (customer_id IS NULL OR checkout_id IS NOT NULL)
);
CREATE TABLE public.hz_sandbox_webhook_events (
  event_id text PRIMARY KEY CHECK (event_id ~ '^evt_[A-Za-z0-9_]{1,200}$'),
  event_type text NOT NULL CHECK (length(event_type) BETWEEN 1 AND 80),
  received_at timestamptz NOT NULL DEFAULT now()
);
REVOKE ALL ON public.hz_sandbox_checkout,public.hz_sandbox_webhook_events FROM PUBLIC;
-- Grant app role SELECT, INSERT on checkout, UPDATE only checkout_id/customer_id/subscription_id.
-- Grant webhook role INSERT on event table (and SELECT(event_id) for ON CONFLICT if required).
-- No shared application analytics writer, no privileges to delete or modify account keys.
COMMIT;
