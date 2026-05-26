# Staging Ingress Canary Runbook

## Scope

PR-6B adds **header-based canary** support to the staging ingress config.
**Config is disabled by default.** Only requests carrying the explicit header
`X-Gaokao-Gateway-Canary: go` are routed to the Go shadow gateway.
No production traffic is affected. No percentage-based traffic is enabled.

| PR | Phase | Traffic |
|----|-------|---------|
| PR-6A | Prepare config + validator | 0% |
| PR-6B | Header-based canary | Header-only staging |

## Config Files

| File | Purpose |
|------|---------|
| `go-gateway-shadow.example.yaml` | Default (disabled) config; also documents canary fields |
| `go-gateway-shadow.header-canary.example.yaml` | Header-canary-enabled example; requires `--allow-header-canary` |

### Default Config

```yaml
mode: staging_only
enabled: false
default_weight: 0

canary:
  type: header
  enabled: false
  header: X-Gaokao-Gateway-Canary
  value: go
```

### Header-Canary-Enabled Config

```yaml
mode: staging_only
enabled: true
default_weight: 0

canary:
  type: header
  enabled: true
  header: X-Gaokao-Gateway-Canary
  value: go
```

### Requirements

| Field | Default | Header-Canary Enabled |
|-------|---------|----------------------|
| `mode` | `staging_only` | `staging_only` |
| `enabled` | `false` | `true` (with `--allow-header-canary`) |
| `canary.enabled` | `false` | `true` (with `--allow-header-canary`) |
| `default_weight` | `0` | `0` (must still be 0) |
| `canary.header` | `X-Gaokao-Gateway-Canary` | `X-Gaokao-Gateway-Canary` |
| `canary.value` | `go` | `go` |
| Route weights | `0` | `0` (must still be 0) |

---

## Checker Behavior

```bash
# Default check (both configs)
make check-staging-ingress-config

# Header canary check (requires --allow-header-canary)
make check-staging-header-canary-config
```

### Default Mode (no flags)

| Scenario | Result |
|----------|--------|
| `enabled=true` | FAIL |
| `canary.enabled=true` | FAIL |
| `weight>0` | FAIL |
| Wildcard route | FAIL |
| GET admin route | FAIL |
| Production host | FAIL |

### Header Canary Mode (`--allow-header-canary`)

| Scenario | Result |
|----------|--------|
| `enabled=true` | PASS (with canary enabled) |
| `canary.enabled=true` | PASS |
| `default_weight>0` | FAIL (use `--allow-weight`) |
| Route `weight>0` | FAIL (use `--allow-weight`) |
| Wrong canary header name | FAIL |
| Wrong canary value | FAIL |
| Wildcard route | FAIL |
| GET admin route | FAIL |
| Production host | FAIL |

---

## Validation

```bash
make check-staging-ingress-config
make check-staging-header-canary-config
```

## Staging Smoke Commands

### Public Chat (no header → Python legacy)

```bash
curl -X POST https://staging.example.com/api/gaokao/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"hello"}'
```

### Public Chat (with header → Go gateway)

```bash
curl -X POST https://staging.example.com/api/gaokao/chat \
  -H "Content-Type: application/json" \
  -H "X-Gaokao-Gateway-Canary: go" \
  -d '{"message":"hello"}'
```

### Admin POST Replacement (with header → Go gateway)

```bash
curl -X POST https://staging.example.com/api/admin/staging/docs/doc-parity-001/validate \
  -H "X-Gaokao-Gateway-Canary: go" \
  -H "X-CSRF-Token: ..." \
  -H "Content-Type: application/json" \
  -d '{}'
```

### Deprecated GET Alias (should return 405)

```bash
curl -X GET "https://staging.example.com/api/admin/staging/docs/doc-parity-001/validate" \
  -H "X-Gaokao-Gateway-Canary: go"
```

Expected: `405 DEPRECATED_ROUTE_NOT_PROXIED` if routed to Go gateway.

---

## Rollback Conditions

If any of these fire, set `enabled: false` and `canary.enabled: false` immediately:

- `unexpected_diffs > 0`
- `upstream_5xx > 1%`
- `auth_csrf_mismatch`
- `deprecated_get_routed_to_go`

---

## PR-6B Acceptance

```bash
make check-staging-ingress-config
make check-staging-header-canary-config
python3 -m unittest tests/security/test_staging_ingress_config.py -v
make check-cutover-readiness
make check-observability-contract
make check-shadow-evidence
make test-route-contract route-inventory
make check-admin-proxy-guard
make test-admin-console-no-legacy-get
make test-python-control-plane-freeze
make test-parity-fixtures
PATH=/usr/local/go/bin:$PATH make test-go-gateway test-go-admin-shadow-proxy test-go-admin-parity-unit
```

## PR-6B Status

- [x] `deploy/staging/ingress/go-gateway-shadow.example.yaml` — updated with canary block
- [x] `deploy/staging/ingress/go-gateway-shadow.header-canary.example.yaml` — header-canary example
- [x] `tools/check_staging_ingress_config.py` — `--allow-header-canary` + canary validation
- [x] `tests/security/test_staging_ingress_config.py` — 20 unit tests (10 original + 10 header-canary)
- [x] `docs/runbooks/STAGING_INGRESS_CANARY.md` — this runbook
- [x] `Makefile` — `check-staging-header-canary-config` target

**PR-6B does NOT enable percentage traffic. Does NOT change production ingress. Does not delete Python fallback.**

---

## Next: PR-6C Staging Header Canary Evidence Run

PR-6C collects evidence from the header-canary config and produces a staging evidence report.
No new ingress capability is added. No percentage traffic is enabled.

### Evidence Report

```json
{
  "mode": "staging_header_canary",
  "generated_at": "...",
  "summary": {
    "header_canary_enabled": true,
    "fallback_without_header_ok": true,
    "go_header_canary_ok": true,
    "admin_post_canary_ok": true,
    "deprecated_get_blocked": true,
    "rollback_verified": true,
    "unexpected_diffs": 0,
    "latency_fail_count": 0
  },
  "routes": [
    {
      "method": "POST",
      "path": "/api/gaokao/chat",
      "without_header": "python",
      "with_header": "go",
      "status": "passed"
    }
  ],
  "privacy": {
    "raw_payload_included": false,
    "contains_pii": false
  }
}
```

### Scripts

| File | Purpose |
|------|---------|
| `scripts/run_staging_header_canary_evidence.sh` | Run smoke tests, capture results |
| `tools/collect_staging_canary_result.py` | Validate and collect evidence JSON |

### Make Targets

```make
staging-header-canary-evidence:
	bash scripts/run_staging_header_canary_evidence.sh

check-staging-header-canary-evidence:
	python3 tools/collect_staging_canary_result.py \
	  --report reports/staging/header-canary-latest.json
```

### If No Staging Environment

- Script writes `"status": "skipped"` and exits 0
- `strict` checks continue to fail
- No fake passed evidence is generated

### If Staging Environment Available

```bash
make staging-header-canary-evidence
make check-staging-header-canary-evidence
make shadow-evidence-bundle
make check-cutover-readiness-strict
```

---

## PR-6C Status

- [x] `scripts/run_staging_header_canary_evidence.sh` — evidence collection script
- [x] `tools/collect_staging_canary_result.py` — evidence collector/validator
- [x] `reports/staging/.gitkeep` — directory placeholder
- [x] `docs/runbooks/STAGING_INGRESS_CANARY.md` — updated with PR-6C docs
- [x] `Makefile` — `staging-header-canary-evidence`, `check-staging-header-canary-evidence`

**PR-6C does NOT add new ingress capability. Does NOT enable percentage traffic. Does NOT fake passed evidence.**

---

## Next: PR-6D Staging Percentage Canary Config

PR-6D prepares percentage-canary config and static checks.
It does NOT enable staging percentage traffic (weight remains 0).

### Percentage Canary Config

```yaml
mode: staging_only
enabled: true
default_weight: 0

canary:
  type: percentage
  enabled: true
  header: X-Gaokao-Gateway-Canary
  value: go
  current_weight: 0
  stages: [1, 5, 25, 50, 100]
```

### Checker

| Scenario | Normal Check | With `--allow-percentage-canary` |
|----------|---------------|-------------------------------|
| `enabled=true` | FAIL | PASS (with canary enabled) |
| `canary.enabled=true` | FAIL | PASS |
| `canary.type=percentage` | FAIL | PASS |
| `current_weight>0` | FAIL | FAIL (use `--allow-weight`) |
| Per-route `weight>0` | FAIL | FAIL (use `--allow-weight`) |
| Invalid `stages` | FAIL | FAIL |
| Non-increasing `stages` | FAIL | FAIL |

### Make Target

```make
check-staging-percentage-canary-config:
	$(PY) tools/check_staging_ingress_config.py \
	  --config deploy/staging/ingress/go-gateway-shadow.percentage-canary.example.yaml \
	  --policy configs/cutover_policy.yaml \
	  --allow-percentage-canary
```

### PR-6D Status

- [x] `deploy/staging/ingress/go-gateway-shadow.percentage-canary.example.yaml` — percentage-canary example
- [x] `tools/check_staging_ingress_config.py` — `--allow-percentage-canary` + `validate_percentage_canary_config`
- [x] `tests/security/test_staging_ingress_config.py` — +6 percentage-canary tests
- [x] `docs/runbooks/STAGING_INGRESS_CANARY.md` — updated with PR-6D docs
- [x] `Makefile` — `check-staging-percentage-canary-config` target

**PR-6D does NOT enable percentage traffic. `current_weight=0` and all route weights=0.**
**Actual 1% traffic starts in PR-6E after header-canary evidence passes.**

---

## PR-6E Staging Percentage Canary Evidence Run

PR-6E runs **only 1%** staging percentage-canary evidence collection.
Does NOT submit weight=1 config to repo. Does NOT run 5% → 25% → 50% → 100%.

### Hard Boundaries

| Boundary | Enforcement |
|----------|-------------|
| Staging only | Script rejects production |
| Max 1% | `CANARY_PERCENT` must be 1 for PR-6E |
| No config commit | Renders to `/tmp` or `reports/staging/tmp`, cleans up after |
| No fake passed | `STAGING_ENV_CONFIRMED!=true` → `status: skipped` |
| Rollback verified | Script verifies weight returns to 0% |
| No runtime change | Does not modify Go/Python code |
| No production | Does not touch production ingress |

### Evidence Report (1%)

```json
{
  "mode": "staging_percentage_canary",
  "percent": 1,
  "status": "passed|failed|skipped",
  "generated_at": "2026-05-27T00:00:00Z",
  "summary": {
    "staging_env_confirmed": true,
    "config_rendered": true,
    "current_weight": 1,
    "routes_checked": 6,
    "health_ok": true,
    "chat_parity": "passed",
    "admin_post_parity": "passed",
    "mirror_result": "passed",
    "legacy_get_usage_events": 0,
    "deprecated_get_blocked": true,
    "unexpected_diffs": 0,
    "latency_fail_count": 0,
    "rollback_verified": true
  },
  "privacy": {
    "raw_payload_included": false,
    "contains_pii": false
  }
}
```

### Scripts

| File | Purpose |
|------|---------|
| `scripts/run_staging_percentage_canary_evidence.sh` | Main driver: render → collect → rollback → cleanup |
| `tools/render_staging_percentage_canary_config.py` | Render temp 1% config from PR-6D example |
| `tools/collect_staging_percentage_canary_result.py` | Validate and collect evidence JSON |

### Make Targets

```make
run-staging-1pct-canary-evidence:
	bash scripts/run_staging_percentage_canary_evidence.sh

check-staging-1pct-canary-evidence:
	python3 tools/collect_staging_percentage_canary_result.py \
	  --config /tmp/staging-1pct-canary.yaml \
	  --policy configs/cutover_policy.yaml \
	  --percent 1 \
	  --report reports/staging/percentage-canary-1pct-latest.json
```

### Usage

```bash
# Without staging environment (writes skipped)
bash scripts/run_staging_percentage_canary_evidence.sh

# With staging environment
STAGING_ENV_CONFIRMED=true \
CANARY_PERCENT=1 \
bash scripts/run_staging_percentage_canary_evidence.sh

# Check evidence
cat reports/staging/percentage-canary-1pct-latest.json
```

### If No Staging Environment

- Script writes `"status": "skipped"` and exits 0
- `strict` readiness checks continue to fail
- No fake passed evidence is generated

### PR-6E Status

- [x] `tools/render_staging_percentage_canary_config.py` — render temp 1% config
- [x] `tools/collect_staging_percentage_canary_result.py` — evidence collector/validator
- [x] `scripts/run_staging_percentage_canary_evidence.sh` — evidence collection script
- [x] `tests/security/test_staging_percentage_canary_evidence.py` — 8 unit tests
- [x] `docs/runbooks/STAGING_INGRESS_CANARY.md` — updated with PR-6E docs
- [x] `Makefile` — `run-staging-1pct-canary-evidence` target
- [x] `reports/staging/.gitkeep` — directory placeholder

**PR-6E does NOT submit weight=1 config. Does NOT fake passed evidence. Does NOT run >1%.**

---

## Next: PR-6F Staging 5% Evidence Run

After PR-6E 1% evidence passes with `status: passed`, PR-6F will run 5% evidence.
PR-6E and PR-6F are separate PRs to enforce gradual rollout.
