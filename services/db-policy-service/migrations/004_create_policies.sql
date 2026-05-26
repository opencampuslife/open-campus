CREATE OR REPLACE FUNCTION max_data_level_int_for_role(role_name TEXT)
RETURNS SMALLINT
LANGUAGE sql
STABLE
AS $$
    SELECT CASE role_name
        WHEN 'visitor' THEN 1
        WHEN 'student' THEN 2
        WHEN 'parent' THEN 2
        WHEN 'sales' THEN 3
        WHEN 'teacher' THEN 3
        WHEN 'operator' THEN 3
        WHEN 'campus_admin' THEN 3
        WHEN 'admin' THEN 5
        ELSE 1
    END;
$$;

CREATE OR REPLACE FUNCTION allowed_visibility_for_role(role_name TEXT)
RETURNS TEXT[]
LANGUAGE sql
STABLE
AS $$
    SELECT CASE role_name
        WHEN 'visitor' THEN ARRAY['public']
        WHEN 'student' THEN ARRAY['public', 'protected']
        WHEN 'parent' THEN ARRAY['public', 'protected']
        WHEN 'sales' THEN ARRAY['public', 'protected', 'internal']
        WHEN 'teacher' THEN ARRAY['public', 'protected', 'internal']
        WHEN 'operator' THEN ARRAY['public', 'protected', 'internal']
        WHEN 'campus_admin' THEN ARRAY['public', 'protected', 'internal']
        WHEN 'admin' THEN ARRAY['public', 'protected', 'internal', 'admin']
        ELSE ARRAY['public']
    END;
$$;

CREATE OR REPLACE FUNCTION review_status_is_approved(doc_uuid UUID)
RETURNS BOOLEAN
LANGUAGE sql
STABLE
AS $$
    SELECT COALESCE((
        SELECT review_status = 'approved'
        FROM knowledge_docs
        WHERE id = doc_uuid
    ), false);
$$;

CREATE OR REPLACE FUNCTION is_effective(doc_uuid UUID)
RETURNS BOOLEAN
LANGUAGE sql
STABLE
AS $$
    SELECT COALESCE((
        SELECT
            (effective_date IS NULL OR effective_date <= CURRENT_DATE)
            AND
            (expiry_date IS NULL OR expiry_date >= CURRENT_DATE)
        FROM knowledge_docs
        WHERE id = doc_uuid
    ), false);
$$;

DROP POLICY IF EXISTS p_knowledge_docs_select ON knowledge_docs;
CREATE POLICY p_knowledge_docs_select
ON knowledge_docs
FOR SELECT
USING (
    current_setting('app.role', true) IS NOT NULL
    AND current_setting('app.role', true) = ANY(allowed_roles)
    AND data_level_int <= max_data_level_int_for_role(current_setting('app.role', true))
    AND visibility = ANY(allowed_visibility_for_role(current_setting('app.role', true)))
    AND (
        'all' = ANY(campus_scope)
        OR current_setting('app.campus', true) = ANY(campus_scope)
    )
    AND review_status = 'approved'
    AND (effective_date IS NULL OR effective_date <= CURRENT_DATE)
    AND (expiry_date IS NULL OR expiry_date >= CURRENT_DATE)
);

DROP POLICY IF EXISTS p_knowledge_chunks_select ON knowledge_chunks;
CREATE POLICY p_knowledge_chunks_select
ON knowledge_chunks
FOR SELECT
USING (
    current_setting('app.role', true) IS NOT NULL
    AND current_setting('app.role', true) = ANY(allowed_roles)
    AND data_level_int <= max_data_level_int_for_role(current_setting('app.role', true))
    AND visibility = ANY(allowed_visibility_for_role(current_setting('app.role', true)))
    AND (
        'all' = ANY(campus_scope)
        OR current_setting('app.campus', true) = ANY(campus_scope)
    )
    AND review_status = 'approved'
    AND (effective_date IS NULL OR effective_date <= CURRENT_DATE)
    AND (expiry_date IS NULL OR expiry_date >= CURRENT_DATE)
);

DROP POLICY IF EXISTS p_knowledge_docs_indexer_all ON knowledge_docs;
CREATE POLICY p_knowledge_docs_indexer_all
ON knowledge_docs
FOR ALL
TO gaokao_indexer
USING (true)
WITH CHECK (true);

DROP POLICY IF EXISTS p_knowledge_chunks_indexer_all ON knowledge_chunks;
CREATE POLICY p_knowledge_chunks_indexer_all
ON knowledge_chunks
FOR ALL
TO gaokao_indexer
USING (true)
WITH CHECK (true);
