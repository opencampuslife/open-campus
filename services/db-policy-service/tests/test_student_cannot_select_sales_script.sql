BEGIN;
SET LOCAL app.role = 'student';
SET LOCAL app.campus = 'zhengzhou';

SELECT COUNT(*) AS sales_script_count
FROM search_accessible_chunks('家长嫌贵', 10)
WHERE chunk_id = 'sales_price_sensitive_2026::chunk_001';
-- expect: 0

ROLLBACK;

