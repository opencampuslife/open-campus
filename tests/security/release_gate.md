# Release Gate Security Assertions

This file mirrors the executable checks in `tests/security/test_release_gate.py`.
Every item here must stay covered by an automated test before a release can pass.

## Browser and BFF Boundary

- OpenHuman Gaokao mode sends only `session_id` and `message` to `/api/gaokao/chat`.
- OpenHuman Gaokao mode sends only `session_id` and optional `reason` to `/api/gaokao/handoff`.
- Frontend client rejects `role`, `evidence`, `model`, and `system_prompt` before `fetch`.
- BFF rejects forged browser fields including `role`, `evidence`, `model`, `system_prompt`, `tools`, `entrypoint`, and `identity`.
- `handoff` rejects `message`; the frontend-to-BFF handoff contract is `session_id` plus `reason`.

## Evidence and Citation Safety

- BFF citations expose only `title`, `section`, and `source_type`.
- BFF citations never expose `doc_id`, `chunk_id`, `source_uri`, `knowledge_vault`, or internal paths.
- Parent, student, and visitor entrypoints cannot retrieve internal/L3 evidence.
- Sales entrypoints can retrieve internal/L3 evidence when authorized.
- Sales entrypoints cannot retrieve admin/L5 evidence.

## Production Retrieval Boundary

- `GAOKAO_ENV=production` resolves to PostgreSQL retrieval.
- `GAOKAO_ENV=production` with `RAG_SOURCE=json` fails closed.
- Public and staff database URLs must not use admin database users.
- Live PostgreSQL RLS tests must verify unset session context fails closed.
- Live PostgreSQL RLS tests must verify connection reuse does not leak a prior role.

## Auditability

- `/api/gaokao/chat` writes an audit event through the orchestrator.
- `/api/gaokao/handoff` writes an audit event through the orchestrator.
- Audit events include user, role, entrypoint, retrieved chunk IDs, and compliance result.
