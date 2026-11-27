# Scheduled sandbox reconciliation — v1

This workflow runs on main every 15 minutes, or on manual dispatch. GitHub schedules may be delayed. It updates a diagnostic snapshot only; a five-minute positive evidence expiry is NOT extended by the worker schedule and snapshots never grant access. The public app's access control remains unchanged. The tester app still verifies against current Stripe when open.

Before activation, verify the additive migration on disposable PostgreSQL; apply only to hoopzaro_billing_sandbox using an owner. Dedicated role hz_billing_sandbox_reconcile may read the checkout binding, bind customer/subscription IDs, and write the latest verification. It may not create a checkout, change its ID, delete data, or read the webhook inbox. Verify effective privileges and cross-database isolation in Neon. Keep no owner connection in GitHub.

GitHub Actions repository secret HOOPZARO_BILLING_RECONCILE_CONFIG contains JSON with exactly six fields:
```json
{
  "database_url": "postgresql://hz_billing_sandbox_reconcile:REPLACE@HOST/hoopzaro_billing_sandbox?sslmode=require",
  "stripe_key": "rk_test_REPLACE",
  "stripe_account": "acct_REPLACE",
  "price_id": "price_REPLACE",
  "product_id": "prod_REPLACE",
  "testers": ["REPLACE_WITH_EXISTING_64_CHARACTER_TESTER_ID"]
}
```

Use a new restricted test key with Read permissions for Accounts, Charges and Refunds, Checkout Sessions, Customers, Invoices, Payment Intents, Prices, Products and Subscriptions. No Write permissions. The worker additionally refuses all POST requests. Copy the tester ID and Stripe identifiers from the existing sandbox configuration; do not copy the HMAC secret, OAuth credentials or Checkout write key. Never put actual secret values in this file or chat.

Set repository variable HOOPZARO_BILLING_RECONCILE_ENABLED=true only after the secret exists and the migration has passed. Manually run Billing sandbox reconciliation on main and inspect aggregate counts. A verified count is expected for the current paid test subscription, subject to actual Stripe state. No charge is created by the workflow. Remove a tester from both the Streamlit allowlist and the worker config when access should be stopped. The worker does not independently synchronize those two allowlists. Max 10 test accounts. This is an interim sandbox polling solution; not a production webhook/event-driven reconciliation system. Real cancellation, refund and renewal still need provider tests; do not mutate the sole successful test subscription without explicit agreement.
