# GaokaoAgent

GaokaoAgent 是一个面向高考志愿、招生咨询、知识检索、合规审核、CRM 跟进和校园运营场景的 AI Agent 平台。项目采用多服务架构，核心 AI 能力仍由 Python 服务承载；HTTP 路由、控制面、shadow proxy、cutover readiness 等稳定性相关能力正在逐步迁移到 Go control plane。

当前工程重点不是一次性重写业务逻辑，而是通过 contract、static gates、shadow gateway、parity harness、evidence bundle 和 staged cutover plan，逐步将系统从 Python gateway 主导的控制面演进为 Go control plane + Python capability services 的结构。

---

## Current Status

当前迁移状态：

```text
PR-1   route contract + freeze gates                         ✅
PR-2A  Go shadow gateway skeleton                            ✅
PR-2B  /api/gaokao/chat transparent proxy                    ✅
PR-2C  parity harness                                        ✅
PR-2D  sanitized parity fixtures + privacy gate              ✅
PR-3A  admin remediation contract                            ✅
PR-3B  POST replacements + deprecated GET aliases            ✅
PR-3C  admin console POST + legacy usage tracking            ✅
PR-3D  POST-only admin shadow proxy allowlist                ✅
PR-3E  admin POST parity fixtures                            ✅
PR-4A  deployment wiring                                     ✅
PR-4B  dry-run tooling + safety defaults                     ✅
PR-4C  external mirror driver                                ✅
PR-4D  shadow evidence policy + checker                      ✅
PR-5A  controlled ingress cutover design + readiness gate     ✅
PR-5B  cutover observability contract                        ✅
PR-5C  shadow evidence bundle                                ✅
PR-6A  staging ingress config disabled by default            ✅
PR-6B  staging header-based canary config                    ✅
PR-6C  staging header canary evidence path                   ✅
PR-6D  staging percentage canary config, weight=0            ✅
PR-6E  staging 1% percentage canary evidence capability      ✅
```

Important: PR-6E provides the capability to run staging 1% percentage canary evidence. It does not mean real staging 1% evidence has passed. PR-6F must not start until a real staging report has `status: passed`.

---

## Architecture

High-level target architecture:

```text
Client / Admin Console
        |
        v
Go Control Plane
  - routing
  - request id
  - timeout
  - body limit
  - proxy allowlist
  - shadow/canary controls
  - structured logging
  - cutover readiness
        |
        v
Python Capability Services
  - api-gateway legacy upstream
  - agent-orchestrator
  - rag-service
  - llm-gateway
  - compliance-service
  - crm-service
  - knowledge-service
        |
        v
Postgres / LLM Provider / Knowledge Store
```

Design principle:

```text
Go owns deterministic control-plane behavior.
Python owns high-velocity AI, RAG, policy, evaluation, and domain capabilities.
```

The Go gateway must not duplicate Python business logic. It acts as a controlled routing and proxy layer with explicit allowlists and evidence-based cutover.

---

## Repository Layout

```text
apps/
  admin-console/                 # Admin web console

configs/
  cutover_policy.yaml             # Controlled ingress cutover policy
  observability_contract.yaml      # Required/forbidden observability fields
  *.yaml                           # Domain and policy configuration

contracts/
  routes.yaml                      # Route source of truth
  openapi/                         # Public/admin/campus/CRM OpenAPI baselines
  schemas/                         # Contract schemas
  python_control_plane_allowlist.json

control-plane/
  cmd/gaokao-gateway/              # Go shadow gateway entrypoint
  internal/
    config/
    contract/
    gatewayhttp/
    observability/
    parity/
    transport/
  tests/                           # Go gateway tests
  Dockerfile
  .dockerignore

deploy/
  staging/
    ingress/                       # Staging ingress examples and canary config

docs/
  runbooks/                        # Migration, canary, cutover, evidence runbooks
  CONTROL_PLANE_MIGRATION.md

reports/
  shadow/                          # Local/staging shadow reports; artifacts ignored
  staging/                         # Staging canary reports; artifacts ignored

scripts/
  run_shadow_dry_run.sh
  run_staging_header_canary_evidence.sh
  run_staging_percentage_canary_evidence.sh
  collect_shadow_health.sh
  collect_legacy_usage_summary.sh

services/
  api-gateway/
  agent-orchestrator/
  rag-service/
  llm-gateway/
  compliance-service/
  crm-service/
  knowledge-service/
  permission-service/
  evaluation-service/
  db-policy-service/

tests/
  parity/
  replay/
  security/

tools/
  check_route_contract.py
  check_python_control_plane_freeze.py
  check_admin_console_legacy_get_usage.py
  check_parity_fixtures.py
  check_shadow_evidence.py
  check_cutover_readiness.py
  check_observability_contract.py
  check_staging_ingress_config.py
  build_shadow_evidence_bundle.py
  render_staging_percentage_canary_config.py
  collect_staging_percentage_canary_result.py
  shadow_mirror_driver.py
```

---

## Core Contracts

### Route Source of Truth

All HTTP routes must be registered in:

```text
contracts/routes.yaml
```

The route contract records:

```text
method
path
surface
owner
auth
csrf
audit
rate_limit
migration wave
legacy flags
replacement route
usage tracking
```

No new route should be added directly to Python gateway code without a route contract update.

Run:

```bash
make test-route-contract
make route-inventory
```

Expected current inventory:

```text
115 routes
legacy gaps 0
state-changing GET gaps 0
deprecated compatibility aliases 5
legacy usage tracking enabled 5
unmapped openapi paths 0
```

### Admin Legacy GET Mutations

Historical state-changing `GET` admin mutations have been remediated:

```text
GET aliases remain for compatibility.
POST replacements are canonical.
GET aliases emit deprecation headers.
GET alias usage is tracked.
Go shadow gateway must not proxy deprecated GET aliases.
```

Deprecated GET alias must not appear in any cutover allowlist.

---

## Control Plane Rules

These constraints are hard rules:

```text
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

## Local Development

### Python checks

```bash
make test-route-contract
make route-inventory
make test-python-control-plane-freeze
make test-parity-fixtures
make check-admin-proxy-guard
make test-admin-console-no-legacy-get
```

### Go control-plane checks

Make sure Go is available:

```bash
go version
```

Run:

```bash
PATH=/usr/local/go/bin:$PATH make test-go-gateway
PATH=/usr/local/go/bin:$PATH make test-go-parity-unit
PATH=/usr/local/go/bin:$PATH make test-go-admin-shadow-proxy
PATH=/usr/local/go/bin:$PATH make test-go-admin-parity-unit
```

### Admin Python regression

```bash
python3 -m pytest \
  services/api-gateway/tests/admin_gateway_test.py \
  services/api-gateway/tests/admin_security_regression_test.py
```

---

## Go Shadow Gateway

Build:

```bash
make build-go-shadow-gateway
```

Run shadow gateway with proxy disabled:

```bash
make run-go-gateway-shadow
```

Smoke test:

```bash
make smoke-go-shadow-gateway
```

Default safety posture:

```text
shadow mode: true
proxy enabled: false
proxy routes: empty
admin proxy: disabled unless explicitly configured
```

---

## Shadow Proxy

The Go gateway supports explicit shadow proxy routes only. Current supported surfaces include:

```text
POST /api/gaokao/chat
5 admin POST replacement routes
```

Admin deprecated GET aliases are blocked by design:

```text
GET deprecated admin alias -> 405 DEPRECATED_ROUTE_NOT_PROXIED
```

Go does not reimplement full auth/RBAC/CSRF during shadow stages. Missing CSRF is transparently proxied to Python, and Python remains the authority for that decision.

---

## Parity and Mirror Evidence

### Parity

Fixtures live under:

```text
tests/parity/
```

Run unit parity:

```bash
make test-go-parity-unit
make test-go-admin-parity-unit
```

Run live parity only when legacy and shadow base URLs are available:

```bash
PYTHON_LEGACY_BASE_URL=http://127.0.0.1:8787 \
GO_SHADOW_BASE_URL=http://127.0.0.1:8788 \
make parity-gaokao-chat

PYTHON_LEGACY_BASE_URL=http://127.0.0.1:8787 \
GO_SHADOW_BASE_URL=http://127.0.0.1:8788 \
make parity-admin-post-replacements
```

### External Mirror Driver

The external mirror driver is evidence tooling only. It does not modify runtime behavior.

Run:

```bash
make shadow-mirror-dry-run
```

Reports:

```text
reports/shadow/mirror-latest.json
reports/shadow/mirror-latest.md
```

Reports must not include:

```text
raw request body
raw response body
Authorization
Cookie
Set-Cookie
raw IP
raw user ID
real student / parent / school data
```

---

## Shadow Dry Run

Run local dry-run:

```bash
make shadow-dry-run
```

In local mode, live parity may be skipped. A skipped report is valid for local development but does not satisfy strict staging evidence.

Check evidence:

```bash
make check-shadow-evidence
```

Strict evidence is for staging only:

```bash
make check-shadow-evidence-strict
```

---

## Evidence Bundle

Build local/staging evidence bundle:

```bash
make shadow-evidence-bundle
```

Test bundle tooling:

```bash
make test-shadow-evidence-bundle
```

Bundle output is ignored by git:

```text
reports/shadow/bundles/*
```

Only `.gitkeep` is tracked.

---

## Cutover Readiness

Policy:

```text
configs/cutover_policy.yaml
```

Default readiness check:

```bash
make check-cutover-readiness
```

Strict readiness check requires real staging evidence:

```bash
make check-cutover-readiness-strict
```

Local dry-run reports are expected to fail strict readiness if live parity/mirror is missing.

Allowed cutover routes are explicit. Admin wildcards and deprecated GET aliases are blocked.

---

## Observability Contract

Observability contract:

```text
configs/observability_contract.yaml
```

Check:

```bash
make check-observability-contract
```

Required request log fields include:

```text
request_id
method
path
path_template
surface
route_owner
status
latency_ms
upstream_status
upstream_latency_ms
proxy_mode
shadow_proxy_enabled
error_code
```

Forbidden fields include:

```text
Authorization
Cookie
Set-Cookie
raw_request_body
raw_response_body
raw_ip
raw_user_id
student_name
parent_phone
document_contents
```

---

## Staging Ingress

Staging ingress config examples:

```text
deploy/staging/ingress/go-gateway-shadow.example.yaml
deploy/staging/ingress/go-gateway-shadow.header-canary.example.yaml
deploy/staging/ingress/go-gateway-shadow.percentage-canary.example.yaml
```

Check disabled default config:

```bash
make check-staging-ingress-config
```

Check header canary config:

```bash
make check-staging-header-canary-config
```

Check percentage canary config:

```bash
make check-staging-percentage-canary-config
```

Rules:

```text
No production host
No wildcard route
No GET admin route
No /api/admin/* wildcard
Default weight must be 0
Percentage stages must be 1, 5, 25, 50, 100
```

---

## Staging 1% Percentage Canary Capability

PR-6E provides the capability to run staging 1% evidence collection.

Run only with real staging environment:

```bash
STAGING_ENV_CONFIRMED=true \
CANARY_PERCENT=1 \
make run-staging-1pct-canary-evidence
```

Without a real staging environment, the report must be:

```text
status: skipped or skipped_live_check
```

It must not be marked as `passed`.

Before moving to 5%, the report must satisfy:

```text
status: passed
percent: 1
rollback_verified: true
unexpected_diffs: 0
latency_fail_count: 0
legacy_get_usage_events: 0
deprecated_get_blocked: true
```

---

## Staging Is Not Necessarily Public

Staging can be:

```text
internal/VPN-only
staging.example.internal
localhost/compose
temporary preview environment
public URL with strict access control
```

Recommended default for this project:

```text
staging should be internal or access-controlled
no real student/parent sensitive data
no production secrets
no public admin mutation surface
```

---

## Release and Gate Philosophy

This project uses layered gates:

```text
contract gates
control-plane freeze gates
privacy gates
admin legacy usage gates
Go gateway tests
parity tests
shadow evidence checks
cutover readiness checks
observability contract checks
staging ingress config checks
```

Default release checks should not require live staging or production dependencies. Strict checks are reserved for staging/cutover procedures.

---

## Common Commands

```bash
make test-route-contract
make route-inventory
make test-python-control-plane-freeze
make test-parity-fixtures
make check-admin-proxy-guard
make test-admin-console-no-legacy-get
make check-shadow-evidence
make check-cutover-readiness
make check-observability-contract
make check-staging-ingress-config
make check-staging-header-canary-config
make check-staging-percentage-canary-config
```

Go:

```bash
PATH=/usr/local/go/bin:$PATH make test-go-gateway
PATH=/usr/local/go/bin:$PATH make test-go-parity-unit
PATH=/usr/local/go/bin:$PATH make test-go-admin-shadow-proxy
PATH=/usr/local/go/bin:$PATH make test-go-admin-parity-unit
```

Admin Python regression:

```bash
python3 -m pytest \
  services/api-gateway/tests/admin_gateway_test.py \
  services/api-gateway/tests/admin_security_regression_test.py
```

---

## Development Rules for Agents and Humans

Before editing:

```text
Read AGENTS.md
Check contracts/routes.yaml
Check docs/CONTROL_PLANE_MIGRATION.md
Check relevant runbook
```

When adding routes:

```text
Update contracts/routes.yaml
Update OpenAPI baseline
Update route contract tests
Do not add unregistered Python route branches
```

When touching admin mutation:

```text
Use POST canonical route
Require CSRF
Require audit
Do not reintroduce state-changing GET
Do not proxy deprecated GET alias
```

When adding parity or replay fixtures:

```text
Use synthetic IDs
No Authorization/Cookie/Set-Cookie
No real phone/email/id-card/student/parent data
No raw production logs
Run make test-parity-fixtures
```

When touching control plane:

```text
Do not add wildcard proxy
Do not enable proxy by default
Do not record raw payloads
Do not modify production ingress in non-cutover PRs
```

---

## Roadmap

Near-term:

```text
PR-6E-live-checks: replace placeholder live checks with real staging checks
PR-6F: staging 5% percentage canary evidence, only after 1% passed
PR-6G: staging 25% percentage canary evidence
PR-6H: staging 50% percentage canary evidence
PR-6I: staging 100% percentage canary evidence
```

Later:

```text
PR-7A: production canary config design
PR-7B: production internal canary
PR-7C: production 1% canary
PR-7D: production gradual ramp
PR-8A: Python gateway external exposure freeze
PR-8B: Python upstream surface inventory
PR-8C: capability service split
PR-9A: deprecated GET alias usage review
PR-9B: deprecated GET alias rejection
PR-9C: remove deprecated GET alias code
PR-9D: expand Go gateway route coverage
```

Long-term hardening:

```text
OpenAPI generated types
Go-side CSRF presence check
Go-side session presence check
Python sys.path.insert debt burn-down
RAG SQL boundary refactor
BFF / orchestrator decomposition
```

---

## Safety Summary

Do not proceed to production cutover unless all of the following are true:

```text
strict shadow evidence passed
strict cutover readiness passed
observability contract passed
staging canary evidence passed
legacy gaps = 0
state-changing GET gaps = 0
deprecated GET aliases not proxied
legacy GET usage = 0 or explicitly waived
rollback verified
no unexpected diffs
no latency fail
admin audit verified
```

Until then, Go gateway remains a shadow/canary control-plane component, and Python gateway remains the reliable fallback/upstream.
