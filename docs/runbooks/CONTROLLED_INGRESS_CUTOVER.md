# Controlled Ingress Cutover

## Overview

PR-5A defines how a future Go gateway ingress cutover can be evaluated. It does not enable ingress routing, production traffic, or automatic mirroring.

The source of truth for this phase is `configs/cutover_policy.yaml`, checked by `tools/check_cutover_readiness.py`.

## Policy Rules

The cutover policy stays in `design_only` mode until staging and production rollout PRs explicitly move beyond design.

Allowed routes must be explicit:

- `POST /api/gaokao/chat`
- `POST /api/admin/ingestion/runs/{run_id}/cancel`
- `POST /api/admin/staging/docs/{doc_id}/validate`
- `POST /api/admin/staging/docs/{doc_id}/approve`
- `POST /api/admin/staging/docs/{doc_id}/reject`
- `POST /api/admin/staging/docs/{doc_id}/publish`

Admin routes must remain canonical POST replacements with `csrf=required`, `audit=true`, and authenticated staff/admin access in `contracts/routes.yaml`.

Blocked routes include:

- `GET /api/admin/**`
- wildcard admin cutover unless a route is explicitly listed
- deprecated compatibility aliases
- state-changing GET aliases

## Evidence Gates

Before cutover design can proceed to staging ingress work, evidence should show:

- 3 consecutive staging shadow dry-run rounds
- strict shadow evidence passed
- `unexpected_diffs == 0`
- `latency_fail_count == 0`
- `legacy_gaps == 0`
- `state_changing_get_gaps == 0`
- `deprecated_aliases == 5`
- `legacy_get_usage_events == 0`, unless an explicit waiver exists

## Commands

Default design check:

```bash
make check-cutover-readiness
```

Strict staging evidence check:

```bash
make check-cutover-readiness-strict
```

Strict mode requires:

- `reports/shadow/latest.json`
- `reports/shadow/mirror-latest.json`
- passed chat and admin parity
- live mirror evidence with no skipped cases and no drift

## Rollback Triggers

Future staging or production canary rollout must roll back when any trigger is hit:

- unexpected diff count greater than 0
- latency fail count greater than 0
- upstream 5xx increase above policy threshold
- auth or CSRF mismatch
- missing admin audit event
- deprecated GET routed to Go

## Non-Goals

- No ingress changes
- No production compose changes
- No Go proxy runtime changes
- No Python gateway changes
- No admin console changes
- No deprecated GET alias removal
- No strict readiness check in the default `release-check`
