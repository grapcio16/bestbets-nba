# Durable consent receipts — staged rollout
This change is not an authorization to enable customer tracking. The existing admin pilot remains independent. The old in-memory customer consent no longer qualifies.

## Database
Review migrations/20261126_consent_receipts.sql; apply first to a disposable staging database, then only after approval to hoopzaro_analytics as its owner. The migration is additive and transactional; no existing rows are deleted. Existing hz_analytics_writer receives INSERT and limited receipt-close permissions; hz_analytics_reader does not receive raw consent access. Verify effective inherited grants on Neon, not only explicit grants. Existing application DB connection is reused; do not copy secrets into chat or GitHub.

## Consent
Two independent receipt identifiers, no raw OIDC subject or email stored in SQL. A session receipt ID is used as the telemetry session ID; a separate receipt is stored for a pseudonymous account only if the account registry is configured. Timestamps may still permit correlation; these data are not anonymous. Both receipts commit before the local grant is enabled. Consent is session-only, maximum 24 hours; logout, identity/role change, changed notice and expiry invalidate it. Withdrawal clears the local grant and pending telemetry before DB I/O. If recording the withdrawal fails, the active server session retries at most once per 30 seconds on reruns; collection stays off. If the server session ends before retry succeeds, the receipt may retain no explicit withdrawal timestamp; expiry still bounds it, and no consent can be restored. This limitation requires operational follow-up before launch. Receipt timestamps on retries represent recorded closure, not necessarily the instant the user clicked.

## Activation gates
Keep HOOPZARO_USAGE_CUSTOMER_ENABLED=false. Only after final notice approval, published and accessible at a stable URL, and staging/database checks:
- HOOPZARO_USAGE_CONSENT_READY=true
- HOOPZARO_USAGE_NOTICE_VERSION=2026-11-26-v2
- HOOPZARO_USAGE_NOTICE_URL=https://hoopzaro.com/privacy (example only; must actually exist)
- HOOPZARO_USAGE_CUSTOMER_ENABLED=true (separate launch approval)
No draft notice should be exposed. The URL allowlist does not itself verify reachability or legal adequacy. Publish an immutable/versioned notice and retain evidence of the exact wording presented. Notice changes require a new version. Define and approve consent-receipt retention and handling of access/erasure requests separately; the existing analytics retention job does NOT delete receipts. Never enable unlimited receipt retention by accident. Verify staged opt-in and withdrawal with actual test accounts; monitor failure conditions. No checkout or account entitlement changes.
