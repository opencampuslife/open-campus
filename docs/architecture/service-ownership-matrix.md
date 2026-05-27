# Service Ownership Matrix

> Source of truth: `contracts/service_ownership.json`. Update both files when adding, removing, or reassigning services.
> Validate locally: `python tools/check_service_ownership.py --root .`

## Service Table

| # | Service | Sensitivity | Code Owner | Runtime Owner | Security Reviewer | Data Reviewer | Migration Wave |
|---|---------|-------------|------------|---------------|-------------------|---------------|----------------|
| 1 | agent-orchestrator | medium | TBD | TBD | — | — | phase_2 |
| 2 | api-gateway | medium | TBD | TBD | — | — | phase_1 |
| 3 | audit-service | **high** | TBD | TBD | TBD | TBD | phase_4 |
| 4 | auth-service | **high** | TBD | TBD | TBD | TBD | phase_2 |
| 5 | compliance-service | medium | TBD | TBD | — | — | phase_2 |
| 6 | crm-service | **high** | TBD | TBD | TBD | TBD | phase_3 |
| 7 | db-policy-service | **high** | TBD | TBD | — | TBD | phase_1 |
| 8 | evaluation-service | low | TBD | TBD | — | — | phase_3 |
| 9 | knowledge-graph-service | **high** | TBD | TBD | TBD | TBD | phase_3 |
| 10 | knowledge-service | **high** | TBD | TBD | TBD | TBD | phase_2 |
| 11 | llm-gateway | **high** | TBD | TBD | TBD | — | phase_1 |
| 12 | mealbot-service | medium | TBD | TBD | — | — | phase_4 |
| 13 | permission-service | **high** | TBD | TBD | TBD | TBD | phase_2 |
| 14 | rag-service | medium | TBD | TBD | — | — | phase_2 |
| 15 | recommendation-service | medium | TBD | TBD | — | — | phase_3 |
| 16 | source-ingestion-service | **high** | TBD | TBD | — | TBD | phase_3 |
| 17 | ua-mcp-server | medium | TBD | TBD | — | — | phase_4 |
| 18 | wecom-adapter | **high** | TBD | TBD | TBD | TBD | phase_2 |
| 19 | wecom-aibot-bridge | **high** | TBD | TBD | TBD | TBD | phase_4 |
| 20 | workflow-service | medium | TBD | TBD | — | — | phase_4 |

> `uploads/` is static file storage — not a service and excluded from the ownership matrix.

## Key

| Field | Required For | Rule |
|-------|-------------|------|
| `code_owner` | all services | Primary code reviewer for PRs |
| `runtime_owner` | all services | On-call for availability, alerts, rollback |
| `security_reviewer` | **high** sensitivity | Security review for auth, PII, LLM input/output |
| `data_reviewer` | **high** sensitivity (data-oriented) | RLS, audit log, data permission review |

**High-sensitivity** services (must have at least one of `security_reviewer` or `data_reviewer`):
`audit-service`, `auth-service`, `crm-service`, `db-policy-service`, `knowledge-graph-service`, `knowledge-service`, `llm-gateway`, `permission-service`, `source-ingestion-service`, `wecom-adapter`, `wecom-aibot-bridge`.

## Dependency Map

```
api-gateway
 ├── agent-orchestrator
 │    ├── llm-gateway (sole LLM caller)
 │    ├── rag-service
 │    │    ├── knowledge-service (JSON index)
 │    │    └── db-policy-service (PostgreSQL RLS)
 │    ├── permission-service
 │    ├── compliance-service
 │    ├── crm-service
 │    └── recommendation-service
 ├── auth-service
 │    ├── wecom-adapter
 │    └── workflow-service (campus_domain)
 └── knowledge-graph-service

mealbot-service
 ├── wecom-adapter
 └── workflow-service (campus_domain)

source-ingestion-service → knowledge-service

ua-mcp-server → knowledge-graph-service

wecom-aibot-bridge → api-gateway

audit-service (not yet implemented)
uploads/ (data only, no runtime dependency)
```

## Notes

- `api-gateway` is the current monolithic entry point being replaced by the Go control plane via Strangler Fig migration.
- `llm-gateway` is the **sole** service allowed to call external LLM APIs.
- `db-policy-service` is the **sole** service that defines database roles and RLS policies.
- No service currently has a `pyproject.toml` — packaging is tracked as future work.
- `audit-service` and `workflow-service` have no tests yet.
