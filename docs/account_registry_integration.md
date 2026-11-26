# Account registry / Free Props — integration gate

This branch adds an opt-in persistence layer only. The public app does not call it, and no production database migration has been executed.

- Use a dedicated server-only account database URL and a stable randomly generated HMAC key of at least 32 bytes. Never commit either. Loss or rotation of the key changes account IDs; plan migration before rotation.
- Record only a verified OIDC issuer/subject pseudonym, first and last observed timestamp, and last observed role. The role snapshot never grants entitlement. No email, raw OIDC claim, IP or password is persisted.
- Registry counts will describe observed signed-in accounts since activation, not all accounts registered at the identity provider. Define retention, deletion process, disclosure and lawful basis before enabling collection. Pseudonyms remain personal data.
- A unique (account_id, quota_day) constraint atomically admits one request per account. The provisional reset is midnight UTC, not local browser time. Guests must log in. Multiple separate identities remain a potential abuse vector.
- Validate query before reserving; keep reservation token entirely server-side; publish a result only after reservation succeeds. On a confirmed failure before disclosure, refund that exact reservation. A process crash or ambiguous DB commit may leave a quota consumed until the next day; do not automatically refund an uncertain result.
- Bind any Free result cache to the verified account and quota date; clear it on identity change and date rollover. Do not use the Premium entitlement flag to expose any other paid output.
- Preserve current OIDC roles, Premium checkout and admin bypass. Never use a browser-supplied role, date or identity as authority.
- Before launch: disposable PostgreSQL concurrency tests, real server integration tests, browser tests, privacy review, controlled migration/rollback plan, and explicit feature enablement. No production writes until these gates are cleared.
