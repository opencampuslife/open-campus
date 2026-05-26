# Shadow Evidence Policy

## Overview

This policy defines the minimum staging evidence required before the control-plane migration can move from shadow validation into cutover design work.

It does not enable traffic cutover, ingress ownership, or production mirroring. It only defines what evidence counts as sufficient.

## Evidence Sources

The current policy relies on two redacted reports:

- `reports/shadow/latest.json`
- `reports/shadow/mirror-latest.json`

These reports must be generated from sanitized fixtures or sanitized replay input only. Raw production logs are not accepted as direct input to this repo workflow.

## Baseline Requirements

Before `PR-5A` cutover design begins, the staging evidence set should show:

- `health_ok == true`
- `route_count == 115`
- `legacy_gaps == 0`
- `state-changing GET gaps == 0`
- `deprecated_aliases == 5`
- `legacy_get_usage_events == 0`, or an explicit external waiver
- `chat_parity == passed`
- `admin_post_parity == passed`
- `mirror drifted_cases == 0`
- `latency fail count == 0`
- latency warnings documented when they exist

## Multi-Round Requirement

The operational requirement is:

- three consecutive staging dry-run rounds pass
- the matching mirror evidence stays stable across the same window

This repo does not yet archive rounds automatically. Until that exists, the three-round requirement is tracked operationally outside the default repo checker.

## Checker Modes

Default checker:

- validates report structure
- validates redaction and absence of forbidden raw payload fields
- allows `skipped` parity and `dry_run` mirror mode for local workflows

Strict checker:

- requires `chat_parity == passed`
- requires `admin_post_parity == passed`
- requires `mirror mode == live`
- requires `executed_cases > 0`
- requires `drifted_cases == 0`
- requires `skipped_cases == 0`
- requires `legacy_get_usage_events == 0` unless there is an explicit waiver

## Commands

Validate available evidence without forcing staging requirements:

```bash
make check-shadow-evidence
```

Apply staging-level requirements:

```bash
make check-shadow-evidence-strict
```

If a formal waiver exists for legacy GET usage, pass it explicitly:

```bash
python3 tools/check_shadow_evidence.py \
  --root . \
  --strict \
  --allow-legacy-usage-waiver
```

## Non-Goals

- No production traffic cutover
- No ingress integration
- No runtime changes to Python gateway or Go shadow proxy
- No requirement that every local developer has access to staging
- No inclusion in the default `make release-check`
