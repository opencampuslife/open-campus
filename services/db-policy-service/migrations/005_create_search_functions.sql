CREATE OR REPLACE VIEW v_accessible_knowledge_chunks
WITH (security_barrier = true)
AS
SELECT
    id,
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
    source_page,
    review_status,
    effective_date,
    expiry_date,
    created_at
FROM knowledge_chunks;

ALTER VIEW v_accessible_knowledge_chunks OWNER TO gaokao_rls_reader;

CREATE OR REPLACE FUNCTION search_accessible_chunks(
    query_text TEXT,
    limit_count INT DEFAULT 5
)
RETURNS TABLE (
    chunk_id TEXT,
    title TEXT,
    content TEXT,
    source_uri TEXT,
    source_page TEXT,
    visibility TEXT,
    data_level TEXT,
    data_level_int SMALLINT,
    business_tags TEXT[]
)
LANGUAGE sql
STABLE
SECURITY INVOKER
AS $$
    WITH ranked AS (
        SELECT
            kc.*,
            (
                CASE
                    WHEN query_text IS NOT NULL AND query_text != '' AND kc.title ILIKE '%' || query_text || '%'
                    THEN 4.0 ELSE 0.0
                END
                +
                CASE
                    WHEN query_text IS NOT NULL AND query_text != ''
                         AND array_to_string(kc.business_tags, ' ') ILIKE '%' || query_text || '%'
                    THEN 3.0 ELSE 0.0
                END
                +
                CASE
                    WHEN query_text IS NOT NULL AND query_text != '' AND kc.content ILIKE '%' || query_text || '%'
                    THEN 1.0 ELSE 0.0
                END
                +
                similarity(
                    lower(
                        concat_ws(
                            ' ',
                            kc.title,
                            kc.title,
                            kc.title,
                            kc.title,
                            array_to_string(kc.business_tags, ' '),
                            array_to_string(kc.business_tags, ' '),
                            array_to_string(kc.business_tags, ' '),
                            kc.content
                        )
                    ),
                    lower(COALESCE(query_text, ''))
                ) * 2.0
            ) AS relevance,
            similarity(
                lower(
                    concat_ws(
                        ' ',
                        kc.title,
                        kc.content,
                        array_to_string(kc.business_tags, ' ')
                    )
                ),
                lower(COALESCE(query_text, ''))
            ) AS sim_score
        FROM v_accessible_knowledge_chunks kc
    )
    SELECT
        ranked.chunk_id,
        ranked.title,
        ranked.content,
        ranked.source_uri,
        ranked.source_page,
        ranked.visibility,
        ranked.data_level,
        ranked.data_level_int,
        ranked.business_tags
    FROM ranked
    WHERE
        query_text IS NULL
        OR query_text = ''
        OR ranked.title ILIKE '%' || query_text || '%'
        OR ranked.content ILIKE '%' || query_text || '%'
        OR array_to_string(ranked.business_tags, ' ') ILIKE '%' || query_text || '%'
        OR ranked.sim_score > 0.04
    ORDER BY
        ranked.relevance DESC,
        ranked.created_at DESC
    LIMIT limit_count;
$$;
