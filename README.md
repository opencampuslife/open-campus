# Metacampus — AI Agent Platform for Gaokao Admissions & Campus Operations

[![release-check](https://github.com/opencampuslife/metacampus/actions/workflows/release-check.yml/badge.svg)](https://github.com/opencampuslife/metacampus/actions/workflows/release-check.yml)
[![go-control-plane](https://github.com/opencampuslife/metacampus/actions/workflows/go-control-plane.yml/badge.svg)](https://github.com/opencampuslife/metacampus/actions/workflows/go-control-plane.yml)
[![CodeQL](https://github.com/opencampuslife/metacampus/actions/workflows/codeql.yml/badge.svg)](https://github.com/opencampuslife/metacampus/actions/workflows/codeql.yml)
[![Dependency Review](https://github.com/opencampuslife/metacampus/actions/workflows/dependency-review.yml/badge.svg)](https://github.com/opencampuslife/metacampus/actions/workflows/dependency-review.yml)

Metacampus is a multi-service AI agent platform for college admissions consulting, knowledge retrieval, compliance auditing, CRM follow-up, and campus lifecycle management. It serves thousands of students, parents, and staff across a full admissions cycle — from inquiry through enrollment and daily campus operations.

> **License Notice**: This repository is **source-available, proprietary software**.
> Public visibility does not grant any right to use, modify, or redistribute the code.
> See [License](#license) for details.

---

## Technical Architecture

The platform is built on a **heterogeneous language runtime** that separates concerns along two axes:

```
Go Control Plane (deterministic routing & stability)
    │
    ├── HTTP routing, request ID, timeout, body limit
    ├── Rate limiting, circuit breaking, connection pooling
    ├── Shadow proxy, parity harness, evidence bundle
    ├── Header canary, percentage canary, deterministic bucketing
    ├── Cutover readiness evaluation & staged migration
    │
    ▼
Python Capability Services (high-velocity AI & domain logic)
    │
    ├── agent-orchestrator      (behavior tree FSM, multi-turn dialogue)
    ├── rag-service              (hybrid retrieval, knowledge indexing)
    ├── llm-gateway              (model routing, prompt guard, tone policy)
    ├── compliance-service       (regulatory audit, privacy gate)
    ├── crm-service              (lead lifecycle, profile merge, follow-up)
    ├── knowledge-service        (source ingestion, knowledge graph)
    ├── recommendation-service   (admissions matching, scoring)
    ├── evaluation-service       (benchmarking, quality metrics)
    ├── mealbot-service          (campus meal management, OCR)
    ├── db-policy-service        (RLS, tenant isolation, audit log)
    └── api-gateway              (legacy routing, auth, CSRF — being phased out)
```

### Design Principle

> **Go owns deterministic control-plane behavior.
> Python owns high-velocity AI, RAG, policy, evaluation, and domain capabilities.**

The Go gateway never duplicates Python business logic. It operates as a controlled routing and proxy layer with explicit allowlists, independent connection pools, independent circuit breakers, and evidence-driven cutover decisions.

---

## Evidence-Driven Strangler Fig Migration

The platform is executing a **Strangler Fig migration** from a Python-monolithic gateway to a Go control plane + Python capability services architecture. This is not a big-bang rewrite — it is a staged, evidence-driven process with full observability and automated rollback capability.

### Migration Stages (Completed)

```
P0   Concurrency Hardening            ✅  160 total tests
PR-A Shadow Proxy Foundation          ✅  12 tests — async traffic cloning
PR-B Parity Harness v1                ✅  10 tests — field-level diffing
PR-C Evidence Bundle Gate             ✅  12 tests — JSONL evidence, sensitive redaction
PR-D Header Canary                    ✅  17 tests — header-based traffic routing
PR-E Percentage Canary                ✅  16 tests — FNV-32a deterministic bucketing
PR-F Cutover Readiness                ✅  22 tests — phase aggregation, evaluator
```

### Key Technical Capabilities

| Capability | Description |
|---|---|
| **Shadow Proxy** | Async request cloning with independent connection pool, timeout, and circuit breaker. `X-Shadow-Mode` header injection. Never delays primary response. |
| **Parity Harness** | `captureResponseWriter` tees primary response; compares status, headers, and body against shadow via `json_required_fields` mode. Field-level diff classification. |
| **Evidence Bundle Gate** | JSONL-parity-event writer with mutex-protected `os.O_APPEND`. Five-condition gate (min_samples, status_match_rate, schema_match_rate, pass_rate, privacy_violations). Sensitive diff values redacted. Modes: strict, warn, off. |
| **Header Canary** | `X-Gaokao-Canary: go-control-plane` header-based traffic routing. Candidate upstream pool with independent circuit breaker. Canary headers stripped before forwarding. Priority over percentage canary. |
| **Percentage Canary** | Deterministic bucketing via `hash/fnv.New32a` (stdlib). Zero-alloc, same key = same bucket. Supports 1% → 5% → 25% → 50% → 100% staged ramp. `X-Gaokao-Canary-Key` header or request-ID key extraction. Bucket keys stripped before forwarding. |
| **Cutover Readiness** | Aggregates parity summary, phase reports, and evidence gate reports. Evaluates per-phase thresholds (5xx delta, P95 latency, privacy violations, business match rate). Requires rollback plan and owner approval. High-risk route classification. Machine-readable JSON output. |

### Request Flow (Full Chain)

```
Client Request
  → Rate Limit (global + per-route token bucket)
  → Route Match (contracts/routes.yaml)
  → Allowlist Check (explicit METHOD /path)
  → Canary Decision: Header Canary > Percentage Canary > Legacy
  → Upstream Circuit Breaker (per-pool)
  → Prepare Shadow (header sanitize, X-Shadow-Mode)
  → Primary Proxy (via captureResponseWriter)
  → Response to Client
  → Async Shadow Dispatch (independent timeout)
  → Parity Compare (field-level diff)
  → Evidence Write (JSONL)
```

### Decision Chain Priority

```
Header Canary (X-Gaokao-Canary match)
  → Percentage Canary (fnv(key) % 100 < percent)
  → Legacy (Python upstream)
```

All canary decisions are gated by evidence status. If evidence is required and the gate has not passed, traffic falls back to legacy automatically.

---

## Safety Architecture

### Independent Connection Pools

Legacy, shadow, and candidate upstreams each maintain their own `UpstreamPool` with independent:
- HTTP connection pool (`MaxConns`, `MaxInFlight`)
- Request timeout
- Circuit breaker (`FailureThreshold`, `CooldownDuration`)
- Health tracking

Failure in one pool never cascades to another.

### Circuit Breaker

Three-state design (closed → open → half-open) with configurable failure threshold and cooldown. Independent breakers per pool — shadow pool failure does not affect primary, candidate pool failure does not affect legacy.

### Rate Limiting

Dual-layer token bucket: global RPS + per-route RPS. Request ID generation on ingress; timeout enforcement with configurable global deadline.

### Observability Contract

Structured JSON logging with required fields:
```
request_id, method, path, path_template, surface, route_owner,
status, latency_ms, upstream_status, upstream_latency_ms,
proxy_mode, shadow_proxy_enabled, error_code,
canary_requested, canary_allowed, canary_reason,
primary_upstream, evidence_status, canary_type,
canary_percent, canary_bucket
```

Forbidden in logs: `Authorization`, `Cookie`, `Set-Cookie`, `raw_request_body`, `raw_response_body`, `raw_ip`, `raw_user_id`, `student_name`, `parent_phone`, `document_contents`.

---

## Route Contract System

### Source of Truth

All 115 HTTP routes are registered in `contracts/routes.yaml` with:

```yaml
method, path, surface, owner, auth, csrf, audit,
rate_limit, migration_wave, legacy_flags,
replacement_route, usage_tracking
```

No route may be added to Python gateway code without a contract update. This enables:
- Automated route inventory auditing
- Migration wave tracking
- Deprecated GET alias detection
- Controlled ingress cutover planning

### Admin Legacy Remediation

Five historical state-changing `GET` admin mutations have been fully remediated:
- POST replacements are canonical
- GET aliases emit deprecation headers and are usage-tracked
- Go shadow gateway blocks deprecated GET aliases with `405 DEPRECATED_ROUTE_NOT_PROXIED`

---

## Repository Layout

```
apps/admin-console/               Admin web console (TypeScript)
configs/                          Domain config, cutover policy, observability contract
contracts/                        Route source of truth, OpenAPI baselines
control-plane/                    Go control plane
  cmd/gaokao-gateway/             Entry point
  internal/
    config/                       Flag/env config loading
    contract/                     Route contract parser
    gatewayhttp/                  Router, shadow, parity, evidence, canary, readiness
    observability/                Structured JSON logger
    parity/                       Diff engine
    transport/                    Upstream pool, circuit breaker, request forwarding
  tests/                          Go integration tests
deploy/staging/ingress/           Staging ingress configs
docs/                             Architecture, runbooks, migration plan
reports/                          Evidence artifacts (gitignored)
scripts/                          Dry-run, evidence collection, health collection
services/                         Python capability services (20 services + uploads/)
tests/                            Cross-service test suites
tools/                            Contract checkers, evidence checkers, mirror drivers
```

---

## Test Infrastructure

```
go test ./...      160 PASS
go vet ./...       CLEAN
```

| Layer | Tests | Focus |
|---|---|---|
| `gatewayhttp` | 115 | Router, shadow, parity, evidence, canary, readiness |
| `transport` | 14 | Upstream pool, forwarding, timeout, race detection |
| `tests/` | 31 | Parity harness unit, admin shadow proxy, integration |

Race condition tests via `go test -race` (one pre-existing circuit breaker race identified, not from migration code).

---

## Hard Control Plane Rules

```
Do not add wildcard proxy /api/*
Do not add wildcard proxy /api/admin/*
Do not proxy deprecated GET aliases
Do not default-enable shadow proxy
Do not commit rendered canary configs with weight > 0
Do not output raw request or response bodies in reports
Do not put live staging checks into default release-check
Do not copy Python business logic into Go
Do not cut production without strict evidence
```

---

## Quick Start

```bash
# Python checks
make test-route-contract
make test-python-control-plane-freeze
make test-parity-fixtures

# Go control-plane checks
make test-go-gateway          # Full test suite (160 tests)
make test-go-readiness        # Cutover readiness evaluator (22 tests)
make test-go-evidence         # Evidence gate tests (12 tests)
make test-go-canary           # Header canary tests (17 tests)
make test-go-percentage       # Percentage canary tests (16 tests)
make test-go-shadow           # Shadow proxy tests
make test-go-parity           # Parity harness tests
make test-go-control-plane    # All Go targets

# Go shadow gateway
make build-go-shadow-gateway
make run-go-gateway-shadow
make smoke-go-shadow-gateway
```

---

## Staging & Evidence

```
# Staging ingress config checks
make check-staging-ingress-config
make check-staging-header-canary-config
make check-staging-percentage-canary-config

# Evidence
make shadow-evidence-bundle
make check-shadow-evidence

# Cutover readiness
make check-cutover-readiness
make check-cutover-readiness-strict
```

---

## Safety Gate Summary

Production cutover is gated on:

```
strict shadow evidence passed
strict cutover readiness passed
observability contract passed
staging canary evidence passed (1% → 5% → 25% → 50% → 100%)
legacy gaps = 0
state-changing GET gaps = 0
deprecated GET aliases not proxied
rollback plan verified
owner approval recorded
no unexpected diffs, latency failures, or privacy violations
```

Until all gates pass, the Go gateway operates as a shadow/canary control-plane component with Python gateway as the reliable upstream fallback.

---

## License

This project is **proprietary**. All rights reserved.

Public visibility of this repository does **not** grant any license to use, copy, modify, merge, publish, distribute, sublicense, or sell copies of the software. Unauthorized use, reproduction, or distribution is prohibited.
