# Campus New Modules Implementation

## Scope

This delivery extends the existing single-school campus transaction platform with:

- Material collection and missing-submission reminders.
- Leave return confirmation and overdue return escalation.
- Attendance sessions with approved-leave matching and anomaly reminders.
- Score batch extraction review, anomaly checks, confirmation, and RPA dry-run preparation.
- Payment proof review, amount anomaly checks, confirmation, and missing-payment reminders.

The implementation deliberately keeps OCR and RPA out of final decision writes. OCR jobs can produce a review payload; a staff confirmation endpoint is still required before scores or payments become confirmed. RPA delivery is represented as a `draft` dry-run job that requires approval before any external execution can be added.

## Architecture

```text
H5 / Admin Console / WeCom authenticated request
  -> WeCom OAuth session cookie or trusted staff proxy identity
  -> API Gateway role and object-scope checks
  -> mealbot-service campus module service
  -> PostgreSQL repositories
  -> operation_logs + reminder_tasks + ocr_jobs / rpa_jobs
  -> worker heartbeat and release gate
```

Database migration: `services/db-policy-service/migrations/015_campus_new_modules.sql`

Service modules:

- `app/modules/campus/materials.py`
- `app/modules/campus/leaves.py`
- `app/modules/campus/attendance.py`
- `app/modules/campus/scores.py`
- `app/modules/campus/payments.py`
- `app/modules/campus/automation.py`
- `app/modules/campus/reports.py`

## API Contract

| Endpoint | Method | Role | Purpose |
| --- | --- | --- | --- |
| `/api/campus/auth/wecom/start?redirect_path=/h5/...` | GET | public | Start WeCom OAuth for an H5 route |
| `/api/campus/auth/wecom/callback` | GET | WeCom callback | Establish HttpOnly scoped session and return to H5 |
| `/api/campus/materials/tasks` | POST | head teacher / academic staff / admin | Create material collection task |
| `/api/campus/materials/submissions` | POST | parent/student H5 or staff | Submit material attachment |
| `/api/campus/materials/tasks/:id/missing/remind` | POST | teacher / academic staff | Generate missing list and reminders |
| `/api/campus/modules/leaves` | POST | parent/student H5 or staff | Submit DB-backed leave request |
| `/api/campus/modules/leaves/:id/approve` | POST | teacher / academic staff | Approve leave and schedule return reminder |
| `/api/campus/modules/leaves/:id/reject` | POST | teacher / academic staff | Reject leave |
| `/api/campus/modules/leaves/:id/return` | POST | owner or responsible staff | Confirm return |
| `/api/campus/modules/leaves/process-overdue` | POST | academic staff / admin | Escalate overdue returns |
| `/api/campus/attendance/sessions` | POST | teacher / academic staff | Start roll-call session |
| `/api/campus/attendance/sessions/:id/records` | POST | teacher / academic staff | Submit attendance and create anomalies |
| `/api/campus/scores/batches` | POST | teacher / academic staff | Upload score batch and queue extraction |
| `/api/campus/scores/batches/:id/confirm` | POST | academic staff / admin | Confirm reviewed scores |
| `/api/campus/scores/batches/:id/rpa-dry-run` | POST | academic staff / admin | Prepare non-executing RPA payload |
| `/api/campus/payments/tasks` | POST | finance / admin | Create payment task |
| `/api/campus/payments/records` | POST | parent/student H5 or finance | Upload payment proof |
| `/api/campus/payments/records/:id/confirm` | POST | finance / admin | Confirm reviewed payment |
| `/api/campus/payments/tasks/:id/missing/remind` | POST | finance / head teacher | Remind missing payments |
| `/api/campus/jobs/ocr/process` | POST | authorized staff | Test/manual worker trigger |
| `/api/campus/modules/exports` | POST | academic staff / finance / admin | Export reviewed CSV ledgers |
| `/api/campus/modules/dashboard` | GET | staff / admin | Module pending-count dashboard |

## Security Decisions

- `school_id` is present on all business tables; live RLS policies restrict staff reads by school and class where applicable.
- Parent requests are constrained to the bound `student_id`; attachment ownership and single-use linkage are checked before submission.
- WeCom OAuth resolves `campus_users.wecom_userid` or a student's imported `parent_userid` binding and creates an eight-hour, server-side session. Browser requests carry only the HttpOnly session cookie, not a caller-supplied role.
- In production, an unauthenticated `/h5/*` visit redirects through WeCom OAuth when `WECOM_H5_OAUTH_AUTO_REDIRECT` is not disabled. `APP_BASE_URL` should be the same HTTPS origin that serves H5 and the API so the session cookie remains first-party.
- Image, PDF, XLS and XLSX uploads are size/type checked and SHA-256 hashed.
- OCR input supplied by parent-facing requests is discarded. Worker output always lands in `review_required`.
- Payment transaction references are stored only as SHA-256 hashes.
- Key status changes and exports write `operation_logs`; reminders use existing `reminder_tasks`.

## UI Delivery

- Admin console route: `/admin/campus/modules`
- H5 hub: `/h5/campus/index`
- H5 forms: `/h5/campus/material`, `/h5/campus/payment`, `/h5/campus/leave-return`, `/h5/campus/attendance`

For deployment, set `GAOKAO_ENV=production`, `APP_BASE_URL=https://<same-origin-host>`, `WECOM_CORP_ID`, `WECOM_SCHOOL_ID`, and the protected WeCom application secret values. Leave `H5_API_BASE_URL` empty for the recommended same-origin session flow. Import parent bindings before issuing H5 menus; otherwise OAuth succeeds but correctly rejects the unbound user.
Production readiness fails closed when `APP_BASE_URL` is a placeholder or localhost origin because WeCom cannot return real users to such a callback.

## Release Gate

```bash
make migrate-db-policy
make test-campus-new-modules
make test-campus-modules-rls-live
make benchmark-campus-agent
make release-check
```

`benchmark-campus-agent` is a blocking functional/security benchmark. It does not claim production OCR recognition accuracy or external RPA accuracy until real labeled fixtures and an approved adapter are configured.
