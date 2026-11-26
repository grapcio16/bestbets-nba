-- Apply only to an isolated QA database until production review.
BEGIN;
CREATE TABLE IF NOT EXISTS hoopzaro_admin_audit (
    event_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    actor_id TEXT NOT NULL CHECK (actor_id ~ '^[0-9a-f]{64}$'),
    action TEXT NOT NULL CHECK (action IN ('refresh_telemetry','review_access','review_models')),
    outcome TEXT NOT NULL CHECK (outcome IN ('success','failure'))
);
CREATE INDEX IF NOT EXISTS hoopzaro_admin_audit_recent
    ON hoopzaro_admin_audit (occurred_at DESC, event_id DESC);
COMMIT;
