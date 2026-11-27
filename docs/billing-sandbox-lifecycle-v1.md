# Sandbox subscription lifecycle v1

- Active authenticated tester: verify on opening the app, manual refresh, and a Streamlit fragment every 60 seconds while the session is active.
- Each decision uses current Stripe Checkout/subscription/invoice/payment/charge evidence, not a persisted allow flag. Latest snapshot is diagnostic only. A read or write outage does not grant Premium.
- Denials distinguish incomplete checkout, non-active subscription and refund/dispute; remaining invalid API evidence fails closed.
- Store one last result per account in hz_sandbox_verification. Timestamp ordering rejects an older check overwriting a later result; positive evidence expires in at most five minutes from verification, capped by paid period. Verification taking more than 45 seconds fails closed.
- Existing test subscription is preserved. No public app entitlement or live Stripe change.
- Fixture tests cover renewal invoice, failed payment evidence, refund, cancellation, stale write and storage failure. Real Stripe renewal/refund/cancellation still need testing. For cancellation scheduled at period end, a still-active paid subscription remains eligible until its paid period ends.
- Apply migrations/billing_sandbox_lifecycle_v1.sql only to hoopzaro_billing_sandbox after PostgreSQL integration passes. No raw payment or card data is stored.
- This is not an always-on background worker. A closed browser session stops periodic verification. Existing signed webhook inbox has not been deployed, and event-driven reconciliation is not yet implemented. Production rollout requires separate review of access, subscription lifecycle and privacy retention.
