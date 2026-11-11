# BestBets × Stripe — sandbox development (NOT a live rollout)

This is an **isolated test-only gateway** in `stripe_test_billing.py`. It is not
imported by `app.py` or the existing custom Streamlit screen. It does not
create Stripe products, customers, prices or subscriptions by itself.

## Business / compliance first

BestBets provides NBA statistics plus analytics of betting markets and player props. Stripe's
restricted/prohibited list includes gambling categories, including sports forecasting or
odds-making involving monetary/material prizes and other gambling-related activities. The
product's precise scope and jurisdiction must be disclosed, not described merely as a
generic analytics tool. Before enabling production billing, obtain **explicit confirmation
from Stripe** that the actual BestBets business model can be supported. Also obtain
qualified advice regarding Polish/EEA rules on digital subscriptions, advertising,
consumer cancellation, VAT and privacy.

- Stripe business policy: https://stripe.com/en-pl/legal/restricted-businesses
- Stripe Checkout: https://docs.stripe.com/api/checkout/sessions/create
- Customer portal: https://docs.stripe.com/customer-management
- Signature verification: https://docs.stripe.com/events/set-up-events

## Setup for Codex (test environment)

1. Use branch `feature/stripe-subscriptions-test-only-20261111`. **Do not modify main.**
2. Run `python -m pip install -r requirements-stripe-test.txt`.
3. Set the following values as local environment variables or an ignored `.env` file
   loaded by your chosen application runner. Never paste secrets in chats or source files.

   - `STRIPE_TEST_SECRET_KEY=sk_test_...` (rotate any key visible in a screenshot)
   - `STRIPE_TEST_PRICE_ID=price_...` (a TEST recurring Stripe Price created in Dashboard)
   - `STRIPE_TEST_WEBHOOK_SECRET=whsec_...` (the TEST event destination secret)
   - `BESTBETS_APP_URL=https://bestbets-nba.streamlit.app` (future return URL)

4. Run offline tests: `python -m unittest -v test_stripe_test_billing.py`.
5. Import the module only into a **separate authenticated backend** when ready.
   Currently BestBets has no verified user authentication, subscription persistence,
   or publicly reachable webhook endpoint. Do not add a "Purchase" button yet.

## What's implemented

`StripeTestGateway` provides:
- `create_checkout(authenticated_user_id,request_id,verified_customer_id=None,...)`:
  a Stripe-hosted **test** subscription checkout URL, subscription metadata and
  idempotency key. The user ID **must be supplied by server authentication**, and
  customer IDs must come from that user's trusted DB record, not request parameters.
- `create_customer_portal(verified_customer_id,authenticated_user_id)`:
  a sandbox portal URL. Again, verify ownership from a trusted data store.
- `verify_webhook(raw_body,signature)`: uses Stripe's signature verification on
  the raw body, rejects live events and returns normalized event data.
- `has_premium_access(status)`: status helper, NEVER a substitute for server
  authentication, reconciliation, paid invoice checks or subscription storage.

## Minimum requirements before integrating into production

1. Authenticating users: account ID from a verified server-side session (e.g., Firebase
   Auth ID token verified on the server); never trust a client-supplied ID.
2. Persistent database: maps `user_id -> stripe_customer_id -> stripe_subscription_id`;
   unique constraints; no Streamlit `session_state` as the payment record.
3. A public backend webhook route with signature verification using the exact raw
   payload; idempotent event ID processing in a DB transaction; out-of-order event
   reconciliation (retrieve current Stripe subscription state before changing access).
4. Grant Premium only when the **authenticated** user has an active or trialing
   verified subscription to the **correct Price/Product**, and revoke as required.
   Do not grant access based solely on the Checkout success URL or `checkout.session.completed`.
5. The portal route must retrieve the Stripe customer by authenticated user ID;
   never accept customer IDs from a browser form.
6. Restrict redirect URLs to approved HTTPS app origins; implement CSRF protections,
   logging without secrets/PII, rate limiting and cancellation flows.
7. Product/legal approval, GDPR documentation, consumer-facing terms and support.
8. Full sandbox lifecycle tests: first successful payment, SCA, failed renewals,
   retries, cancellation, late/out-of-order webhooks, duplicated webhook deliveries
   and multiple tabs.
9. Only after all gates are satisfied, build a **separate reviewed live-money adapter**.
   This test module deliberately rejects `sk_live_` keys and `livemode=true`.

## Notes for Codex

Codex should start from this document, build authenticated API endpoints on a separate
branch and demonstrate end-to-end tests locally. **Do not merge into main, deploy
production subscriptions, or put billing secrets in the GitHub repository.**
