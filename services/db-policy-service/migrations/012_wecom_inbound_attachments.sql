-- Migration 012: WeCom inbound image callback processing
-- Extends callback messages with asynchronous download state and attachment linkage.

ALTER TABLE inbound_messages
    ADD COLUMN IF NOT EXISTS attachment_id TEXT REFERENCES attachments(attachment_id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS last_error TEXT,
    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT now();

CREATE INDEX IF NOT EXISTS idx_inbound_messages_download_pending
    ON inbound_messages (created_at)
    WHERE status = 'download_pending';

CREATE INDEX IF NOT EXISTS idx_attachments_wecom_owner
    ON attachments (school_id, created_by_wecom_userid, attachment_id)
    WHERE source = 'wecom_callback';

CREATE OR REPLACE FUNCTION update_inbound_messages_updated_at()
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
        WHERE tgname = 'trg_inbound_messages_updated_at'
          AND tgrelid = 'inbound_messages'::regclass
    ) THEN
        CREATE TRIGGER trg_inbound_messages_updated_at
        BEFORE UPDATE ON inbound_messages
        FOR EACH ROW EXECUTE FUNCTION update_inbound_messages_updated_at();
    END IF;
END $$;
