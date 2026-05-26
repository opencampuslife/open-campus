-- Migration 011: Reminder worker fields and indexes
-- Adds: last_error, locked_at, locked_by columns
-- Adds: due-task index, idempotency unique index

ALTER TABLE reminder_tasks
    ADD COLUMN IF NOT EXISTS last_error TEXT,
    ADD COLUMN IF NOT EXISTS locked_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS locked_by TEXT;

CREATE UNIQUE INDEX IF NOT EXISTS uq_reminder_tasks_idempotency
    ON reminder_tasks (school_id, idempotency_key)
    WHERE idempotency_key IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_reminder_tasks_due
    ON reminder_tasks (status, scheduled_at)
    WHERE status = 'pending';
