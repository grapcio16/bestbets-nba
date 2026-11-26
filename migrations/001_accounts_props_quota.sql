-- Explicit migration for isolated test database first.
-- Do not execute against production until approved and reviewed.
BEGIN;
CREATE TABLE IF NOT EXISTS hoopzaro_accounts (
    account_id TEXT PRIMARY KEY CHECK (account_id ~ '^[0-9a-f]{64}$'),
    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_observed_role TEXT NOT NULL CHECK (last_observed_role IN ('free','premium','admin'))
);
CREATE TABLE IF NOT EXISTS hoopzaro_props_daily (
    account_id TEXT NOT NULL REFERENCES hoopzaro_accounts(account_id) ON DELETE CASCADE,
    quota_day DATE NOT NULL,
    reservation_id UUID NOT NULL,
    reserved_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (account_id, quota_day)
);
COMMIT;
