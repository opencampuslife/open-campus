# Production Admin Checklist

## Pre-Launch

### Environment

- [ ] `.env` created from `.env.example`
- [ ] `DEEPSEEK_API_KEY` set (keep offline if not using LLM)
- [ ] `CSRF_TOKEN_SECRET` set (min 32 chars, generate with `python3 -c 'import secrets; print(secrets.token_hex(32))'`)
- [ ] `TRUSTED_PROXY_TOKEN` set (same value on gateway)
- [ ] `GAOKAO_ENV=production`
- [ ] `ALLOW_DEV_IDENTITY_OVERRIDE=0`
- [ ] `ENABLE_REMOTE_URL_INGESTION=0` (default — change only with explicit confirmation)
- [ ] `ADMIN_SESSION_TTL_SECONDS=28800` (8 hours default)
- [ ] `ADMIN_IDLE_TIMEOUT_SECONDS=1800` (30 minutes default)

### Infrastructure

- [ ] Edge strips `x-gaokao-*` headers from external requests
- [ ] Internal gateway injects `x-gaokao-trusted-proxy` header
- [ ] Docker container runs as non-root user
- [ ] Docker container has read-only filesystem (except data dirs)
- [ ] `no-new-privileges: true` on container
- [ ] `cap_drop: ALL` on container
- [ ] Memory/CPU limits configured
- [ ] Health checks configured (`/api/health`)
- [ ] Rate limits: 30/min chat, 60/min admin

### Database

- [ ] PostgreSQL with pgvector extension
- [ ] Row-Level Security (RLS) enabled on all knowledge tables
- [ ] `search_accessible_chunks` function deployed
- [ ] Migrations applied: `make migrate-db-policy`
- [ ] Index synced: `make sync-db-index`
- [ ] Separate DB roles: admin, api_public, api_staff, api_admin

### Admin Console

- [ ] CSRF tokens working (HMAC-signed, 1h TTL)
- [ ] Rate limits active on admin routes
- [ ] Dangerous actions require confirmation phrases
- [ ] Admin sessions expire after TTL/idle timeout
- [ ] Audit events logged for all admin actions
- [ ] Admin roles assigned to real users (not default tokens)

### Backup

- [ ] Backup schedule configured (cron or orchestrator)
- [ ] `make recovery-drill` passes
- [ ] `make check-backup BACKUP_FILE=<latest>` passes
- [ ] Backup includes: PostgreSQL, knowledge_vault, CRM, staging, graph, audit, published
- [ ] `.env` excluded from backup
- [ ] `.env.example` included in backup
- [ ] Restore tested on clean environment

### Security

- [ ] CSRF token secret is strong (random 32+ chars)
- [ ] Rate limits enforced
- [ ] Trusted proxy boundary configured
- [ ] Remote URL ingestion disabled (default)
- [ ] Prompt injection detection active
- [ ] Promise-seeking detection active
- [ ] Compliance engine active
- [ ] RLS: parent/student cannot see internal/knowledge
- [ ] RLS: sales cannot see admin L4 documents
- [ ] Sensitive metadata redacted in audit events

## Post-Launch

### Monitoring

- [ ] Health endpoints monitored (`/api/health/full`)
- [ ] Audit events reviewed daily
- [ ] Error rate alerts configured
- [ ] Rate limit block events reviewed

### Ongoing

- [ ] Monthly backup integrity check
- [ ] Quarterly recovery drill
- [ ] Knowledge expiry dates monitored (no expired docs in index)
- [ ] CSRF token secret rotated on schedule
- [ ] Admin role assignments reviewed monthly

### Emergency

- [ ] Rollback procedure documented
- [ ] Emergency contact list maintained
- [ ] Backup restore procedure tested
- [ ] Admin password/secret rotation procedure

## Confirmation Phrases

Dangerous admin actions require explicit confirmation:

| Action | Confirmation Phrase |
|--------|-------------------|
| Publish document | `PUBLISH` |
| Delete staging doc | `DELETE` |
| Change permission fields | `CHANGE PERMISSION` |
| Enable remote URL ingestion | `ENABLE URL INGESTION` |
| Restore backup | `RESTORE` |
| Assign admin role | `ASSIGN ADMIN` |

## Session Policy

- Absolute TTL: 8 hours (configurable via `ADMIN_SESSION_TTL_SECONDS`)
- Idle timeout: 30 minutes (configurable via `ADMIN_IDLE_TIMEOUT_SECONDS`)
- CSRF tokens: 1 hour TTL, HMAC-signed with nonce
