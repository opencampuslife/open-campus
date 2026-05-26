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
    'assessment_parent_guide_2026',
    '家长测评说明',
    'knowledge_vault/protected/parent_guides/assessment_parent_guide.md',
    'protected',
    'L2',
    2,
    ARRAY['student', 'parent', 'sales'],
    ARRAY['all'],
    ARRAY['测评', '家长指南'],
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
    'assessment_parent_guide_2026::chunk_001',
    id,
    '测评准备',
    '入学测评用于了解学生基础、薄弱科目和班型适配情况。',
    'protected',
    'L2',
    2,
    ARRAY['student', 'parent', 'sales'],
    ARRAY['all'],
    ARRAY['测评', '家长指南'],
    'knowledge_vault/protected/parent_guides/assessment_parent_guide.md',
    'approved',
    '2026-01-01',
    '2026-12-31'
FROM knowledge_docs
WHERE doc_id = 'assessment_parent_guide_2026'
ON CONFLICT (chunk_id) DO NOTHING;
