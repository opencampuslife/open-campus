# Mealbot Pilot Runbook

## Deployment Shape

The controlled single-school pilot runs these components:

```text
Reverse proxy / TLS
  -> api-gateway
       -> PostgreSQL + pgvector
       -> local/managed attachment storage
  -> reminder_worker
  -> wecom_media_worker
```

Enterprise WeChat callback traffic enters only through:

```text
GET/POST /wecom/callback/message
```

The browser and WeCom clients do not connect directly to PostgreSQL or workers.

## Required Configuration

Production requires:

```text
ENVIRONMENT=prod
DATABASE_URL
APP_BASE_URL
UPLOAD_DIR
WECOM_CORP_ID
WECOM_AGENT_ID
WECOM_SECRET
WECOM_TOKEN
WECOM_ENCODING_AES_KEY
REMINDER_WORKER_INTERVAL_SECONDS
MEDIA_WORKER_INTERVAL_SECONDS
BENCHMARK_ADMISSIONS_BLOCKING=false
BENCHMARK_MEALBOT_BLOCKING=true
```

Store secrets in the deployment secret store or protected environment file. Do not log callback keys, provider tokens, access tokens, or vendor confirmation tokens.

## Preflight

```bash
make db-up
make migrate-db-policy
make benchmark-mealbot-gate
make release-check
```

Probe runtime readiness:

```text
GET /healthz
GET /readyz
GET /api/internal/worker-status
```

`/api/internal/worker-status` requires an authenticated operations role.

## Pilot Proof

`make run-mealbot-e2e` executes the deterministic transaction path and writes:

```text
data/reports/mealbot_e2e_report.json
```

Expected minimum:

```text
score >= 90
meal_lock_status = closed
vendor_confirmation_status = confirmed
reminders_sent >= 1
```

## Rollback

1. Stop incoming WeCom callback routing or point the application menu to a maintenance notice.
2. Stop `reminder_worker` and `wecom_media_worker` before rolling back API code.
3. Preserve PostgreSQL, attachments, and `operation_logs`; never roll these back by deleting pilot records.
4. Restore the previous API/worker deployment artifact.
5. Run `/readyz`, then run `make benchmark-mealbot-gate` before re-enabling traffic.

Migration `013_release_hardening.sql` is additive and may remain in place during an application rollback.
