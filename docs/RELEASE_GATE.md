# Release Gate

`make release-check` is the release gate for the current admissions and campus-operations baseline.
It turns the safety and mealbot pilot chains into repeatable validation steps with explicit outcomes.

## What It Runs

```bash
make test-frontend-gaokao
make test-db-policy-live
make test
make benchmark-admissions-gate
make benchmark-mealbot-gate
python3 -m unittest discover -s services/api-gateway/tests -p '*_test.py'
GAOKAO_ENV=production RAG_SOURCE=postgres python3 tools/ci_policy_check.py --root .
GAOKAO_ENV=production RAG_SOURCE=json python3 tools/ci_policy_check.py --root . # expected to fail
```

## Blocking Assertions

- The OpenHuman frontend does not send `role`, `evidence`, `model`, or `system_prompt`.
- The BFF rejects browser-forged fields such as `role`, `evidence`, `model`, `system_prompt`, `tools`, `entrypoint`, and `identity`.
- Chat payloads are limited to `session_id` and `message`.
- Handoff payloads are limited to `session_id` and `reason`.
- Citations returned to the browser do not expose `doc_id`, `chunk_id`, `source_uri`, or internal paths.
- Parent, student, and visitor entrypoints cannot retrieve internal/L3 evidence.
- Sales entrypoints can retrieve internal/L3 evidence but cannot retrieve admin/L5 evidence.
- Production retrieval resolves to PostgreSQL.
- Production JSON fallback fails closed.
- Public and staff database URLs must not use admin database users.
- Live PostgreSQL RLS tests verify unset `app.role` fails closed.
- Live PostgreSQL RLS tests verify connection reuse does not leak a previous role.
- Chat and handoff both write audit events.
- WeCom callback images remain asynchronous, bind only to the owning H5 user, and write audit events on rejection.
- `mealbot_e2e` executes submit, lock, vendor confirmation, reminders, image callback, attachment binding, and summary export.

## Benchmark Outcomes

Every gate check emits one of:

```text
PASS
FAIL
WARN_NON_BLOCKING
```

The existing admissions-quality suite currently scores below the target threshold and is explicit rather than silent:

```text
Benchmark: admissions_quality
Threshold: 85
Mode: non-blocking
Result: WARN_NON_BLOCKING
```

Set `BENCHMARK_ADMISSIONS_BLOCKING=true` only after improving that suite to the threshold.

The campus pilot flow is blocking by default:

```text
Benchmark: mealbot_e2e
Threshold: 90
Mode: blocking
Result: PASS
```

## Required Environment

PostgreSQL with pgvector must be running before the release gate:

```bash
make db-up
make migrate-db-policy
make release-check
```

The frontend test runner uses the bundled Node path in `NODE_BIN` by default.
Override it only if the local shell has a compatible Node/Vitest setup:

```bash
make release-check NODE_BIN=/path/to/node/bin
```

## Failure Policy

A failed release gate means the build is not releasable. Do not bypass failures by:

- Falling back to JSON retrieval in production.
- Removing live DB/RLS tests.
- Relaxing BFF payload validation.
- Returning raw retrieval evidence to the browser.
- Disabling audit writes.
- Disabling the blocking mealbot E2E gate during a pilot release.

Fix the failing assertion and run `make release-check` again.
