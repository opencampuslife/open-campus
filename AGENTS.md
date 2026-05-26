# Control Plane Migration Rules

These rules apply to the repository while the Go control-plane migration is in progress.

- Treat `contracts/routes.yaml` as the inventory for public and internal gateway entrypoints.
- Do not add a route branch to `services/api-gateway/src/server.py` without first updating its contract and migration owner.
- Do not add new `sys.path.append`, `sys.path.insert`, or `sys.path.extend` calls under `services/*/src`; existing entries are frozen debt until packaging work removes them.
- Keep existing external response bodies compatible during proxy or cutover changes.
- Run `make test-route-contract` before submitting gateway or Python service boundary changes.

---

# PR Status

## Completed

| PR | Description | Status |
|----|-------------|--------|
| PR-1 | Route contract + freeze gates | ✅ |
| PR-2A | Go shadow gateway skeleton | ✅ |
| PR-2B | /api/gaokao/chat transparent proxy | ✅ |
| PR-2C | Parity harness | ✅ |
| PR-2D | Sanitized parity fixtures + privacy gate | ✅ |
| PR-3A | Admin remediation contract | ✅ |
| PR-3B | POST replacements + deprecated GET aliases | ✅ |
| PR-3C | Admin console POST + legacy usage tracking | ✅ |
| PR-3D | POST-only admin shadow proxy allowlist | ✅ |
| PR-3E | Admin POST parity fixtures | ✅ |
| PR-4A | Deployment wiring | ✅ |
| PR-4B | Dry-run tooling + safety defaults | ✅ |
| PR-4C | External mirror driver | ✅ |
| PR-4D | Shadow evidence policy + checker | ✅ |
| PR-5A | Controlled ingress cutover design + readiness gate | ✅ |
| PR-5B | Cutover observability contract | ✅ |
| PR-5C | Shadow evidence bundle | ✅ |
| PR-6A | Staging ingress config disabled by default | ✅ |
| PR-6B | Staging header-based canary config | ✅ |
| PR-6C | Staging header canary evidence path | ✅ |
| PR-6D | Staging percentage canary config, weight=0 | ✅ |
| PR-6E | Staging 1% evidence capability | ✅ ready to merge |

## PR-6E Note

PR-6E introduces the **capability** to run staging 1% percentage canary evidence.
It does **NOT** prove staging 1% has passed.

Real staging evidence must be produced manually with:
```bash
STAGING_ENV_CONFIRMED=true CANARY_PERCENT=1 make run-staging-1pct-canary-evidence
make check-staging-percentage-canary-1pct-evidence
make shadow-evidence-bundle
```

PR-6F (5%) must not start until the 1% report has `status: passed`.

## Next

- **PR-6E-live**: Run real staging 1% evidence and attach bundle
- **PR-6F**: Staging 5% evidence run (requires 1% passed)
- **PR-6G**: Staging 25% evidence run (requires 5% passed)
- **PR-6H**: Staging 50% evidence run (requires 25% passed)
- **PR-6I**: Staging 100% evidence run (requires 50% passed)

## Staging Evidence Gate

Each stage requires previous stage `status: passed`:
- `reports/staging/percentage-canary-1pct-latest.json` → PR-6F
- `reports/staging/percentage-canary-5pct-latest.json` → PR-6G
- `reports/staging/percentage-canary-25pct-latest.json` → PR-6H
- `reports/staging/percentage-canary-50pct-latest.json` → PR-6I

## Hard Boundaries

- Staging only, no production
- No weight>0 config committed to repo
- Temp configs in `reports/staging/tmp/` (gitignored)
- No fake `passed` evidence
- `--allow-weight` and `--allow-percentage-canary` are independent
- Do not skip stages (1% → 5% → 25% → 50% → 100%)
