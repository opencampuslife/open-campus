BEGIN;
SET LOCAL app.role = 'parent';
SET LOCAL app.campus = 'zhengzhou';

SELECT COUNT(*) AS internal_count
FROM v_accessible_knowledge_chunks
WHERE visibility = 'internal';
-- expect: 0

ROLLBACK;

