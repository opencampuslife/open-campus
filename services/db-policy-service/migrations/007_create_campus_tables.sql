CREATE TABLE IF NOT EXISTS schools (
    school_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    wecom_corp_id TEXT,
    wecom_agent_id TEXT,
    encrypted_app_secret TEXT,
    status TEXT NOT NULL DEFAULT 'active',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS campus_users (
    user_id TEXT PRIMARY KEY,
    school_id TEXT NOT NULL REFERENCES schools(school_id) ON DELETE CASCADE,
    wecom_userid TEXT UNIQUE,
    name TEXT NOT NULL,
    mobile_hash TEXT,
    role TEXT NOT NULL,
    class_id TEXT,
    status TEXT NOT NULL DEFAULT 'active',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS classes (
    class_id TEXT PRIMARY KEY,
    school_id TEXT NOT NULL REFERENCES schools(school_id) ON DELETE CASCADE,
    grade TEXT NOT NULL,
    name TEXT NOT NULL,
    head_teacher_id TEXT,
    external_party_id TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS students (
    student_id TEXT PRIMARY KEY,
    school_id TEXT NOT NULL REFERENCES schools(school_id) ON DELETE CASCADE,
    class_id TEXT NOT NULL REFERENCES classes(class_id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    student_no TEXT,
    parent_name TEXT,
    parent_mobile_hash TEXT,
    parent_userid TEXT,
    status TEXT NOT NULL DEFAULT 'active',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS leave_requests (
    leave_id TEXT PRIMARY KEY,
    school_id TEXT NOT NULL REFERENCES schools(school_id) ON DELETE CASCADE,
    student_id TEXT NOT NULL REFERENCES students(student_id) ON DELETE CASCADE,
    class_id TEXT NOT NULL REFERENCES classes(class_id) ON DELETE CASCADE,
    type TEXT NOT NULL,
    start_time TIMESTAMPTZ,
    end_time TIMESTAMPTZ,
    reason TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    approver_id TEXT,
    approved_at TIMESTAMPTZ,
    attachments_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS meal_orders (
    order_id TEXT PRIMARY KEY,
    school_id TEXT NOT NULL REFERENCES schools(school_id) ON DELETE CASCADE,
    student_id TEXT NOT NULL REFERENCES students(student_id) ON DELETE CASCADE,
    class_id TEXT NOT NULL REFERENCES classes(class_id) ON DELETE CASCADE,
    meal_date DATE NOT NULL,
    meal_type TEXT NOT NULL,
    action TEXT NOT NULL,
    dietary_note TEXT,
    status TEXT NOT NULL DEFAULT 'submitted',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS delivery_confirmations (
    delivery_id TEXT PRIMARY KEY,
    school_id TEXT NOT NULL REFERENCES schools(school_id) ON DELETE CASCADE,
    meal_date DATE NOT NULL,
    meal_type TEXT NOT NULL,
    vendor_id TEXT NOT NULL,
    total_count INTEGER NOT NULL DEFAULT 0,
    special_count INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'pending',
    confirmed_at TIMESTAMPTZ,
    token_hash TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS repair_tickets (
    ticket_id TEXT PRIMARY KEY,
    school_id TEXT NOT NULL REFERENCES schools(school_id) ON DELETE CASCADE,
    class_id TEXT REFERENCES classes(class_id) ON DELETE SET NULL,
    location_type TEXT NOT NULL,
    location_detail TEXT,
    category TEXT NOT NULL,
    description TEXT NOT NULL,
    priority TEXT NOT NULL DEFAULT 'medium',
    status TEXT NOT NULL DEFAULT 'pending',
    assignee_id TEXT,
    deadline_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    images_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS reminder_tasks (
    reminder_id TEXT PRIMARY KEY,
    school_id TEXT NOT NULL REFERENCES schools(school_id) ON DELETE CASCADE,
    biz_type TEXT NOT NULL,
    biz_id TEXT NOT NULL,
    receiver_type TEXT NOT NULL,
    receiver_id TEXT NOT NULL,
    channel TEXT NOT NULL,
    template_id TEXT,
    payload_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    scheduled_at TIMESTAMPTZ,
    sent_at TIMESTAMPTZ,
    status TEXT NOT NULL DEFAULT 'pending',
    retry_count INTEGER NOT NULL DEFAULT 0,
    idempotency_key TEXT
);

CREATE TABLE IF NOT EXISTS operation_logs (
    log_id TEXT PRIMARY KEY,
    school_id TEXT NOT NULL REFERENCES schools(school_id) ON DELETE CASCADE,
    actor_user_id TEXT,
    biz_type TEXT NOT NULL,
    biz_id TEXT NOT NULL,
    action TEXT NOT NULL,
    before_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    after_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    ip TEXT,
    user_agent TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
