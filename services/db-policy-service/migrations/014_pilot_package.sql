-- Migration 014: Controlled single-school pilot configuration and runtime controls.

CREATE TABLE IF NOT EXISTS pilot_school_configs (
    school_id TEXT PRIMARY KEY REFERENCES schools(school_id) ON DELETE CASCADE,
    timezone TEXT NOT NULL DEFAULT 'Asia/Shanghai',
    callback_url TEXT,
    meal_policy_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    vendor_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS mealbot_runtime_controls (
    school_id TEXT PRIMARY KEY REFERENCES schools(school_id) ON DELETE CASCADE,
    h5_submissions_enabled BOOLEAN NOT NULL DEFAULT true,
    reminder_worker_enabled BOOLEAN NOT NULL DEFAULT true,
    wecom_media_worker_enabled BOOLEAN NOT NULL DEFAULT true,
    updated_by TEXT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE OR REPLACE FUNCTION update_pilot_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_trigger WHERE tgname = 'trg_pilot_school_configs_updated'
    ) THEN
        CREATE TRIGGER trg_pilot_school_configs_updated
        BEFORE UPDATE ON pilot_school_configs
        FOR EACH ROW EXECUTE FUNCTION update_pilot_timestamp();
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_trigger WHERE tgname = 'trg_mealbot_runtime_controls_updated'
    ) THEN
        CREATE TRIGGER trg_mealbot_runtime_controls_updated
        BEFORE UPDATE ON mealbot_runtime_controls
        FOR EACH ROW EXECUTE FUNCTION update_pilot_timestamp();
    END IF;
END $$;

ALTER TABLE pilot_school_configs ENABLE ROW LEVEL SECURITY;
ALTER TABLE pilot_school_configs FORCE ROW LEVEL SECURITY;
ALTER TABLE mealbot_runtime_controls ENABLE ROW LEVEL SECURITY;
ALTER TABLE mealbot_runtime_controls FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS p_pilot_configs_admin ON pilot_school_configs;
CREATE POLICY p_pilot_configs_admin ON pilot_school_configs
FOR ALL TO gaokao_api_admin USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS p_pilot_controls_admin ON mealbot_runtime_controls;
CREATE POLICY p_pilot_controls_admin ON mealbot_runtime_controls
FOR ALL TO gaokao_api_admin USING (true) WITH CHECK (true);

GRANT SELECT, INSERT, UPDATE, DELETE ON pilot_school_configs, mealbot_runtime_controls TO gaokao_api_admin;
