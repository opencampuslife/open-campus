-- Migration 015: Campus agent modules for materials, leave returns, attendance,
-- score review, payment reconciliation, and review-only automation jobs.

ALTER TABLE leave_requests
    ADD COLUMN IF NOT EXISTS submitted_by TEXT,
    ADD COLUMN IF NOT EXISTS approval_note TEXT,
    ADD COLUMN IF NOT EXISTS returned_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS returned_by TEXT,
    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT now();

CREATE TABLE IF NOT EXISTS collection_tasks (
    task_id TEXT PRIMARY KEY,
    school_id TEXT NOT NULL REFERENCES schools(school_id) ON DELETE CASCADE,
    class_id TEXT NOT NULL REFERENCES classes(class_id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    material_type TEXT NOT NULL,
    deadline_at TIMESTAMPTZ NOT NULL,
    status TEXT NOT NULL DEFAULT 'open'
        CHECK (status IN ('draft', 'open', 'closed', 'archived')),
    created_by TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS material_submissions (
    submission_id TEXT PRIMARY KEY,
    school_id TEXT NOT NULL REFERENCES schools(school_id) ON DELETE CASCADE,
    task_id TEXT NOT NULL REFERENCES collection_tasks(task_id) ON DELETE CASCADE,
    student_id TEXT NOT NULL REFERENCES students(student_id) ON DELETE CASCADE,
    attachment_id TEXT REFERENCES attachments(attachment_id) ON DELETE SET NULL,
    status TEXT NOT NULL DEFAULT 'submitted'
        CHECK (status IN ('submitted', 'processing', 'review_required', 'accepted', 'rejected')),
    extracted_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    submitted_by TEXT,
    reviewed_by TEXT,
    reviewed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (task_id, student_id)
);

CREATE TABLE IF NOT EXISTS material_missing_items (
    missing_id TEXT PRIMARY KEY,
    school_id TEXT NOT NULL REFERENCES schools(school_id) ON DELETE CASCADE,
    task_id TEXT NOT NULL REFERENCES collection_tasks(task_id) ON DELETE CASCADE,
    student_id TEXT NOT NULL REFERENCES students(student_id) ON DELETE CASCADE,
    status TEXT NOT NULL DEFAULT 'missing'
        CHECK (status IN ('missing', 'reminded', 'submitted', 'waived')),
    reminded_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (task_id, student_id)
);

CREATE TABLE IF NOT EXISTS score_batches (
    batch_id TEXT PRIMARY KEY,
    school_id TEXT NOT NULL REFERENCES schools(school_id) ON DELETE CASCADE,
    class_id TEXT NOT NULL REFERENCES classes(class_id) ON DELETE CASCADE,
    exam_name TEXT NOT NULL,
    subject TEXT NOT NULL,
    max_score NUMERIC(8,2) NOT NULL DEFAULT 100,
    attachment_id TEXT REFERENCES attachments(attachment_id) ON DELETE SET NULL,
    status TEXT NOT NULL DEFAULT 'uploaded'
        CHECK (status IN ('uploaded', 'processing', 'review_required', 'confirmed', 'exported', 'rejected')),
    created_by TEXT NOT NULL,
    confirmed_by TEXT,
    confirmed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS score_entries (
    entry_id TEXT PRIMARY KEY,
    school_id TEXT NOT NULL REFERENCES schools(school_id) ON DELETE CASCADE,
    batch_id TEXT NOT NULL REFERENCES score_batches(batch_id) ON DELETE CASCADE,
    student_id TEXT REFERENCES students(student_id) ON DELETE SET NULL,
    student_no TEXT,
    student_name TEXT NOT NULL,
    score NUMERIC(8,2),
    extraction_confidence NUMERIC(5,4),
    review_status TEXT NOT NULL DEFAULT 'pending'
        CHECK (review_status IN ('pending', 'accepted', 'corrected', 'rejected')),
    reviewed_by TEXT,
    reviewed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (batch_id, student_no)
);

CREATE TABLE IF NOT EXISTS score_anomalies (
    anomaly_id TEXT PRIMARY KEY,
    school_id TEXT NOT NULL REFERENCES schools(school_id) ON DELETE CASCADE,
    batch_id TEXT NOT NULL REFERENCES score_batches(batch_id) ON DELETE CASCADE,
    entry_id TEXT REFERENCES score_entries(entry_id) ON DELETE CASCADE,
    anomaly_type TEXT NOT NULL,
    message TEXT NOT NULL,
    risk_level TEXT NOT NULL DEFAULT 'medium',
    status TEXT NOT NULL DEFAULT 'open'
        CHECK (status IN ('open', 'resolved', 'waived')),
    resolved_by TEXT,
    resolved_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS payment_tasks (
    task_id TEXT PRIMARY KEY,
    school_id TEXT NOT NULL REFERENCES schools(school_id) ON DELETE CASCADE,
    class_id TEXT NOT NULL REFERENCES classes(class_id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    amount_due NUMERIC(10,2) NOT NULL,
    deadline_at TIMESTAMPTZ NOT NULL,
    account_note TEXT,
    status TEXT NOT NULL DEFAULT 'open'
        CHECK (status IN ('draft', 'open', 'closed', 'archived')),
    created_by TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS payment_records (
    record_id TEXT PRIMARY KEY,
    school_id TEXT NOT NULL REFERENCES schools(school_id) ON DELETE CASCADE,
    task_id TEXT NOT NULL REFERENCES payment_tasks(task_id) ON DELETE CASCADE,
    student_id TEXT NOT NULL REFERENCES students(student_id) ON DELETE CASCADE,
    attachment_id TEXT REFERENCES attachments(attachment_id) ON DELETE SET NULL,
    extracted_name TEXT,
    extracted_amount NUMERIC(10,2),
    extracted_paid_at TIMESTAMPTZ,
    transaction_ref_hash TEXT,
    status TEXT NOT NULL DEFAULT 'submitted'
        CHECK (status IN ('submitted', 'processing', 'review_required', 'confirmed', 'rejected')),
    submitted_by TEXT,
    confirmed_by TEXT,
    confirmed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (task_id, student_id)
);

CREATE TABLE IF NOT EXISTS payment_anomalies (
    anomaly_id TEXT PRIMARY KEY,
    school_id TEXT NOT NULL REFERENCES schools(school_id) ON DELETE CASCADE,
    task_id TEXT NOT NULL REFERENCES payment_tasks(task_id) ON DELETE CASCADE,
    record_id TEXT REFERENCES payment_records(record_id) ON DELETE CASCADE,
    anomaly_type TEXT NOT NULL,
    message TEXT NOT NULL,
    risk_level TEXT NOT NULL DEFAULT 'medium',
    status TEXT NOT NULL DEFAULT 'open'
        CHECK (status IN ('open', 'resolved', 'waived')),
    resolved_by TEXT,
    resolved_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS attendance_sessions (
    session_id TEXT PRIMARY KEY,
    school_id TEXT NOT NULL REFERENCES schools(school_id) ON DELETE CASCADE,
    class_id TEXT NOT NULL REFERENCES classes(class_id) ON DELETE CASCADE,
    attendance_date DATE NOT NULL,
    period TEXT NOT NULL CHECK (period IN ('morning', 'class', 'evening_study')),
    status TEXT NOT NULL DEFAULT 'open'
        CHECK (status IN ('open', 'submitted', 'closed')),
    created_by TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (school_id, class_id, attendance_date, period)
);

CREATE TABLE IF NOT EXISTS attendance_records (
    record_id TEXT PRIMARY KEY,
    school_id TEXT NOT NULL REFERENCES schools(school_id) ON DELETE CASCADE,
    session_id TEXT NOT NULL REFERENCES attendance_sessions(session_id) ON DELETE CASCADE,
    student_id TEXT NOT NULL REFERENCES students(student_id) ON DELETE CASCADE,
    status TEXT NOT NULL CHECK (status IN ('present', 'late', 'early_leave', 'leave', 'absent')),
    note TEXT,
    matched_leave_id TEXT REFERENCES leave_requests(leave_id) ON DELETE SET NULL,
    submitted_by TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (session_id, student_id)
);

CREATE TABLE IF NOT EXISTS attendance_anomalies (
    anomaly_id TEXT PRIMARY KEY,
    school_id TEXT NOT NULL REFERENCES schools(school_id) ON DELETE CASCADE,
    session_id TEXT NOT NULL REFERENCES attendance_sessions(session_id) ON DELETE CASCADE,
    record_id TEXT REFERENCES attendance_records(record_id) ON DELETE CASCADE,
    student_id TEXT NOT NULL REFERENCES students(student_id) ON DELETE CASCADE,
    anomaly_type TEXT NOT NULL,
    risk_level TEXT NOT NULL DEFAULT 'medium',
    status TEXT NOT NULL DEFAULT 'open'
        CHECK (status IN ('open', 'notified', 'resolved')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (session_id, student_id, anomaly_type)
);

CREATE TABLE IF NOT EXISTS ocr_jobs (
    job_id TEXT PRIMARY KEY,
    school_id TEXT NOT NULL REFERENCES schools(school_id) ON DELETE CASCADE,
    job_type TEXT NOT NULL CHECK (job_type IN ('material_extract', 'score_extract', 'payment_extract')),
    biz_id TEXT NOT NULL,
    attachment_id TEXT REFERENCES attachments(attachment_id) ON DELETE SET NULL,
    input_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    output_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'processing', 'review_required', 'completed', 'failed')),
    last_error TEXT,
    locked_by TEXT,
    locked_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS rpa_jobs (
    job_id TEXT PRIMARY KEY,
    school_id TEXT NOT NULL REFERENCES schools(school_id) ON DELETE CASCADE,
    job_type TEXT NOT NULL,
    biz_id TEXT NOT NULL,
    input_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    output_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    status TEXT NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'approved', 'running', 'completed', 'failed')),
    approved_by TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS anomaly_records (
    anomaly_id TEXT PRIMARY KEY,
    school_id TEXT NOT NULL REFERENCES schools(school_id) ON DELETE CASCADE,
    biz_type TEXT NOT NULL,
    biz_id TEXT NOT NULL,
    anomaly_type TEXT NOT NULL,
    risk_level TEXT NOT NULL CHECK (risk_level IN ('low', 'medium', 'high')),
    details_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    status TEXT NOT NULL DEFAULT 'open'
        CHECK (status IN ('open', 'notified', 'resolved', 'waived')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    resolved_at TIMESTAMPTZ,
    resolved_by TEXT
);

CREATE INDEX IF NOT EXISTS idx_collection_tasks_school_class ON collection_tasks (school_id, class_id, status);
CREATE INDEX IF NOT EXISTS idx_material_missing_task ON material_missing_items (task_id, status);
CREATE INDEX IF NOT EXISTS idx_score_batches_school_class ON score_batches (school_id, class_id, status);
CREATE INDEX IF NOT EXISTS idx_payment_tasks_school_class ON payment_tasks (school_id, class_id, status);
CREATE INDEX IF NOT EXISTS idx_attendance_sessions_date ON attendance_sessions (school_id, attendance_date, period);
CREATE INDEX IF NOT EXISTS idx_ocr_jobs_pending ON ocr_jobs (status, created_at) WHERE status = 'pending';
CREATE INDEX IF NOT EXISTS idx_anomaly_records_school_open ON anomaly_records (school_id, status, risk_level);

CREATE OR REPLACE FUNCTION update_campus_module_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DO $$
DECLARE
    table_name TEXT;
BEGIN
    FOREACH table_name IN ARRAY ARRAY[
        'collection_tasks', 'material_submissions', 'score_batches',
        'payment_tasks', 'payment_records', 'attendance_sessions',
        'attendance_records', 'ocr_jobs', 'rpa_jobs'
    ]
    LOOP
        IF NOT EXISTS (
            SELECT 1 FROM pg_trigger
            WHERE tgname = 'trg_' || table_name || '_updated'
        ) THEN
            EXECUTE format(
                'CREATE TRIGGER %I BEFORE UPDATE ON %I FOR EACH ROW EXECUTE FUNCTION update_campus_module_updated_at()',
                'trg_' || table_name || '_updated', table_name
            );
        END IF;
    END LOOP;
END $$;

DO $$
DECLARE
    table_name TEXT;
BEGIN
    FOREACH table_name IN ARRAY ARRAY[
        'collection_tasks', 'material_submissions', 'material_missing_items',
        'score_batches', 'score_entries', 'score_anomalies',
        'payment_tasks', 'payment_records', 'payment_anomalies',
        'attendance_sessions', 'attendance_records', 'attendance_anomalies',
        'ocr_jobs', 'rpa_jobs', 'anomaly_records'
    ]
    LOOP
        EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', table_name);
        EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY', table_name);
        EXECUTE format('DROP POLICY IF EXISTS p_%I_admin ON %I', table_name, table_name);
        EXECUTE format(
            'CREATE POLICY p_%I_admin ON %I FOR ALL TO gaokao_api_admin USING (true) WITH CHECK (true)',
            table_name, table_name
        );
        EXECUTE format('GRANT SELECT, INSERT, UPDATE, DELETE ON %I TO gaokao_api_admin', table_name);
    END LOOP;
END $$;

DROP POLICY IF EXISTS p_collection_tasks_staff ON collection_tasks;
CREATE POLICY p_collection_tasks_staff ON collection_tasks
FOR SELECT TO gaokao_api_staff
USING (
    campus_school_match(school_id)
    AND (
        current_setting('app.role', true) IN ('academic_admin', 'academic_staff', 'school_admin')
        OR current_setting('app.role', true) = 'head_teacher' AND campus_class_match(class_id)
    )
);
DROP POLICY IF EXISTS p_material_submissions_staff ON material_submissions;
CREATE POLICY p_material_submissions_staff ON material_submissions
FOR SELECT TO gaokao_api_staff
USING (
    campus_school_match(school_id)
    AND EXISTS (
        SELECT 1 FROM collection_tasks ct
        WHERE ct.task_id = material_submissions.task_id
          AND (
              current_setting('app.role', true) IN ('academic_admin', 'academic_staff', 'school_admin')
              OR current_setting('app.role', true) = 'head_teacher' AND campus_class_match(ct.class_id)
          )
    )
);
DROP POLICY IF EXISTS p_material_missing_staff ON material_missing_items;
CREATE POLICY p_material_missing_staff ON material_missing_items
FOR SELECT TO gaokao_api_staff
USING (
    campus_school_match(school_id)
    AND EXISTS (
        SELECT 1 FROM collection_tasks ct
        WHERE ct.task_id = material_missing_items.task_id
          AND (
              current_setting('app.role', true) IN ('academic_admin', 'academic_staff', 'school_admin')
              OR current_setting('app.role', true) = 'head_teacher' AND campus_class_match(ct.class_id)
          )
    )
);
DROP POLICY IF EXISTS p_score_batches_staff ON score_batches;
CREATE POLICY p_score_batches_staff ON score_batches
FOR SELECT TO gaokao_api_staff
USING (
    campus_school_match(school_id)
    AND (
        current_setting('app.role', true) IN ('academic_admin', 'academic_staff', 'school_admin')
        OR current_setting('app.role', true) IN ('head_teacher', 'teacher') AND campus_class_match(class_id)
    )
);
DROP POLICY IF EXISTS p_score_entries_staff ON score_entries;
CREATE POLICY p_score_entries_staff ON score_entries
FOR SELECT TO gaokao_api_staff
USING (
    campus_school_match(school_id)
    AND EXISTS (
        SELECT 1 FROM score_batches sb
        WHERE sb.batch_id = score_entries.batch_id
          AND (
              current_setting('app.role', true) IN ('academic_admin', 'academic_staff', 'school_admin')
              OR current_setting('app.role', true) IN ('head_teacher', 'teacher') AND campus_class_match(sb.class_id)
          )
    )
);
DROP POLICY IF EXISTS p_score_anomalies_staff ON score_anomalies;
CREATE POLICY p_score_anomalies_staff ON score_anomalies
FOR SELECT TO gaokao_api_staff
USING (
    campus_school_match(school_id)
    AND EXISTS (
        SELECT 1 FROM score_batches sb
        WHERE sb.batch_id = score_anomalies.batch_id
          AND (
              current_setting('app.role', true) IN ('academic_admin', 'academic_staff', 'school_admin')
              OR current_setting('app.role', true) IN ('head_teacher', 'teacher') AND campus_class_match(sb.class_id)
          )
    )
);
DROP POLICY IF EXISTS p_payment_tasks_staff ON payment_tasks;
CREATE POLICY p_payment_tasks_staff ON payment_tasks
FOR SELECT TO gaokao_api_staff
USING (
    campus_school_match(school_id)
    AND (
        current_setting('app.role', true) IN ('finance', 'school_admin')
        OR current_setting('app.role', true) = 'head_teacher' AND campus_class_match(class_id)
    )
);
DROP POLICY IF EXISTS p_payment_records_staff ON payment_records;
CREATE POLICY p_payment_records_staff ON payment_records
FOR SELECT TO gaokao_api_staff
USING (
    campus_school_match(school_id)
    AND EXISTS (
        SELECT 1 FROM payment_tasks pt
        WHERE pt.task_id = payment_records.task_id
          AND (
              current_setting('app.role', true) IN ('finance', 'school_admin')
              OR current_setting('app.role', true) = 'head_teacher' AND campus_class_match(pt.class_id)
          )
    )
);
DROP POLICY IF EXISTS p_payment_anomalies_staff ON payment_anomalies;
CREATE POLICY p_payment_anomalies_staff ON payment_anomalies
FOR SELECT TO gaokao_api_staff
USING (
    campus_school_match(school_id)
    AND EXISTS (
        SELECT 1 FROM payment_tasks pt
        WHERE pt.task_id = payment_anomalies.task_id
          AND (
              current_setting('app.role', true) IN ('finance', 'school_admin')
              OR current_setting('app.role', true) = 'head_teacher' AND campus_class_match(pt.class_id)
          )
    )
);
DROP POLICY IF EXISTS p_attendance_sessions_staff ON attendance_sessions;
CREATE POLICY p_attendance_sessions_staff ON attendance_sessions
FOR SELECT TO gaokao_api_staff
USING (
    campus_school_match(school_id)
    AND (
        current_setting('app.role', true) IN ('academic_admin', 'academic_staff', 'school_admin')
        OR current_setting('app.role', true) IN ('head_teacher', 'teacher') AND campus_class_match(class_id)
    )
);
DROP POLICY IF EXISTS p_attendance_records_staff ON attendance_records;
CREATE POLICY p_attendance_records_staff ON attendance_records
FOR SELECT TO gaokao_api_staff
USING (
    campus_school_match(school_id)
    AND EXISTS (
        SELECT 1 FROM attendance_sessions ats
        WHERE ats.session_id = attendance_records.session_id
          AND (
              current_setting('app.role', true) IN ('academic_admin', 'academic_staff', 'school_admin')
              OR current_setting('app.role', true) IN ('head_teacher', 'teacher') AND campus_class_match(ats.class_id)
          )
    )
);
DROP POLICY IF EXISTS p_attendance_anomalies_staff ON attendance_anomalies;
CREATE POLICY p_attendance_anomalies_staff ON attendance_anomalies
FOR SELECT TO gaokao_api_staff
USING (
    campus_school_match(school_id)
    AND EXISTS (
        SELECT 1 FROM attendance_sessions ats
        WHERE ats.session_id = attendance_anomalies.session_id
          AND (
              current_setting('app.role', true) IN ('academic_admin', 'academic_staff', 'school_admin')
              OR current_setting('app.role', true) IN ('head_teacher', 'teacher') AND campus_class_match(ats.class_id)
          )
    )
);
DROP POLICY IF EXISTS p_anomaly_records_staff ON anomaly_records;
CREATE POLICY p_anomaly_records_staff ON anomaly_records
FOR SELECT TO gaokao_api_staff
USING (
    campus_school_match(school_id)
    AND current_setting('app.role', true) IN ('academic_admin', 'academic_staff', 'finance', 'school_admin')
);

GRANT SELECT ON
    collection_tasks, material_submissions, material_missing_items,
    score_batches, score_entries, score_anomalies,
    payment_tasks, payment_records, payment_anomalies,
    attendance_sessions, attendance_records, attendance_anomalies,
    anomaly_records
TO gaokao_api_staff;
