# HOOPZARO: Premium paywall and administrator model report

## Premium modal

- A guest or free user attempting Player Props sees a centered, blurred-background
  Premium dialog instead of the previous red horizontal alert.
- The monthly price shown is **9.99 USD**. The popup contains benefits, a close
  control, Escape dismissal and keyboard focus handling.
- Server-side premium entitlement checks remain unchanged; the modal is only UI.
- When no verified Stripe destination is available, users see **Payments are
  being prepared** and can open Settings. No fake checkout URL is generated.

For test-mode checkout, set this Streamlit Secret (or environment variable):

```toml
HOOPZARO_PREMIUM_CHECKOUT_URL = "https://buy.stripe.com/test_REPLACE_WITH_REAL_LINK"
```

Only `https://buy.stripe.com/...` and `https://checkout.stripe.com/...` are
accepted. Test links are explicitly labeled **test mode** in the dialog.

**Do not enable real charges until purchases automatically activate Premium.**
Once the Stripe webhook/subscription fulfillment process is verified, explicitly
set `HOOPZARO_PREMIUM_FULFILLMENT_READY = true` and configure the production
checkout URL. A Stripe link does not itself update `access_control.py`'s
verified entitlement. Configuring a price does not implement subscription
renewal, cancellation, or account provisioning.

## Model Performance (admin only)

- A `Model Performance` navigation item appears only for a verified admin role.
- The report loads on demand from `TRACKER_DATABASE_URL`; credentials never
  travel to the frontend. The event handler verifies admin role on the server.
- It shows per-model archived count, finished count, audit-verified count,
  winner accuracy, total-score MAE, team-score MAE, Brier score and 30 recent
  frozen forecasts. The historical score is blank until a result is final.
- No estimates of a model's actual accuracy are shown before games finish.
- Reloads are rate-limited to 30 seconds. Other users receive no report data.

Tests:

```sh
python -m unittest test_admin_model_performance.py test_premium_checkout.py \
  test_performance_tracker.py test_access_control.py -q
```
