DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'gaokao_api_public') THEN
        CREATE ROLE gaokao_api_public LOGIN PASSWORD 'postgres';
    END IF;
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'gaokao_api_staff') THEN
        CREATE ROLE gaokao_api_staff LOGIN PASSWORD 'postgres';
    END IF;
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'gaokao_api_admin') THEN
        CREATE ROLE gaokao_api_admin LOGIN PASSWORD 'postgres';
    END IF;
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'gaokao_indexer') THEN
        CREATE ROLE gaokao_indexer LOGIN PASSWORD 'postgres';
    END IF;
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'gaokao_audit_writer') THEN
        CREATE ROLE gaokao_audit_writer LOGIN PASSWORD 'postgres';
    END IF;
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'gaokao_rls_reader') THEN
        CREATE ROLE gaokao_rls_reader NOLOGIN;
    END IF;
END $$;
