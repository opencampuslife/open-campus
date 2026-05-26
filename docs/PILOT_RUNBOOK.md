# Controlled Pilot Runbook

## Purpose

This package supports one school's controlled Mealbot trial for ordering, meal cancellation, WeCom image intake, lock/summary and vendor confirmation. AI/OCR and group-message listening are not part of the pilot.

## 1. Initialize A School

Prepare a non-secret YAML file based on `configs/pilot_school.example.yaml`. Keep `WECOM_SECRET`, `WECOM_TOKEN` and `WECOM_ENCODING_AES_KEY` in protected environment configuration only.

```bash
make seed-school-pilot PILOT_CONFIG=configs/pilot_school.example.yaml SCHOOL=demo_school
```

The command prints `school_id`, meal policy, safe vendor summary and callback preflight status.

## 2. Import Pilot Roster

Provide UTF-8 CSV files using the example shapes in `data/pilot/examples/`.

```bash
make import-school-pilot SCHOOL_ID=demo_school \
  CLASSES_CSV=data/pilot/examples/classes.csv \
  STUDENTS_CSV=data/pilot/examples/students.csv \
  TEACHERS_CSV=data/pilot/examples/teachers.csv \
  PARENT_BINDINGS_CSV=data/pilot/examples/parent_bindings.csv
```

The import is idempotent. Invalid rows are written to `data/pilot/reports/import_report.json` and cause a non-zero exit code; they are never silently discarded. Parent mobile numbers are stored as hashes, not raw numbers.

## 3. Configure Enterprise WeChat

Configure the internal application callback:

```text
URL: https://<host>/wecom/callback/message
Token: WECOM_TOKEN
EncodingAESKey: WECOM_ENCODING_AES_KEY
```

Environment:

```text
WECOM_CORP_ID
WECOM_AGENT_ID
WECOM_SECRET
WECOM_TOKEN
WECOM_ENCODING_AES_KEY
WECOM_SCHOOL_ID=<school_id>
APP_BASE_URL=https://<host>
GAOKAO_ENV=production
WECOM_H5_OAUTH_AUTO_REDIRECT=1
```

Verify that the WeCom console accepts the callback URL. A user image message should create an attachment and receive a `/h5/meal/cancel?attachment_id=...` confirmation link.
Production `/readyz` rejects placeholder or localhost `APP_BASE_URL` values so a trial cannot be reported ready before a real HTTPS callback origin is configured.

## 4. H5 Menus And Users

Configure the application menu with the school's authenticated H5 entry pages:

```text
/h5/meal/order
/h5/meal/cancel
```

Families with imported `parent_wecom_userid` bindings can select their student. Teachers and logistics personnel must be imported with their WeCom userid and required role. The H5 and API routes must be served from the HTTPS `APP_BASE_URL`: an unauthenticated H5 request goes through `/api/campus/auth/wecom/start`, then the callback creates an HttpOnly session cookie and returns to the original page.

## 5. Daily Flow

1. Families submit ordering or cancellation before the configured cutoff.
2. Students may send an image to the application and confirm the linked cancellation page.
3. Logistics lock each meal period and review the summary.
4. The vendor uses the signed confirmation link.
5. Operations review reminders, failed media downloads and the audit log.

Status endpoint for operations roles:

```http
GET /api/pilot/status?school_id=<school_id>&date=YYYY-MM-DD
```

Daily checks:

```text
/healthz is ok
/readyz is ok
/api/internal/worker-status contains fresh worker heartbeats
/api/pilot/status has no unexpected pending/failed items
```

## 6. Export Summary

```bash
make export-meal-summary SCHOOL_ID=demo_school DATE=2026-05-25
```

The CSV is written under `data/pilot/exports/` and the export action is audited.

## 7. Pause And Resume

To stop all new H5 submissions and suspend background dispatch without losing queued data:

```bash
make mealbot-pause SCHOOL_ID=demo_school
```

To resume:

```bash
make mealbot-resume SCHOOL_ID=demo_school
```

Paused workers leave pending rows unclaimed. Restarting deployment processes is not required for the database-backed controls to take effect.

## 8. Incident Operations

Invalidate pending vendor links:

```bash
PYTHONPATH=services/mealbot-service/src DATABASE_URL="$DATABASE_URL_ADMIN" \
python3 -m app.scripts.pilot_ops invalidate-vendor-links --school-id demo_school
```

Manually unlock one mistakenly locked meal period:

```bash
PYTHONPATH=services/mealbot-service/src DATABASE_URL="$DATABASE_URL_ADMIN" \
python3 -m app.scripts.pilot_ops unlock-meal --school-id demo_school --lock-id ML-xxx
```

Both actions write `operation_logs`. Use them only with an incident ticket and named operator approval.

## 9. Rollback To Manual Excel

1. Run `make mealbot-pause SCHOOL_ID=<school_id>`.
2. Export the day's summary.
3. Stop callback routing if image intake must also halt.
4. Preserve PostgreSQL records, attachment files and audit logs.
5. Continue meal handling using the exported CSV/manual process.
6. Fix the incident, run `make release-check`, then run `make mealbot-resume`.

## 10. Pilot Acceptance

Before opening the pilot:

```bash
make pilot-smoke
make benchmark-mealbot-gate
make release-check
```

Required results:

```text
mealbot_e2e: PASS, blocking=true, score >= 90
make release-check: exit_code = 0
```
