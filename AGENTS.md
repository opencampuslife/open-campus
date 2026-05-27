# Control Plane Migration Rules

These rules apply to the repository while the Go control-plane migration is in progress.

- Treat `contracts/routes.yaml` as the inventory for public and internal gateway entrypoints.
- Do not add a route branch to `services/api-gateway/src/server.py` without first updating its contract and migration owner.
- Do not add new `sys.path.append`, `sys.path.insert`, or `sys.path.extend` calls under `services/*/src`; existing entries are frozen debt until packaging work removes them.
- Keep existing external response bodies compatible during proxy or cutover changes.
- Run `make test-route-contract` before submitting gateway or Python service boundary changes.

## Health Hardening Checks

Use these checks when changing service boundaries, gateway code, CI policy, or codegraph behavior:

```bash
python tools/check_package_boundary.py --root .
python tools/check_gateway_freeze.py --root . --allow-existing
python tools/check_ci_policy.py --root .
```

Reference docs:

- `docs/architecture/code-health-review-2026-05-27.md`
- `docs/testing/service-test-matrix.md`

Additional hard rules:

- Do not add production `sys.path.append`, `sys.path.insert`, or `sys.path.extend` under `services/*/src`.
- Do not add new Python gateway route branches; route inventory and control-plane migration must start from `contracts/routes.yaml`.
- Treat protocol labels in `docs/codegraph.html` as audit signals only when evidence is `confirmed`; review `weak` evidence manually.


# Check Rules

Use `make health` before committing (`make release-gate` for CI-wide check).

----

## Gateway Freeze

- Do NOT add new route branches (`elif path.startswith(...)`) to `services/api-gateway/src/server.py` — route must go through `contracts/routes.yaml` instead.
- Do NOT add new HTTP handler classes to `server.py`.
- Do NOT add cross-service Python imports in `bff_gateway.py` — BFF must call services via API, not direct import.
- Run `make test-gateway-freeze` before modifying any gateway file.

## Package Boundary

- Production code (`services/*/src`) must NOT use `sys.path.insert`, `sys.path.append`, or `sys.path.extend`.
- Each Python service must eventually have a `pyproject.toml` and be installable via `pip install -e`.
- `make test-python-control-plane-freeze` validates the allowlist in `contracts/python_control_plane_allowlist.json`.

## Service Ownership

Every `services/*` directory must have an entry in `contracts/service_ownership.json`.

| Field | Required for | Rule |
|-------|-------------|------|
| `code_owner` | all services | must not be `TBD` |
| `runtime_owner` | all services | must not be `TBD` |
| `security_reviewer` | high-sensitivity services | required if `data_reviewer` is null |
| `data_reviewer` | high-sensitivity services | required if `security_reviewer` is null |

High-sensitivity services (must have at least one reviewer): `auth-service`, `crm-service`, `db-policy-service`, `knowledge-service`, `knowledge-graph-service`, `llm-gateway`, `permission-service`, `source-ingestion-service`, `wecom-adapter`, `wecom-aibot-bridge`.

Check locally:
```bash
python tools/check_service_ownership.py --root .
python tools/check_service_ownership.py --root . --allow-tbd  # transitional mode
```

CI currently runs with `--allow-tbd` (transitional). Remove this flag once all owners are assigned.
When adding a new service, update both `contracts/service_ownership.json` and `docs/architecture/service-ownership-matrix.md`.

## Lint Baseline

ruff and mypy use a baseline-gated approach: existing issues are grandfathered; only NEW issues block CI.

```bash
python tools/check_lint_baseline.py              # check against baseline (CI mode)
python tools/check_lint_baseline.py --mode check  # explicit check mode
python tools/check_lint_baseline.py --tool ruff   # ruff only
python tools/check_lint_baseline.py --tool mypy   # mypy only
python tools/check_lint_baseline.py --mode update # regenerate baselines after fixing issues
```

### Baseline Integrity Gate

The `tools/check_baseline_integrity.py` checker runs in CI and enforces:

| Rule | Enforcement |
|------|-------------|
| Baseline `issue_count` must not increase | BLOCKED |
| No new issue `key` entries beyond baseline | BLOCKED |
| `schema_version` must not change | BLOCKED |
| `tool` name must not change | BLOCKED |
| Baseline file must exist | BLOCKED |
| Issues resolved (baseline shrinks) | ALLOWED |
| `generated_at` timestamp change | ALLOWED |

**Hard rule**: Never expand baseline files in a PR to bypass lint/typecheck failures.
Fix the code instead. Only `--mode update` to shrink baseline after resolving issues.

If you fix a lint/type issue and need to update the baseline:
```bash
python tools/check_lint_baseline.py --mode update --tool ruff
python tools/check_lint_baseline.py --mode update --tool mypy
```
Then commit the shrunk baseline with a clear message like "fix: resolve 3 ruff F401 issues".

Baselines are stored in `contracts/ruff_baseline.json` and `contracts/mypy_baseline.json` (schema v1).

## CI Policy

- `make ci-policy-check` runs production JSON checks, database URL safety, provider isolation, and SQL policy.
- All SQL must be parameterized; policy filters must not be string-concatenated.

## Codegraph Protocol

| Level | Definition |
|-------|------------|
| confirmed | AST import / API-level evidence (e.g., `import psycopg`, `requests.get(...)`) |
| weak | Keyword/regex hit (e.g., `postgres`, `DATABASE_URL`) |
| false_positive_suspect | HTML `<select>`, Python `.update()`, HTTP `DELETE`, `sys.path.insert` |

Do not treat `weak` or `false_positive_suspect` as real protocol evidence.

## Test Matrix

Each service must pass the test requirements defined in `docs/testing/service-test-matrix.md`.
New services added without meeting the minimum test matrix → CI fail.

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

---

# MetaCampus 2D Game 项目约定

## Agent 命名限制
- Mavis agent 名称最大 20 字符，超长会报错（40002）
- agent 名必须使用 daemon 已注册名称，不能随意创造
- 如遇未注册名称，使用现有通用 agent 替代
- 已验证可用名称：godot-developer、narrative-designer、qa-demo-lead、pixel-artist、api-bridge-developer、general、coder、verifier
- 避免使用未注册短名：dq-eng、mt-eng（均已失败）

## 指标命名约定（4个核心指标）
| 指标 ID | 说明 | 初始值 |
|---------|------|--------|
| school_efficiency | 学校效率 | 40 |
| parent_trust | 家长信任 | 50 |
| compliance_safety | 合规安全 | 70 |
| system_stability | 系统稳定性 | 60 |

## T2 高风险分支数据（game/metacampus-godot/data/dialogues.json）
- 错误分支：action=promise_admission, compliance_safety=-20, parent_trust=+2
- 正确分支：compliance_safety=+10, parent_trust=+6

## Phase G2 smoke flow（必须跑通才能验收）
1. 玩家靠近家长 NPC → E 对话 → 选择知识库回答 → 指标增加 → quest 完成 toast
2. 家长问"保证录取" → 选错误分支 → compliance_safety -20
