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
    'sales_price_sensitive_2026',
    '价格敏感用户沟通规则',
    'knowledge_vault/internal/sales_scripts/price_sensitive_users.md',
    'internal',
    'L3',
    3,
    ARRAY['sales', 'campus_admin'],
    ARRAY['zhengzhou'],
    ARRAY['招生话术', 'internal_pricing', '异议处理'],
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
    'sales_price_sensitive_2026::chunk_001',
    id,
    '价格敏感用户沟通规则',
    '当用户反复追问优惠底价时，招生顾问应优先解释公开费用构成，并引导用户到校面谈。',
    'internal',
    'L3',
    3,
    ARRAY['sales', 'campus_admin'],
    ARRAY['zhengzhou'],
    ARRAY['招生话术', 'internal_pricing', '异议处理'],
    'knowledge_vault/internal/sales_scripts/price_sensitive_users.md',
    'approved',
    '2026-01-01',
    '2026-12-31'
FROM knowledge_docs
WHERE doc_id = 'sales_price_sensitive_2026'
ON CONFLICT (chunk_id) DO NOTHING;
