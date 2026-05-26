# Shadow Evidence Bundle Runbook

## Scope|

PR-5C aggregates scattered evidence outputs into a single archive for review, sign-off, and
future staging ingress cutover.

PR-6C extends this by adding staging header-canary evidence
(`reports/staging/header-canary-latest.json`) into the bundle.

| Evidence | Source | Format |
|----------|--------|--------|
| Shadow dry-run report | `reports/shadow/latest.json` | JSON |
| Mirror report | `reports/shadow/mirror-latest.json` | JSON |
| Staging header-canary | `reports/staging/header-canary-latest.json` | JSON |
| Route inventory | `check_route_contract.py --inventory` | TXT |
| Cutover readiness | `check_cutover_readiness.py` validation | JSON |
| Observability contract | `configs/observability_contract.yaml` | JSON |

**Does NOT change ingress. Does NOT cut traffic. Does NOT require a staging environment.**

---

## Usage|

### Build a bundle|

```bash|
make shadow-evidence-bundle|
```

Writes to `reports/shadow/bundles/<timestamp>/`.

### Include staging evidence (if available)|

```bash|
python3 tools/build_shadow_evidence_bundle.py \
  --shadow-report reports/shadow/latest.json \
  --mirror-report reports/shadow/mirror-latest.json \
  --staging-report reports/staging/header-canary-latest.json \
  --strict|
```

### Run in local mode (default)|

Missing live evidence produces warnings, not failures. `strict_ready` is reported as `null`.

### Run in staging strict mode|

```bash|
python3 tools/build_shadow_evidence_bundle.py \
  --shadow-report reports/shadow/latest.json \
  --mirror-report reports/shadow/mirror-latest.json \
  --staging-report reports/staging/header-canary-latest.json \
  --strict|
```

Missing live evidence is fatal. `strict_ready` requires all conditions.

---

## Bundle Contents|

```
reports/shadow/bundles/<timestamp>/|
├── bundle.json              # Top-level manifest + bundle dir|
├── evidence-summary.md      # Human-readable summary|
├── manifest.json            # Machine-readable manifest|
├── shadow-report.json       # Copy of latest.json|
├── mirror-report.json       # Copy of mirror-latest.json|
├── header-canary-report.json # Copy of header-canary-latest.json (if available)|
├── route-inventory.txt      # Route inventory output|
├── cutover-readiness.json   # Cutover policy validation|
└── observability-contract.json  # Contract YAML (as JSON)|
```

### manifest.json|

| Field | Type | Description |
|-------|------|-------------|
| `generated_at` | string | ISO 8601 timestamp |
| `git_commit` | string | Git SHA at generation time |
| `bundle_version` | int | Always 1 for PR-5C/6C |
| `mode` | string | `local`, `staging_strict`, or `staging_header_canary` |
| `inputs` | object | Map of input source paths |
| `privacy` | object | Privacy attestation flags |
| `summary` | object | Aggregate health/evidence summary |
| `gates` | object | Per-gate pass/fail status |

---

## Gate Checks|

| Gate | When It Passes |
|------|----------------|
| `cutover_readiness_ok` | Policy shape, allowed routes, blocked routes, rollback triggers all valid |
| `observability_contract_ok` | Contract shape valid + all fixtures pass |
| `shadow_evidence_ok` | Shadow dry-run report (`latest.json`) is present and parseable |
| `mirror_evidence_ok` | Mirror report is present and parseable |
| `staging_canary_ok` | Staging header-canary evidence collected and valid |

---

## Conditions for `strict_ready=true`|

- `chat_parity == "passed"`|
- `admin_post_parity == "passed"`|
- Mirror mode is `"live"`|
- `drifted_cases == 0`|
- Staging header-canary evidence `status == "completed"`|

---

## Privacy Attestation|

Every bundle includes a privacy attestation:|

```json|
"privacy": {|
  "raw_payload_included": false,|
  "contains_pii": false,|
  "redacted": true|
}|```

These are hardcoded to `false`/`true` in PR-5C/6C because no raw payload or PII touches the
bundle builder. All evidence reports are redacted at source (via `check_shadow_evidence`|
forbidden-field checks and parity redaction logic).|

---

## PR-5C/6C Status|

- [x] `tools/build_shadow_evidence_bundle.py` builds bundle from inputs|
- [x] `docs/runbooks/SHADOW_EVIDENCE_BUNDLE.md` this runbook|
- [x] `tests/security/test_shadow_evidence_bundle.py` unit tests|
- [x] `Makefile` has `shadow-evidence-bundle` and `test-shadow-evidence-bundle`|
- [x] `.gitignore` excludes bundle content, keeps `.gitkeep`|
- [x] `reports/shadow/bundles/.gitkeep` placeholder|
- [x] `scripts/run_staging_header_canary_evidence.sh` — PR-6C evidence script|
- [x] `tools/collect_staging_canary_result.py` — PR-6C evidence collector|
- [x] `reports/staging/.gitkeep` — staging directory placeholder|

**PR-6C does NOT fake passed evidence. If no staging environment is available,**
**it writes `"status": "skipped"` and exits 0.**

---

## Next: PR-6D Staging Percentage Canary Config (Future)|

After PR-6C, PR-6D will add percentage-based canary config|
(`weight: 1` for initial rollout). This introduces actual traffic percentage|
to the Go gateway for the first time.