# Go Control Plane Migration

The migration keeps the existing Python gateway live while establishing an externally compatible Go control plane in independently reversible waves.

## Phase 0 Baseline

This repository now treats the following files as the migration boundary:

- `contracts/routes.yaml` records the current gateway route surface, policy intent, legacy owner, and migration wave.
- `contracts/schemas/routes.schema.json` fixes the route contract shape for future Go loaders and review tooling.
- `contracts/openapi/*.yaml` publishes the HTTP contract baseline without changing current response bodies.
- `contracts/python_control_plane_allowlist.json` captures existing production `sys.path` debt; it may shrink but must not grow.
- `tools/check_route_contract.py` rejects new unregistered Python gateway dispatch branches and incomplete mutation policy declarations.
- `tools/check_python_control_plane_freeze.py` rejects new production path-splicing debt and runs the route contract guard.

The OpenAPI documents and route inventory use JSON syntax inside `.yaml` files. JSON is valid YAML and lets the checks run with the Python standard library only.

## Validation

Run the Phase 0 checks without starting dependent services:

```bash
make test-route-contract
make test-python-control-plane-freeze
make route-inventory
```

The established `make release-check` now runs these boundary checks first. `make release-check-control-plane` aliases that release path for migration automation; subsequent waves add Go gateway, shadow parity, and capability tests to it rather than bypassing the existing release chain.

## Known Legacy Debt

The Python gateway currently includes admin state-changing handlers reached through `GET` route branches. Their contract metadata requires CSRF at the control-plane boundary and records `legacy_flags=["legacy_policy_gap"]`.

Each legacy policy gap must include:

```json
{
  "target_phase": "PR-3",
  "allowed_until": "go_cutover_admin_shadow",
  "required_fix": "replace state-changing GET with POST or preserve GET as read-only compatibility alias"
}
```

## PR-1 Review Note

This PR is a migration guardrail PR, not a functional rewrite.

Not run:

- `make release-check`

Reason:

- It includes live DB, frontend, and benchmark integration chains.
- This PR only changes route contract metadata and static freeze gates.

Compensating checks:

- `python3 -m py_compile tools/check_route_contract.py tools/check_python_control_plane_freeze.py`
- `make test-route-contract`
- `make test-python-control-plane-freeze`
- Negative checks for an unregistered route and a new production `sys.path.insert`

## PR-2A Shadow Skeleton

PR-2A introduces the Go control-plane runtime without proxying business traffic or changing Python gateway behavior.

Included:

- `control-plane/` Go module.
- `contracts/routes.yaml` loader and validator.
- Request ID, structured logging, panic recovery, timeout, and body limit middleware.
- Go-owned `GET /api/health`.
- JSON error envelope for Go gateway errors.

Not included:

- No production traffic cutover.
- No Python `server.py` edits.
- No business proxy route.
- No DB ownership.
- No auth, CSRF, RBAC, BFF, RAG, or LLM rewrite.

Validation:

```bash
make test-route-contract
make test-python-control-plane-freeze
make route-inventory
make test-go-gateway
```

`make release-check-control-plane` now extends the existing release chain with `make test-go-gateway`.

Run locally in shadow mode:

```bash
make run-go-gateway-shadow
```

## PR-2B One-Route Proxy

PR-2B adds one transparent shadow proxy route for `POST /api/gaokao/chat`.

Included:

- A Python upstream transport that preserves method, path, query, body, and business response status/body.
- Forwarding of `content-type`, `accept`, `authorization`, `cookie`, `x-csrf-token`, and `x-request-id`.
- Injection of `x-request-id`, `x-forwarded-host`, `x-forwarded-proto`, `x-forwarded-for`, and `x-gaokao-gateway-mode: shadow`.
- Gateway-owned errors for disabled proxy route, upstream timeout, upstream unavailable, and oversized request bodies.

Not included:

- No admin route proxy.
- No auth, RBAC, or CSRF behavior change.
- No Python response normalization.
- No DB access.
- No production traffic cutover.

Default state:

- Shadow proxy is disabled unless explicitly enabled with `--shadow-proxy-enabled true`.
- Allowed proxy routes are empty unless `--shadow-proxy-routes` is set.

Validation:

```bash
make test-go-gateway
make test-route-contract
make test-python-control-plane-freeze
make route-inventory
```

Run the one-route proxy locally:

```bash
make run-go-gateway-shadow-proxy
```

## PR-2C Parity Harness

PR-2C adds a repeatable parity harness for `POST /api/gaokao/chat`.

Included:

- Fixture-driven parity cases under `tests/parity/`.
- A Go parity runner that executes the same request against legacy Python and Go shadow.
- Normalization for JSON field order, compatible `content-type`, ignored volatile headers, and latency ratio warnings.
- Unit parity using `httptest` and optional live parity using configured base URLs.

Not included:

- No second proxy route.
- No admin parity.
- No release-check dependency on live upstream startup.
- No auth, CSRF, RBAC, DB, or admin gap work.

Validation:

```bash
make test-go-gateway
make test-go-parity-unit
make test-route-contract
make test-python-control-plane-freeze
make route-inventory
```

Optional live parity:

```bash
make parity-gaokao-chat GO_SHADOW_BASE_URL=http://127.0.0.1:8788 PYTHON_LEGACY_BASE_URL=http://127.0.0.1:8787
```

## PR-2D Sanitized Real Traffic Fixtures

PR-2D keeps the runtime unchanged and tightens only the parity-fixture layer for `POST /api/gaokao/chat`.

Included:

- Add fixture categories for deterministic errors, deterministic policy cases, and nondeterministic success cases.
- Add privacy metadata requirements to every parity case.
- Add sanitized real-traffic fixture coverage under `tests/parity/gaokao_chat_real_sanitized.yaml`.
- Redact parity report bodies while preserving body length and digest for debugging.
- Add static fixture privacy scanning with `make test-parity-fixtures`.

Not included:

- No new proxy routes.
- No proxy behavior change.
- No admin migration work.
- No live parity requirement in default CI.

Validation:

```bash
make test-go-gateway
make test-go-parity-unit
make test-parity-fixtures
make test-route-contract
make test-python-control-plane-freeze
make route-inventory
```

Optional live parity with sanitized fixtures:

```bash
make parity-gaokao-chat \
  GO_SHADOW_BASE_URL=http://127.0.0.1:8788 \
  PYTHON_LEGACY_BASE_URL=http://127.0.0.1:8787 \
  PARITY_FIXTURE_PATH=../../tests/parity/gaokao_chat_real_sanitized.yaml
```

## PR-3A Admin Legacy Mutation Remediation

PR-3A is contract-only. It documents and gates the five legacy admin `GET` mutation gaps without changing runtime behavior.

Included:

- Add `state_changing_get` as an explicit legacy flag.
- Add `legacy_exit.cutover_blocker=true` for each legacy admin GET mutation.
- Add planned `POST` replacement contracts for the five admin mutation gaps.
- Add a dedicated remediation note at `docs/ADMIN_LEGACY_MUTATION_REMEDIATION.md`.
- Extend `make route-inventory` with a `state-changing GET gaps` count.

Not included:

- No runtime handler changes.
- No new admin proxy routes.
- No deprecation headers yet.
- No traffic cutover.

Validation:

```bash
make test-route-contract
make route-inventory
```

The migration blocker remains the same: the admin shadow/cutover path stays blocked until the legacy GET mutation gaps are actually remediated in PR-3B or explicitly waived.

## PR-3B POST Replacements And Deprecated GET Aliases

PR-3B implements the five admin `POST` replacement routes while keeping the matching `GET` routes as deprecated compatibility aliases.

Included:

- Add `POST` replacements for cancel, validate, approve, reject, and publish.
- Keep the legacy `GET` aliases available without introducing Go admin proxying.
- Add `Deprecation`, `Sunset`, `Link`, and `X-Gaokao-Legacy-Route` headers to the legacy aliases.
- Mark replacement status as `implemented` in `contracts/routes.yaml`.
- Update route inventory to distinguish deprecated aliases from unresolved state-changing GET gaps.

Not included:

- No admin shadow gateway.
- No traffic cutover.
- No forced CSRF on legacy `GET` aliases.
- No removal of the compatibility aliases.

Validation:

```bash
make test-route-contract route-inventory
make test-python-control-plane-freeze
make test-parity-fixtures
PATH=/usr/local/go/bin:$PATH make test-go-gateway test-go-parity-unit
python3 -m pytest services/api-gateway/tests/admin_gateway_test.py services/api-gateway/tests/admin_security_regression_test.py
```

## PR-4A Go Shadow Gateway Deployment Wiring

PR-4A connects the verified Go shadow gateway to local and staging deployment tooling without changing business logic or enabling production traffic.

Included:

- `control-plane/Dockerfile` for building a standalone Go gateway container.
- `.dockerignore` / `control-plane/.dockerignore` to keep the build context clean.
- `docker-compose.shadow.yml` with the `go-shadow-gateway` service.
- Enhanced `GET /api/health` with `deprecated_compatibility_alias_count`.
- `make build-go-shadow-gateway` — builds the Docker image.
- `make smoke-go-shadow-gateway` — build, start, health-check, and tear-down smoke test.

Not included:

- No production traffic cutover.
- No admin shadow proxy enabled by default.
- No live parity as a required release check.
- No DB access from Go gateway.
- No Python gateway behavior changes.
- No admin console changes.

Default state:

- Shadow mode is on (`SHADOW_MODE=true`).
- Shadow proxy is off (`SHADOW_PROXY_ENABLED=false`).
- Shadow proxy routes are empty (`SHADOW_PROXY_ROUTES=""`).
- Deprecated GET aliases return `405 DEPRECATED_ROUTE_NOT_PROXIED` when admin proxy is enabled.

Run modes:

```bash
make build-go-shadow-gateway

make run-go-gateway-shadow
make run-go-gateway-shadow-proxy
make run-go-admin-shadow-proxy

make smoke-go-shadow-gateway
```

Docker compose shadow:

```bash
make shadow-up
```

Admin shadow proxy override:

```bash
SHADOW_PROXY_ENABLED=true \
SHADOW_PROXY_ROUTES="POST /api/admin/ingestion/runs/{run_id}/cancel,..." \
make shadow-up
```

Validation:

```bash
make test-route-contract route-inventory
make check-admin-proxy-guard
make test-admin-console-no-legacy-get
make test-python-control-plane-freeze
make test-parity-fixtures
PATH=/usr/local/go/bin:$PATH make test-go-gateway test-go-parity-unit test-go-admin-shadow-proxy test-go-admin-parity-unit
python3 -m pytest services/api-gateway/tests/admin_gateway_test.py services/api-gateway/tests/admin_security_regression_test.py
make build-go-shadow-gateway
make smoke-go-shadow-gateway
```

## PR-4C Staging-Only External Mirror Driver

PR-4C adds an external replay driver for staging and local evidence collection. It compares sanitized requests against the legacy Python gateway and the Go shadow gateway without changing either runtime.

Included:

- `tools/shadow_mirror_driver.py` for JSONL replay and parity-fixture replay.
- `tests/replay/shadow_mirror_sample.jsonl` as a checked-in sanitized sample.
- `docs/runbooks/SHADOW_MIRRORING.md` for mirror-only operation.
- `make shadow-mirror-dry-run`, `make shadow-mirror-chat`, and `make shadow-mirror-admin`.
- Redacted JSON and Markdown reports at `reports/shadow/mirror-latest.*`.

Not included:

- No Python gateway changes.
- No Go proxy runtime changes.
- No allowlist expansion.
- No ingress hookup or automatic production mirroring.
- No live mirror in the default `release-check`.

Safety defaults:

- Dry-run works without live services.
- Reports include only case name, method/path, statuses, latency, diff category, and redacted body summaries.
- Raw request and response bodies are never written to the report.
- Report artifacts remain ignored by git except `reports/shadow/.gitkeep`.

Validation:

```bash
make test-route-contract route-inventory
make test-python-control-plane-freeze
make test-parity-fixtures
PATH=/usr/local/go/bin:$PATH make test-go-gateway test-go-parity-unit test-go-admin-shadow-proxy test-go-admin-parity-unit
python3 -m pytest services/api-gateway/tests/admin_gateway_test.py services/api-gateway/tests/admin_security_regression_test.py
python3 -m pytest tests/security/test_shadow_mirror_driver.py
make shadow-mirror-dry-run
```

## PR-5A Controlled Ingress Cutover Design

PR-5A defines the future Go gateway ingress cutover policy without changing ingress, production compose, Go runtime, Python runtime, admin console, or route behavior.

Included:

- `configs/cutover_policy.yaml` in `design_only` mode.
- `tools/check_cutover_readiness.py` for policy and route-reference validation.
- `docs/runbooks/CONTROLLED_INGRESS_CUTOVER.md` for cutover stages, evidence gates, and rollback triggers.
- `make check-cutover-readiness` and `make check-cutover-readiness-strict`.

Not included:

- No ingress config changes.
- No production traffic cutover.
- No Go proxy runtime changes.
- No Python gateway changes.
- No deprecated GET alias removal.
- No strict readiness check in the default `release-check`.

Validation:

```bash
make test-route-contract route-inventory
make check-admin-proxy-guard
make test-admin-console-no-legacy-get
make test-python-control-plane-freeze
make test-parity-fixtures
make check-shadow-evidence
make check-cutover-readiness
PATH=/usr/local/go/bin:$PATH make test-go-gateway test-go-admin-shadow-proxy test-go-admin-parity-unit
python3 -m pytest tests/security/test_cutover_readiness.py
python3 -m pytest services/api-gateway/tests/admin_gateway_test.py services/api-gateway/tests/admin_security_regression_test.py
```

`check-cutover-readiness-strict` is reserved for staging evidence after live parity and live mirror reports exist.
