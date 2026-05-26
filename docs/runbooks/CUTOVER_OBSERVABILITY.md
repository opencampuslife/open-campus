# Cutover Observability Runbook

## Scope

PR-5B defines the **observability contract** for Go gateway during controlled ingress cutover.
This runbook covers validation, log field requirements, and safe operating procedures.

**Does NOT change ingress. Does NOT cut traffic. Does NOT connect to Prometheus/Grafana.**

---

## Observability Contract

Defined in `configs/observability_contract.yaml`.

### Required Request Log Fields

Every Go gateway request log MUST include:

| Field | Type | Description |
|-------|------|-------------|
| `request_id` | string | Unique request ID (`req_` prefix) |
| `method` | string | HTTP method |
| `path` | string | Actual request path |
| `path_template` | string | Route template (e.g. `/api/admin/staging/docs/{doc_id}/validate`) |
| `surface` | string | `public` or `admin` |
| `route_owner` | string | Team owning the route |
| `status` | int | HTTP response status |
| `latency_ms` | int | Total request latency in milliseconds |
| `upstream_status` | int or null | Upstream HTTP status (null if not proxied) |
| `upstream_latency_ms` | int or null | Upstream latency (null if not proxied) |
| `proxy_mode` | string | `shadow`, `direct`, or `cutover` |
| `shadow_proxy_enabled` | bool | Whether shadow proxy is enabled |
| `error_code` | string or null | One of the defined error codes, or null |

### Admin Routes Additional Fields

| Field | Type | Description |
|-------|------|-------------|
| `auth_required` | bool | Whether auth is required |
| `csrf_required` | bool | Whether CSRF protection is enforced |
| `audit_required` | bool | Whether audit logging is required |
| `deprecated_route_denied` | bool | Whether a deprecated route was denied |
| `successor_route` | string or null | Successor route for deprecated endpoints |

### Forbidden Fields (Never Log)

These fields MUST NOT appear in any log:

- `authorization`, `cookie`, `set-cookie`
- `raw_request_body`, `raw_response_body`
- `raw_ip`, `raw_user_id`
- `student_name`, `parent_phone`, `document_contents`

### Allowed Metrics

| Metric Name | Labels |
|-------------|--------|
| `gaokao_gateway_requests_total` | method, path_template, surface, status |
| `gaokao_gateway_request_duration_ms` | method, path_template, surface |
| `gaokao_gateway_upstream_requests_total` | upstream, status |
| `gaokao_gateway_upstream_duration_ms` | upstream |
| `gaokao_gateway_errors_total` | code |
| `gaokao_gateway_deprecated_route_denied_total` | route |
| `gaokao_gateway_proxy_disabled_total` | route |

**Forbidden metric labels** (high cardinality): `raw_user_id`, `raw_ip`, `student_name`, `parent_phone`, `document_id`, `request_id`

---

## Validation

### Check Observability Contract

```bash
make check-observability-contract
```

Passes if:
- Contract YAML shape is valid
- All fixture logs contain required fields
- No forbidden fields appear in fixtures
- Admin fixtures include admin-specific fields
- Error codes are from the allowed set
- Metric names and labels match the contract

### Run All Checks (PR-5B Acceptance)

```bash
make test-route-contract route-inventory
make check-admin-proxy-guard
make test-admin-console-no-legacy-get
make test-python-control-plane-freeze
make test-parity-fixtures
make check-shadow-evidence
make check-cutover-readiness
make check-observability-contract
PATH=/usr/local/go/bin:$PATH make test-go-gateway test-go-admin-shadow-proxy test-go-admin-parity-unit
python3 -m pytest tests/security/test_observability_contract.py
python3 -m pytest services/api-gateway/tests/admin_gateway_test.py services/api-gateway/tests/admin_security_regression_test.py
```

---

## Go Gateway Log Field Enhancement

The Go gateway's `observability.Logger.Request()` now accepts additional context:

```go
type LogContext struct {
    PathTemplate      string
    Surface          string
    RouteOwner       string
    UpstreamStatus   *int
    UpstreamLatency  *int64
    ProxyMode        string
    ShadowProxyEnabled bool
    ErrorCode        *string
    AuthRequired     *bool
    CSRFRequired     *bool
    AuditRequired    *bool
    DeprecatedDenied *bool
    SuccessorRoute   *string
}

func (logger Logger) RequestWithContext(r *http.Request, status int, duration time.Duration, requestID string, ctx LogContext)
```

### Admin Route Example (logged fields)

```json
{
  "event": "http_request",
  "request_id": "req_...",
  "method": "POST",
  "path": "/api/admin/staging/docs/doc-001/validate",
  "path_template": "/api/admin/staging/docs/{doc_id}/validate",
  "surface": "admin",
  "route_owner": "content_team",
  "status": 200,
  "latency_ms": 198,
  "upstream_status": 200,
  "upstream_latency_ms": 190,
  "proxy_mode": "shadow",
  "shadow_proxy_enabled": true,
  "error_code": null,
  "auth_required": true,
  "csrf_required": true,
  "audit_required": true,
  "deprecated_route_denied": false,
  "successor_route": null
}
```

---

## PR-5B Status

- [x] `configs/observability_contract.yaml` defines all required fields
- [x] `tools/check_observability_contract.py` validates contract + fixtures
- [x] `tests/fixtures/observability/` has sample request + error logs
- [x] `tests/security/test_observability_contract.py` unit tests pass
- [x] `Makefile` has `check-observability-contract` target
- [x] `docs/runbooks/CUTOVER_OBSERVABILITY.md` runbook
- [ ] Go gateway `Logger.Request()` extended with new fields (runtime)
- [ ] `middleware.go` passes route context to logger

**PR-5B does NOT cut traffic. It only defines the observability contract and validates it against fixtures.**

---

## Next: PR-5C Evidence Bundle

After PR-5B, PR-5C will package shadow/mirror/evidence/readiness artifacts:

```
reports/shadow/bundles/<timestamp>/
  shadow-report.json
  mirror-report.json
  route-inventory.txt
  cutover-readiness.json
  evidence-summary.md
```

PR-5C still does NOT cut traffic. It is the last evidence-packaging step before Phase 6 staging ingress.
