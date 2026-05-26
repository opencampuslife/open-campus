-- Migration 010: Meal lock and vendor confirmation tables
-- Adds: meal_locks, vendor_confirmations

CREATE TABLE IF NOT EXISTS meal_locks (
    lock_id           TEXT PRIMARY KEY,
    school_id         TEXT NOT NULL REFERENCES schools(school_id) ON DELETE CASCADE,
    meal_date         DATE NOT NULL,
    meal_type         TEXT NOT NULL CHECK (meal_type IN ('lunch', 'dinner', 'extra')),
    status            TEXT NOT NULL DEFAULT 'locked'
                      CHECK (status IN ('locked', 'sent_to_vendor', 'closed')),
    locked_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    locked_by         TEXT,
    summary_snapshot  JSONB NOT NULL DEFAULT '{}',
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (school_id, meal_date, meal_type)
);

CREATE TABLE IF NOT EXISTS vendor_confirmations (
    confirmation_id   TEXT PRIMARY KEY,
    school_id         TEXT NOT NULL REFERENCES schools(school_id) ON DELETE CASCADE,
    meal_lock_id      TEXT NOT NULL REFERENCES meal_locks(lock_id) ON DELETE CASCADE,
    vendor_name       TEXT,
    vendor_contact    TEXT,
    token_hash        TEXT NOT NULL UNIQUE,
    expires_at        TIMESTAMPTZ NOT NULL,
    status            TEXT NOT NULL DEFAULT 'pending'
                      CHECK (status IN ('pending', 'confirmed', 'abnormal', 'expired')),
    confirmed_at      TIMESTAMPTZ,
    confirmed_by      TEXT,
    abnormal_note     TEXT,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_meal_locks_school_date
    ON meal_locks(school_id, meal_date);

CREATE INDEX IF NOT EXISTS idx_vendor_confirmations_lock
    ON vendor_confirmations(meal_lock_id);

CREATE INDEX IF NOT EXISTS idx_vendor_confirmations_token
    ON vendor_confirmations(token_hash);

-- Trigger to keep updated_at current
CREATE OR REPLACE FUNCTION update_meal_locks_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trg_meal_locks_updated_at' AND tgrelid = 'meal_locks'::regclass) THEN
        CREATE TRIGGER trg_meal_locks_updated_at
        BEFORE UPDATE ON meal_locks
        FOR EACH ROW EXECUTE FUNCTION update_meal_locks_updated_at();
    END IF;
END $$;

CREATE OR REPLACE FUNCTION update_vendor_confirmations_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trg_vendor_confirmations_updated_at' AND tgrelid = 'vendor_confirmations'::regclass) THEN
        CREATE TRIGGER trg_vendor_confirmations_updated_at
        BEFORE UPDATE ON vendor_confirmations
        FOR EACH ROW EXECUTE FUNCTION update_vendor_confirmations_updated_at();
    END IF;
END $$;
