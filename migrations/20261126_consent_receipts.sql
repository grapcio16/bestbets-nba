-- Review and apply only to hoopzaro_analytics after staging test.
-- No changes to existing account, quota, telemetry, tracker or billing rows.
BEGIN;
DO $$
BEGIN
    IF current_database() <> 'hoopzaro_analytics' THEN
        RAISE EXCEPTION 'Unexpected consent database';
    END IF;
END $$;
CREATE TABLE public.hz_session_consent (
    receipt_id uuid PRIMARY KEY,
    notice_version text NOT NULL CHECK (length(notice_version) BETWEEN 1 AND 80),
    notice_url text NOT NULL CHECK (length(notice_url) BETWEEN 1 AND 512),
    purpose text NOT NULL CHECK (purpose = 'optional_usage_analytics'),
    role text NOT NULL CHECK (role IN ('guest','free','premium')),
    accepted_at timestamptz NOT NULL DEFAULT now(),
    expires_at timestamptz NOT NULL DEFAULT (now() + interval '24 hours'),
    ended_at timestamptz,
    end_reason text CHECK (end_reason IN ('withdrawn','identity_changed','expired','disabled','logout')),
    CHECK (expires_at > accepted_at AND expires_at <= accepted_at + interval '24 hours'),
    CHECK ((ended_at IS NULL) = (end_reason IS NULL)),
    CHECK (ended_at IS NULL OR ended_at >= accepted_at)
);
CREATE TABLE public.hz_account_consent (
    receipt_id uuid PRIMARY KEY,
    account_id text NOT NULL CHECK (account_id ~ '^[0-9a-f]{64}$'),
    notice_version text NOT NULL CHECK (length(notice_version) BETWEEN 1 AND 80),
    notice_url text NOT NULL CHECK (length(notice_url) BETWEEN 1 AND 512),
    purpose text NOT NULL CHECK (purpose = 'optional_usage_analytics'),
    accepted_at timestamptz NOT NULL DEFAULT now(),
    expires_at timestamptz NOT NULL DEFAULT (now() + interval '24 hours'),
    ended_at timestamptz,
    end_reason text CHECK (end_reason IN ('withdrawn','identity_changed','expired','disabled','logout')),
    CHECK (expires_at > accepted_at AND expires_at <= accepted_at + interval '24 hours'),
    CHECK ((ended_at IS NULL) = (end_reason IS NULL)),
    CHECK (ended_at IS NULL OR ended_at >= accepted_at)
);
CREATE INDEX hz_account_consent_account_idx ON public.hz_account_consent(account_id,accepted_at);
REVOKE ALL ON public.hz_session_consent,public.hz_account_consent FROM PUBLIC,hz_analytics_reader,hz_analytics_writer;
GRANT INSERT ON public.hz_session_consent,public.hz_account_consent TO hz_analytics_writer;
GRANT SELECT(receipt_id,ended_at),UPDATE(ended_at,end_reason) ON public.hz_session_consent,public.hz_account_consent TO hz_analytics_writer;
COMMIT;
