INSERT INTO knowledge_docs (
    doc_id,
    title,
    source_uri,
    visibility,
    data_level,
    data_level_int,
    allowed_roles,
    campus_scope,
    business_tags,
    review_status,
    effective_date,
    expiry_date,
    owner
)
VALUES (
    'tuition_public_2026',
    '公开费用说明',
    'knowledge_vault/public/enrollment/tuition_public.md',
    'public',
    'L1',
    1,
    ARRAY['visitor', 'student', 'parent', 'sales'],
    ARRAY['all'],
    ARRAY['费用政策', '学费', '公开口径'],
    'approved',
    '2026-01-01',
    '2026-12-31',
    '招生运营部'
)
ON CONFLICT (doc_id) DO NOTHING;

INSERT INTO knowledge_chunks (
    chunk_id,
    doc_id,
    title,
    content,
    visibility,
    data_level,
    data_level_int,
    allowed_roles,
    campus_scope,
    business_tags,
    source_uri,
    review_status,
    effective_date,
    expiry_date
)
SELECT
    'tuition_public_2026::chunk_001',
    id,
    '公开费用说明',
    '学费会根据校区、班型、课程周期和学生学情安排有所差异。',
    'public',
    'L1',
    1,
    ARRAY['visitor', 'student', 'parent', 'sales'],
    ARRAY['all'],
    ARRAY['费用政策', '学费', '公开口径'],
    'knowledge_vault/public/enrollment/tuition_public.md',
    'approved',
    '2026-01-01',
    '2026-12-31'
FROM knowledge_docs
WHERE doc_id = 'tuition_public_2026'
ON CONFLICT (chunk_id) DO NOTHING;

INSERT INTO knowledge_docs (
    doc_id,
    title,
    source_uri,
    visibility,
    data_level,
    data_level_int,
    allowed_roles,
    campus_scope,
    business_tags,
    review_status,
    effective_date,
    expiry_date,
    owner
)
VALUES (
    'course_fulltime_repeat_2026',
    '全日制高考复读班介绍',
    'knowledge_vault/public/courses/fulltime_repeat.md',
    'public',
    'L1',
    1,
    ARRAY['visitor', 'student', 'parent', 'sales'],
    ARRAY['all'],
    ARRAY['课程体系', '复读班', '分层教学'],
    'approved',
    '2026-01-01',
    '2026-12-31',
    '教学教务部'
)
ON CONFLICT (doc_id) DO NOTHING;

INSERT INTO knowledge_chunks (
    chunk_id,
    doc_id,
    title,
    content,
    visibility,
    data_level,
    data_level_int,
    allowed_roles,
    campus_scope,
    business_tags,
    source_uri,
    review_status,
    effective_date,
    expiry_date
)
SELECT
    'course_fulltime_repeat_2026::chunk_002',
    id,
    '适合对象',
    '适合希望系统复习、提升高考成绩、需要较强学习管理的复读学生。',
    'public',
    'L1',
    1,
    ARRAY['visitor', 'student', 'parent', 'sales'],
    ARRAY['all'],
    ARRAY['课程体系', '复读班', '分层教学'],
    'knowledge_vault/public/courses/fulltime_repeat.md',
    'approved',
    '2026-01-01',
    '2026-12-31'
FROM knowledge_docs
WHERE doc_id = 'course_fulltime_repeat_2026'
ON CONFLICT (chunk_id) DO NOTHING;

INSERT INTO knowledge_docs (
    doc_id,
    title,
    source_uri,
    visibility,
    data_level,
    data_level_int,
    allowed_roles,
    campus_scope,
    business_tags,
    review_status,
    effective_date,
    expiry_date,
    owner
)
VALUES (
    'enrollment_flow_2026',
    '2026 报名流程说明',
    'knowledge_vault/public/enrollment/flow_2026.md',
    'public',
    'L1',
    1,
    ARRAY['visitor', 'student', 'parent', 'sales'],
    ARRAY['all'],
    ARRAY['招生信息', '报名流程'],
    'approved',
    '2026-01-01',
    '2026-12-31',
    '招生运营部'
)
ON CONFLICT (doc_id) DO NOTHING;

INSERT INTO knowledge_chunks (
    chunk_id,
    doc_id,
    title,
    content,
    visibility,
    data_level,
    data_level_int,
    allowed_roles,
    campus_scope,
    business_tags,
    source_uri,
    review_status,
    effective_date,
    expiry_date
)
SELECT
    'enrollment_flow_2026::chunk_002',
    id,
    '基础流程',
    '1. 在线或电话咨询 2. 提交基础学情信息 3. 预约入学测评或到校咨询 4. 根据测评和目标确定适合班型 5. 确认入学安排',
    'public',
    'L1',
    1,
    ARRAY['visitor', 'student', 'parent', 'sales'],
    ARRAY['all'],
    ARRAY['招生信息', '报名流程'],
    'knowledge_vault/public/enrollment/flow_2026.md',
    'approved',
    '2026-01-01',
    '2026-12-31'
FROM knowledge_docs
WHERE doc_id = 'enrollment_flow_2026'
ON CONFLICT (chunk_id) DO NOTHING;
