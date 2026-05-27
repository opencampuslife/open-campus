# Service Test Matrix

This matrix defines the minimum test surface for each service. It complements global test count; it is intended to prevent individual service blind spots.

## Minimum Categories

| Category | Meaning |
|---|---|
| Unit | Pure function/module tests with local fixtures |
| Contract | Route, schema, OpenAPI, RPC, or payload compatibility tests |
| Security | Auth, CSRF, injection, redaction, privacy, or permission bypass tests |
| Policy | Data scope, RLS, role, compliance, or deny-by-default tests |
| Migration | Database migration, fixture, or backward compatibility tests |
| Parity | Go/Python, shadow/legacy, or old/new endpoint response equivalence tests |
| E2E | Small end-to-end smoke path using realistic service composition |

## Matrix

| Service / Area | Required Tests | Priority |
|---|---|---|
| `control-plane` | Contract, parity, middleware, timeout/body-limit, proxy allowlist, panic recovery | P0 |
| `services/api-gateway` | Route contract, auth/CSRF, error model, legacy compatibility, admin mutation audit | P0 |
| `services/agent-orchestrator` | Intent classification, pipeline stages, compliance gate, audit emission, empty/denied retrieval path | P1 |
| `services/rag-service` | SQL builder, parameterization, data-scope policy, citation builder, empty result, low-confidence result | P0 |
| `services/llm-gateway` | Prompt guard, redactor, provider contract, fallback, prompt-injection regression | P0 |
| `services/compliance-service` | Allow/deny matrix, rewrite behavior, evidence logging, unsafe output rejection | P1 |
| `services/permission-service` | Role scope, data level, campus scope, deny by default, invalid role handling | P1 |
| `services/db-policy-service` | Migration, fixture load, RLS live checks, DB role isolation, SECURITY INVOKER policy | P0 |
| `services/knowledge-service` | Frontmatter parser, loader, chunker, validator, indexer, malformed document handling | P1 |
| `services/crm-service` | Handoff, lead profile sync, merge policy, next-best-action, PII-safe summary | P1 |
| `services/evaluation-service` | Benchmark case loading, scoring, regression thresholds, report output | P2 |
| `services/mealbot-service` | Session flow, permission checks, data isolation, campus module flows, WeCom inbound | P1 |
| `apps/admin-console` | POST-only admin mutations, legacy GET absence, role UI states, API client compatibility | P1 |
| `tests/security` | Release gate, prompt injection, admin regression, privacy/evidence redaction | P0 |
| `scripts` / `tools` | Dry-run behavior, staging evidence validation, no live side effects in default checks | P1 |

## Hard Gates

These gates should fail CI when violated:

```text
New endpoint -> routes.yaml/OpenAPI update required
New admin mutation -> audit=true and csrf=true required
New SQL path -> policy/RLS test required
New prompt construction -> prompt-injection regression required
New Python production import hack -> package-boundary check fails
New Python gateway route branch -> gateway-freeze check fails
New cross-service direct import -> import-boundary check fails
```

## Suggested Make Targets

```bash
make test-route-contract
make test-python-control-plane-freeze
python tools/check_package_boundary.py --root .
python tools/check_gateway_freeze.py --root . --allow-existing
make ci-policy-check
make test-security
make test-go-gateway
make test-parity-fixtures
```

## Review Checklist

- Does the change add or alter a route?
- Does the route have `owner`, `auth`, `csrf`, `audit`, and `rate_limit` metadata?
- Does the change alter SQL, RLS, data scope, or retrieval policy?
- Does it touch prompt construction or LLM provider behavior?
- Does it add a package boundary workaround?
- Does it add observability without leaking raw payloads, credentials, or personal data?
