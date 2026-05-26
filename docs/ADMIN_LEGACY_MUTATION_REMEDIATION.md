# Admin Legacy Mutation Remediation

This document describes the staged remediation plan for the five legacy admin `GET` mutation gaps recorded in `contracts/routes.yaml`.

## Problem

The legacy Python control plane still exposes five state-changing admin routes via `GET` branches. They are explicitly tracked as contract gaps so the shadow/control-plane migration can keep moving without hiding the risk.

## Current Gaps

- `GET /api/admin/ingestion/runs/{run_id}/cancel`
- `GET /api/admin/staging/docs/{doc_id}/validate`
- `GET /api/admin/staging/docs/{doc_id}/approve`
- `GET /api/admin/staging/docs/{doc_id}/reject`
- `GET /api/admin/staging/docs/{doc_id}/publish`

## PR-3A Contract Rules

- Each gap must carry `legacy_flags` including `state_changing_get`.
- Each gap must include `legacy_exit` with `cutover_blocker=true`.
- Each gap must include a planned `replacement` contract for a `POST` route.
- PR-3A does not change runtime behavior or cut traffic.

## PR-3B Runtime Rules

- Each replacement `POST` route is implemented in the Python gateway.
- Each legacy `GET` route remains available as a deprecated compatibility alias.
- The legacy alias must emit `Deprecation`, `Sunset`, `Link`, and `X-Gaokao-Legacy-Route` headers.
- The replacement `POST` route remains the canonical mutation path and requires CSRF.

## Replacement Contract

The replacement is a `POST` route with the same path, `csrf=required`, `audit=true`, and `status=implemented`.

That keeps the migration path explicit while preserving the current GET alias for compatibility until callers finish moving off it.

## Cutover Policy

- The admin shadow gateway must not cut over while any `state_changing_get` gap remains unresolved.
- PR-3B is the implementation phase for the planned `POST` replacements.
- PR-3C can keep the legacy GET aliases with deprecation headers if the compatibility window needs to stay open.

## Rollback

Rollback is metadata-only for PR-3A:

- remove the remediation metadata from `contracts/routes.yaml`
- keep the existing runtime unchanged
- keep the existing legacy GET behavior intact
