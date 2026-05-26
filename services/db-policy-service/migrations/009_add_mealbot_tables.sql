-- Migration 009: Add mealbot tables and extend existing campus tables
-- Adds: attachments, inbound_messages
-- Alters: meal_orders (reason, submitted_by, updated_at, unique constraint)
-- Alters: schools (wecom_token, wecom_encoding_aes_key)

-- attachments: store uploaded photos/images
CREATE TABLE IF NOT EXISTS attachments (
    attachment_id  TEXT PRIMARY KEY,
    school_id      TEXT NOT NULL REFERENCES schools(school_id) ON DELETE CASCADE,
    source         TEXT NOT NULL CHECK (source IN ('h5_upload', 'wecom_callback')),
    biz_type       TEXT,
    biz_id         TEXT,
    file_path      TEXT NOT NULL,
    original_name  TEXT,
    content_type   TEXT,
    size_bytes     INTEGER,
    sha256         TEXT,
    created_by_wecom_userid TEXT,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- inbound_messages: raw WeCom callback messages
CREATE TABLE IF NOT EXISTS inbound_messages (
    msg_id          TEXT PRIMARY KEY,
    school_id       TEXT REFERENCES schools(school_id) ON DELETE CASCADE,
    from_wecom_userid TEXT NOT NULL,
    msg_type        TEXT NOT NULL,
    agent_id        TEXT,
    media_id        TEXT,
    pic_url         TEXT,
    raw_xml         TEXT,
    status          TEXT NOT NULL DEFAULT 'received',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Add meal_orders columns for mealbot plan
ALTER TABLE meal_orders
    ADD COLUMN IF NOT EXISTS reason TEXT,
    ADD COLUMN IF NOT EXISTS submitted_by_wecom_userid TEXT,
    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT now();

-- Add idempotency unique constraint on meal_orders
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'meal_orders_student_meal_action_uniq'
        AND conrelid = 'meal_orders'::regclass
    ) THEN
        ALTER TABLE meal_orders
        ADD CONSTRAINT meal_orders_student_meal_action_uniq
        UNIQUE (student_id, meal_date, meal_type, action);
    END IF;
END $$;

-- Add WeCom callback config columns to schools
ALTER TABLE schools
    ADD COLUMN IF NOT EXISTS wecom_token TEXT,
    ADD COLUMN IF NOT EXISTS wecom_encoding_aes_key TEXT;

-- Trigger to keep updated_at current on meal_orders
CREATE OR REPLACE FUNCTION update_meal_orders_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_trigger
        WHERE tgname = 'trg_meal_orders_updated_at'
        AND tgrelid = 'meal_orders'::regclass
    ) THEN
        CREATE TRIGGER trg_meal_orders_updated_at
        BEFORE UPDATE ON meal_orders
        FOR EACH ROW EXECUTE FUNCTION update_meal_orders_updated_at();
    END IF;
END $$;
