# Shadow Dry-Run Runbook

## Overview

The shadow dry-run validates the Go shadow gateway against the Python legacy gateway in a controlled, repeatable manner. It starts the Go shadow gateway (Docker), collects health/inventory/legacy-usage data, and optionally runs live parity for explicitly enabled proxy routes.

No production traffic is touched. No ingress, load balancer, or automatic mirroring is used.

## Prerequisites

- Docker and Docker Compose installed (`docker compose` or `docker-compose`)
- Python 3 running the legacy gateway on `http://localhost:8787`
  - Start with: `make demo-api`
  - Or your own `python3 services/api-gateway/src/server.py --root . --port 8787`
- `curl` or Python `requests` available for health checks

## Quick Start

```bash
make shadow-up
make shadow-health
make shadow-dry-run
make shadow-down
```

Or run the full pipeline in one command:

```bash
make shadow-dry-run
```

This will:
1. Build and start the Go shadow gateway (port 8788, proxy disabled by default)
2. Wait for `/api/health` to return 200
3. Collect route inventory
4. Scan for legacy GET usage events
5. Run live parity only when `SHADOW_PROXY_ENABLED=true` and matching `SHADOW_PROXY_ROUTES` are explicitly set
6. Generate `reports/shadow/latest.json`
7. Keep the container running (run `make shadow-down` to stop)

## Manual Steps

### 1. Start the legacy Python gateway

```bash
make demo-api
```

### 2. Start the Go shadow gateway

```bash
make shadow-up
```

Verify:

```bash
curl http://localhost:8788/api/health
```

### 3. Run the dry-run pipeline

```bash
make shadow-dry-run
```

To opt into live parity, enable only the intended route allowlist:

```bash
SHADOW_PROXY_ENABLED=true \
SHADOW_PROXY_ROUTES="POST /api/gaokao/chat" \
make shadow-dry-run
```

Admin POST live parity is also opt-in:

```bash
SHADOW_PROXY_ENABLED=true \
SHADOW_PROXY_ROUTES="POST /api/admin/ingestion/runs/{run_id}/cancel,POST /api/admin/staging/docs/{doc_id}/validate,POST /api/admin/staging/docs/{doc_id}/approve,POST /api/admin/staging/docs/{doc_id}/reject,POST /api/admin/staging/docs/{doc_id}/publish" \
make shadow-dry-run
```

### 4. Stop

```bash
make shadow-down
```

## Report

The report is written to `reports/shadow/latest.json`:

```json
{
  "generated_at": "2026-05-27T00:00:00Z",
  "summary": {
    "health_ok": true,
    "route_count": 115,
    "legacy_gaps": 0,
    "deprecated_aliases": 5,
    "chat_parity": "passed",
    "admin_post_parity": "passed",
    "legacy_get_usage_events": 0
  },
  "latency": {
    "chat_warn_count": 0,
    "admin_warn_count": 0
  },
  "details": {
    "chat_passed": 8,
    "chat_failed": 0,
    "admin_passed": 8,
    "admin_failed": 0
  },
  "parity_cases": {
    "chat": [
      {
        "name": "gaokao_chat_minimal_valid",
        "status": "passed",
        "latency_ratio": 1.03,
        "diff_category": "none"
      }
    ],
    "admin": []
  },
  "diffs": [],
  "inventory": { ... }
}
```

No request/response bodies are included in `latest.json` — only case name, status, latency ratio, and diff category are summarized.

### Individual report files

| File | Content |
|------|---------|
| `reports/shadow/health.json` | Raw `/api/health` response |
| `reports/shadow/inventory.json` | Route inventory |
| `reports/shadow/legacy_usage.json` | Legacy GET usage event count |
| `reports/shadow/chat_parity.jsonl` | Go test `-json` output (chat) |
| `reports/shadow/admin_parity.jsonl` | Go test `-json` output (admin) |
| `reports/shadow/latest.json` | Aggregated dry-run report |

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SHADOW_PORT` | `8788` | Go shadow gateway port |
| `SHADOW_URL` | `http://localhost:8788` | Go shadow gateway URL |
| `PYTHON_URL` | `http://localhost:8787` | Python legacy gateway URL |
| `PYTHON_GATEWAY_BASE_URL` | `http://host.docker.internal:8787` | Upstream from inside Docker (Linux: set to `http://172.17.0.1:8787`) |
| `SHADOW_PROXY_ENABLED` | `false` | Enables explicit proxy allowlist for optional live parity |
| `SHADOW_PROXY_ROUTES` | empty | Comma-separated `METHOD /path` allowlist |
| `COMPOSE_CMD` | auto-detects `docker-compose` then `docker compose` | Compose command override |

### Linux host networking

On Linux, Docker's `host.docker.internal` may not resolve. Use:

```bash
PYTHON_GATEWAY_BASE_URL=http://172.17.0.1:8787 make shadow-up
```

Or add `--add-host host.docker.internal:host-gateway` to `docker-compose.shadow.yml`.

## Troubleshooting

### Shadow gateway doesn't start

Check Docker build logs:

```bash
docker compose -f docker-compose.shadow.yml build --no-cache
```

### Health check fails

The Go gateway must have `contracts/routes.yaml` in its build context. The Dockerfile copies it at build time. If the contract file changed, rebuild:

```bash
make shadow-down
make shadow-up
```

### Live parity fails

Ensure the Python legacy gateway is running and reachable from the Go shadow container, and that `SHADOW_PROXY_ENABLED=true` plus explicit `SHADOW_PROXY_ROUTES` are set. On Docker Desktop for Mac, `host.docker.internal` resolves automatically. On Linux, use `172.17.0.1` or the docker bridge IP.

### Container port conflict

Use a different port:

```bash
SHADOW_PORT=18788 make shadow-up
make shadow-dry-run SHADOW_URL=http://localhost:18788
```

## Security

- Go shadow gateway runs as non-root user `gaokao`.
- All forwarded requests carry `X-Gaokao-Gateway-Mode: shadow`.
- No raw request/response bodies are written to the report.
- No DB access, auth, or CSRF decisions by the Go gateway.
