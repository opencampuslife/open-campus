REVOKE ALL ON knowledge_docs FROM PUBLIC;
REVOKE ALL ON knowledge_chunks FROM PUBLIC;
REVOKE ALL ON v_accessible_knowledge_chunks FROM PUBLIC;
REVOKE ALL ON FUNCTION search_accessible_chunks(TEXT, INT) FROM PUBLIC;

REVOKE ALL ON knowledge_docs FROM gaokao_api_public;
REVOKE ALL ON knowledge_chunks FROM gaokao_api_public;
REVOKE ALL ON knowledge_docs FROM gaokao_api_staff;
REVOKE ALL ON knowledge_chunks FROM gaokao_api_staff;

GRANT SELECT ON knowledge_docs TO gaokao_rls_reader;
GRANT SELECT ON knowledge_chunks TO gaokao_rls_reader;

GRANT SELECT ON v_accessible_knowledge_chunks TO gaokao_api_public;
GRANT SELECT ON v_accessible_knowledge_chunks TO gaokao_api_staff;
GRANT SELECT ON v_accessible_knowledge_chunks TO gaokao_api_admin;

GRANT EXECUTE ON FUNCTION search_accessible_chunks(TEXT, INT) TO gaokao_api_public;
GRANT EXECUTE ON FUNCTION search_accessible_chunks(TEXT, INT) TO gaokao_api_staff;
GRANT EXECUTE ON FUNCTION search_accessible_chunks(TEXT, INT) TO gaokao_api_admin;

GRANT SELECT, INSERT, UPDATE, DELETE ON knowledge_docs TO gaokao_indexer;
GRANT SELECT, INSERT, UPDATE, DELETE ON knowledge_chunks TO gaokao_indexer;

GRANT SELECT, INSERT, UPDATE, DELETE ON knowledge_docs TO gaokao_api_admin;
GRANT SELECT, INSERT, UPDATE, DELETE ON knowledge_chunks TO gaokao_api_admin;
