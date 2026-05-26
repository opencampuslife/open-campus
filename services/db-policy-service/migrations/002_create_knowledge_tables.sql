CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE TABLE IF NOT EXISTS knowledge_docs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    doc_id TEXT UNIQUE NOT NULL,
    title TEXT NOT NULL,
    source_uri TEXT NOT NULL,

    visibility TEXT NOT NULL CHECK (
        visibility IN ('public', 'protected', 'internal', 'admin')
    ),

    data_level TEXT NOT NULL CHECK (
        data_level IN ('L1', 'L2', 'L3', 'L4', 'L5')
    ),
    data_level_int SMALLINT NOT NULL CHECK (data_level_int BETWEEN 1 AND 5),

    allowed_roles TEXT[] NOT NULL,
    campus_scope TEXT[] NOT NULL DEFAULT ARRAY['all'],
    business_tags TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],

    review_status TEXT NOT NULL CHECK (
        review_status IN ('draft', 'approved', 'archived')
    ),

    effective_date DATE,
    expiry_date DATE,

    owner TEXT,
    version INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS knowledge_chunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    chunk_id TEXT UNIQUE NOT NULL,
    doc_id UUID NOT NULL REFERENCES knowledge_docs(id) ON DELETE CASCADE,

    title TEXT NOT NULL,
    content TEXT NOT NULL,

    visibility TEXT NOT NULL CHECK (
        visibility IN ('public', 'protected', 'internal', 'admin')
    ),
    data_level TEXT NOT NULL CHECK (
        data_level IN ('L1', 'L2', 'L3', 'L4', 'L5')
    ),
    data_level_int SMALLINT NOT NULL CHECK (data_level_int BETWEEN 1 AND 5),

    allowed_roles TEXT[] NOT NULL,
    campus_scope TEXT[] NOT NULL DEFAULT ARRAY['all'],
    business_tags TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
    source_uri TEXT,
    source_page TEXT,

    review_status TEXT NOT NULL DEFAULT 'approved' CHECK (
        review_status IN ('draft', 'approved', 'archived')
    ),
    effective_date DATE,
    expiry_date DATE,

    embedding vector(1536),

    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_knowledge_docs_doc_id ON knowledge_docs(doc_id);
CREATE INDEX IF NOT EXISTS idx_knowledge_chunks_chunk_id ON knowledge_chunks(chunk_id);
CREATE INDEX IF NOT EXISTS idx_knowledge_chunks_visibility ON knowledge_chunks(visibility);
CREATE INDEX IF NOT EXISTS idx_knowledge_chunks_data_level_int ON knowledge_chunks(data_level_int);
CREATE INDEX IF NOT EXISTS idx_knowledge_chunks_roles ON knowledge_chunks USING gin(allowed_roles);
CREATE INDEX IF NOT EXISTS idx_knowledge_chunks_campus ON knowledge_chunks USING gin(campus_scope);
CREATE INDEX IF NOT EXISTS idx_knowledge_chunks_tags ON knowledge_chunks USING gin(business_tags);
CREATE INDEX IF NOT EXISTS idx_knowledge_chunks_review_status ON knowledge_chunks(review_status);
