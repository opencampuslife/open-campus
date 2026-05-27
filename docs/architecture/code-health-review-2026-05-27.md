# Code Health Review — 2026-05-27

## Scope

This review summarizes the static code-tree assessment performed against `docs/codegraph.html` after the Go control-plane migration work was partially applied.

The code graph is useful as an architectural signal, not as a substitute for CI, unit tests, contract tests, type checks, or live staging evidence.

## Score

- Static codegraph baseline: **72 / 100**
- Revised current-state assessment after confirming this tree is derived from the Go control-plane migration plan: **78–82 / 100**

The revised score reflects that `control-plane/`, `contracts/`, route inventory, shadow/canary/parity tooling, release-gate checks, and security regression tests are already visible in the repository.

## Interpretation

The second architecture description is the target blueprint and evaluation yardstick. The current codegraph is the partially implemented result of that blueprint. For project-state assessment, the codegraph is more authoritative because it reflects actual files. For direction and end-state quality, the blueprint remains the stronger model.

Current state:

```text
Architecture direction: healthy
Engineering hygiene: medium, improving
Production maintainability: improving but not complete
Migration phase: middle state from Python-heavy gateway toward Go control plane + Python capability services
```

## Positive Signals

- Service and domain grouping is clear.
- Static import graph does not show import cycles.
- Cross-service direct import count is zero in the parsed import graph.
- Test files are visible across gateway, RAG, LLM, compliance, permission, CRM, security, release-gate, parity, and control-plane areas.
- Go `control-plane/` exists and appears to be carrying shadow gateway, parity, router, middleware, and transport concerns.
- `contracts/` exists and includes route/OpenAPI contract assets.
- Shadow, canary, parity, cutover-readiness, evidence, and security tooling are already present.

## Main Risks

### 1. Static graph sparsity

The codegraph reported many isolated nodes. This should not be interpreted as true architectural isolation. The analyzer likely under-represents Go, TS/TSX, YAML, SQL, shell scripts, route maps, OpenAPI contracts, and dynamic Python imports.

### 2. Python gateway still exists

`services/api-gateway/src/server.py` and related BFF files still represent legacy control-plane debt. The goal is not immediate deletion, but continued reduction to legacy/proxy compatibility while Go owns deterministic routing, timeout, body limit, request ID, proxy allowlist, and cutover readiness.

### 3. Python package boundary debt

Production code still contains `sys.path.insert` style import-path manipulation. This lowers deploy determinism and makes local/CI/container behavior harder to reason about.

### 4. Protocol detection noise

The current codegraph protocol scanner can confuse unrelated tokens with SQL or protocol usage, including:

- HTML `<select>`
- Python `.update(...)`
- HTTP method names such as `DELETE`
- `sys.path.insert(...)`
- hash object `.update(...)`

The scanner should distinguish confirmed, weak, and false-positive-suspect evidence.

### 5. Service-level testing is uneven

Global test count is a useful signal, but individual services still need explicit minimum test matrices. Knowledge, campus/mealbot, RAG SQL policy, and gateway/BFF decomposition need especially clear coverage gates.

## Priority Remediation Plan

### P0 — Establish real health baseline

Run and enforce:

```bash
pytest
go test ./...
npm test
npm run typecheck
npm run lint
make test-route-contract
make test-python-control-plane-freeze
make ci-policy-check
make release-check-control-plane
```

Acceptance:

```text
The project has a reproducible health baseline in CI.
Failures identify service and check category.
```

### P1 — Enforce package boundary

- Add `tools/check_package_boundary.py`.
- Fail if `sys.path.append`, `sys.path.insert`, or `sys.path.extend` appears under `services/*/src`.
- Allow test-only path setup only in controlled test bootstrap files.

Acceptance:

```text
python tools/check_package_boundary.py --root . returns OK.
```

### P1 — Freeze Python gateway growth

- Add `tools/check_gateway_freeze.py`.
- Fail on new `path.startswith` / `path.endswith` route branches in `services/api-gateway/src/server.py` unless explicitly allowlisted.
- Fail on new `BaseHTTPRequestHandler` or `ThreadingHTTPServer` definitions outside the approved legacy file.

Acceptance:

```text
New routes must be represented in contracts/routes.yaml and handled through the control-plane migration path.
```

### P1 — Improve protocol detection

- Split evidence into `confirmed`, `weak`, and `false-positive-suspect`.
- Tighten SQL matching to DB imports, `.execute(...)` with real SQL, SQL files, migrations, and explicit Postgres/DATABASE_URL signals.
- Exclude UI tags and generic method names.

Acceptance:

```text
Codegraph stops marking <select>, dict.update, hash.update, and sys.path.insert as SQL.
```

### P2 — Add service test matrix

Create `docs/testing/service-test-matrix.md` and use it to define minimum unit, contract, security, policy, migration, and parity requirements per service.

Acceptance:

```text
Each service has a declared minimum test surface and matching Makefile/CI target.
```

## Target State

```text
Go owns deterministic control-plane behavior.
Python owns AI/RAG/policy/evaluation/domain capability services.
contracts/routes.yaml and OpenAPI are the route source of truth.
No production sys.path mutation.
No new Python http.server route logic.
Protocol evidence is auditable and low-noise.
Release gates enforce route, package, SQL, prompt, and policy boundaries.
```
