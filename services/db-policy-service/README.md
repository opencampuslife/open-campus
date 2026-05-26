# DB Policy Service

This service defines the PostgreSQL hard boundary for knowledge access.

Application permission checks, RAG metadata filters, prompt guards, and compliance gates are defense-in-depth. PostgreSQL Row Level Security is the mechanical enforcement layer: non-admin entrypoints must not be able to query unauthorized knowledge rows even if application code is wrong.

## Boundary

```text
entrypoint identity
  -> API auth
  -> application permission scope
  -> database connection role
  -> SET LOCAL app.role / app.campus / app.user_id
  -> RLS / non-bypass security-barrier view / SECURITY INVOKER function
  -> RAG secondary filter
  -> LLM gateway prompt guard
```

## Database Roles

- `db_admin`: migration and administration only
- `gaokao_api_public`: public web, student, and parent entrypoints
- `gaokao_api_staff`: sales, teacher, and operator entrypoints
- `gaokao_api_admin`: admin console
- `gaokao_indexer`: knowledge indexing job
- `gaokao_audit_writer`: audit writer

Database role and business role are separate:

- database role limits entrypoint capability
- business role limits row visibility through session variables

## Required Request Pattern

Use `SET LOCAL`, never global `SET`, and always inside a transaction:

```sql
BEGIN;
SET LOCAL app.user_id = 'u_123';
SET LOCAL app.role = 'parent';
SET LOCAL app.campus = 'zhengzhou';
SET LOCAL app.auth_level = 'phone_verified';
SELECT * FROM search_accessible_chunks('学费', 5);
COMMIT;
```

## Migration Order

```bash
make migrate-db-policy
make test-db-policy
```

`DATABASE_URL_ADMIN` must point to a migration-capable PostgreSQL user. Non-admin application services must use role-specific URLs and must not use the admin URL.

## View Ownership

`v_accessible_knowledge_chunks` is owned by `gaokao_rls_reader`, a dedicated non-login role without `BYPASSRLS`. PostgreSQL `security_invoker=true` views require the caller to hold base-table privileges, which conflicts with the hard rule that public/staff roles cannot query base tables directly. The view therefore uses `security_barrier=true` and a non-bypass owner, while the search function remains `SECURITY INVOKER`.
