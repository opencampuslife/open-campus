# Local Docker And SQL Setup

This service uses PostgreSQL 16 with pgvector for live RLS tests.

## Requirements

Install one container runtime:

- Docker Desktop: https://www.docker.com/products/docker-desktop/
- OrbStack: https://orbstack.dev/

You do not need to install `psql` on the host. If host `psql` is missing, `scripts/psql.sh` uses the `psql` binary inside the PostgreSQL container.

## One Command Setup

```bash
cd /Users/john/Downloads/openhuman-main/gaokao-agent
make setup-local-db
```

This starts PostgreSQL, applies migrations, loads fixtures, and runs live RLS tests.

## Manual Commands

```bash
make db-up
make migrate-db-policy
make test-db-policy-live
```

Stop and delete the local test database:

```bash
make db-down
```

## Test Database URLs

```text
DATABASE_URL_ADMIN=postgresql://postgres:postgres@localhost:54329/gaokao_agent_test
DATABASE_URL_PUBLIC=postgresql://gaokao_api_public:postgres@localhost:54329/gaokao_agent_test
DATABASE_URL_STAFF=postgresql://gaokao_api_staff:postgres@localhost:54329/gaokao_agent_test
DATABASE_URL_ADMIN_APP=postgresql://gaokao_api_admin:postgres@localhost:54329/gaokao_agent_test
```

These local passwords are for the disposable Docker test database only. Production should create roles and credentials through infrastructure secrets.

## Expected Live RLS Coverage

- parent cannot direct-query internal chunks by `chunk_id`
- parent cannot get internal chunks through `search_accessible_chunks`
- sales can get internal/L3 chunks
- sales cannot get admin/L5 chunks
- unset session context fails closed
- cross-campus staff access is blocked
- `gaokao_api_public` cannot query base tables
- security-barrier view owned by non-bypass `gaokao_rls_reader` does not leak internal rows
