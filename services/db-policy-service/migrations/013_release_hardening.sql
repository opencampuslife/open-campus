-- Migration 013: pilot release hardening audit metadata and worker health.

ALTER TABLE operation_logs
    ADD COLUMN IF NOT EXISTS actor_type TEXT NOT NULL DEFAULT 'user',
    ADD COLUMN IF NOT EXISTS request_id TEXT,
    ADD COLUMN IF NOT EXISTS ip_address TEXT,
    ADD COLUMN IF NOT EXISTS user_agent TEXT,
    ADD COLUMN IF NOT EXISTS metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb;

CREATE INDEX IF NOT EXISTS idx_operation_logs_action_created
    ON operation_logs (action, created_at DESC);

CREATE TABLE IF NOT EXISTS worker_heartbeats (
    worker_name TEXT PRIMARY KEY,
    school_id TEXT REFERENCES schools(school_id) ON DELETE SET NULL,
    last_heartbeat_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    status TEXT NOT NULL DEFAULT 'running',
    metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb
);

ALTER TABLE worker_heartbeats ENABLE ROW LEVEL SECURITY;
ALTER TABLE worker_heartbeats FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS p_worker_heartbeats_admin ON worker_heartbeats;
CREATE POLICY p_worker_heartbeats_admin ON worker_heartbeats
FOR ALL TO gaokao_api_admin
USING (true)
WITH CHECK (true);

GRANT SELECT, INSERT, UPDATE, DELETE ON worker_heartbeats TO gaokao_api_admin;
