BEGIN;
SET LOCAL app.role = 'sales';
SET LOCAL app.campus = 'zhengzhou';

SELECT COUNT(*) AS sales_script_count
FROM search_accessible_chunks('优惠底价', 10)
WHERE chunk_id = 'sales_price_sensitive_2026::chunk_001';
-- expect: 1

ROLLBACK;

