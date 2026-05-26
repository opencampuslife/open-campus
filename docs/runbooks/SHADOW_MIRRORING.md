# Shadow Mirroring Runbook

## Overview

The shadow mirror driver is an external evidence tool. It replays sanitized cases against the legacy Python gateway and the Go shadow gateway, then writes redacted JSON and Markdown reports.

It does not change Python or Go runtime behavior. It does not hook into ingress, production mirroring, or the live request path.

## Inputs

Supported input formats:

- JSONL replay files under `tests/replay/`
- Existing JSON-compatible parity fixtures under `tests/parity/`

Every case must stay sanitized:

- `privacy.sanitized=true`
- `privacy.contains_pii=false`
- synthetic identifiers only
- no `Authorization`, `Cookie`, or `Set-Cookie`
- no raw request or response bodies in the generated reports

## Commands

Dry-run with the checked-in sanitized sample:

```bash
make shadow-mirror-dry-run
```

Chat mirror against local services:

```bash
make shadow-mirror-chat \
  GO_SHADOW_BASE_URL=http://127.0.0.1:8788 \
  PYTHON_LEGACY_BASE_URL=http://127.0.0.1:8787
```

Admin POST mirror against local services:

```bash
make shadow-mirror-admin \
  GO_SHADOW_BASE_URL=http://127.0.0.1:8788 \
  PYTHON_LEGACY_BASE_URL=http://127.0.0.1:8787
```

## Outputs

The driver writes:

- `reports/shadow/mirror-latest.json`
- `reports/shadow/mirror-latest.md`

Allowed report fields:

- case name
- method and path
- legacy status
- shadow status
- legacy/shadow latency
- latency ratio
- diff category
- redacted body summary with length and short hash

Forbidden report fields:

- raw request body
- raw response body
- `Authorization`
- `Cookie`
- `Set-Cookie`
- raw IPs
- real user, school, student, run, or document identifiers

## Diff Categories

- `none`: status, content type, and body hash matched
- `status`: HTTP status drifted
- `headers`: content type drifted
- `body_hash`: response body changed after redaction
- `unavailable`: one side could not be reached
- `skipped`: dry-run or missing base URLs

## Notes

- `make shadow-mirror-dry-run` is safe to run without live services.
- Live mirror remains optional and is not part of the default `release-check`.
- The report artifacts are ignored by git; only `reports/shadow/.gitkeep` stays tracked.
