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
    'admin_redline_rules_2026',
    '管理后台红线规则',
    'knowledge_vault/admin/compliance_rules/redline_rules.md',
    'admin',
    'L5',
    5,
    ARRAY['admin'],
    ARRAY['all'],
    ARRAY['管理策略', '红线规则'],
    'approved',
    '2026-01-01',
    '2026-12-31',
    '系统管理员'
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
    'admin_redline_rules_2026::chunk_001',
    id,
    '管理后台红线规则',
    '仅系统管理员可查看的后台策略。',
    'admin',
    'L5',
    5,
    ARRAY['admin'],
    ARRAY['all'],
    ARRAY['管理策略', '红线规则'],
    'knowledge_vault/admin/compliance_rules/redline_rules.md',
    'approved',
    '2026-01-01',
    '2026-12-31'
FROM knowledge_docs
WHERE doc_id = 'admin_redline_rules_2026'
ON CONFLICT (chunk_id) DO NOTHING;
