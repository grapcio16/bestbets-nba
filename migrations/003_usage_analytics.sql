-- Dedicated analytics database only. No tracker schema changes.
BEGIN;
CREATE TABLE IF NOT EXISTS hoopzaro_accounts (
 account_id text PRIMARY KEY CHECK (account_id ~ '^[0-9a-f]{64}$'),
 first_seen_at timestamptz NOT NULL DEFAULT now(),
 last_seen_at timestamptz NOT NULL DEFAULT now(),
 last_observed_role text NOT NULL CHECK (last_observed_role IN ('free','premium','admin'))
);
CREATE TABLE IF NOT EXISTS hoopzaro_props_daily (
 account_id text NOT NULL REFERENCES hoopzaro_accounts(account_id) ON DELETE CASCADE,
 quota_day date NOT NULL, reservation_id uuid NOT NULL,
 reserved_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY(account_id,quota_day)
);
CREATE TABLE IF NOT EXISTS hz_usage_sessions (
 session_id uuid PRIMARY KEY,
 first_seen timestamptz NOT NULL DEFAULT now(),
 last_seen timestamptz NOT NULL DEFAULT now(),
 role text NOT NULL CHECK(role IN ('guest','free','premium','admin')),
 observed_seconds integer NOT NULL DEFAULT 0 CHECK(observed_seconds>=0)
);
CREATE INDEX IF NOT EXISTS hz_usage_sessions_seen_idx ON hz_usage_sessions(last_seen);
CREATE TABLE IF NOT EXISTS hz_usage_daily (
 day date NOT NULL, session_id uuid NOT NULL,
 page text NOT NULL CHECK(page IN ('home','props','games','simulations','players','teams','settings')),
 samples integer NOT NULL DEFAULT 1 CHECK(samples>0),
 PRIMARY KEY(day,session_id,page)
);
CREATE TABLE IF NOT EXISTS hz_feature_daily (
 day date NOT NULL, feature text NOT NULL CHECK(feature IN ('simulation','player_simulation','scenario','minutes','props','backtest')),
 outcome text NOT NULL CHECK(outcome IN ('success','failure')),
 calls bigint NOT NULL DEFAULT 1 CHECK(calls>0),
 total_ms bigint NOT NULL DEFAULT 0 CHECK(total_ms>=0),
 PRIMARY KEY(day,feature,outcome)
);
CREATE TABLE IF NOT EXISTS hoopzaro_admin_audit (
 event_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 actor_id text NOT NULL CHECK(actor_id ~ '^[0-9a-f]{64}$'),
 action text NOT NULL CHECK(action IN ('refresh_telemetry','review_access','review_models')),
 outcome text NOT NULL CHECK(outcome IN ('success','failure')),
 occurred_at timestamptz NOT NULL DEFAULT now()
);
COMMIT;
