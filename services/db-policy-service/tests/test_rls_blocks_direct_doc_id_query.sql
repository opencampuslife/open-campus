BEGIN;
SET LOCAL app.role = 'parent';
SET LOCAL app.campus = 'zhengzhou';

SELECT COUNT(*) AS direct_doc_id_count
FROM v_accessible_knowledge_chunks
WHERE chunk_id = 'sales_price_sensitive_2026::chunk_001';
-- expect: 0

ROLLBACK;

