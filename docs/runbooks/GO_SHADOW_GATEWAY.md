# Go Shadow Gateway Runbook

## Overview

The Go shadow gateway (`gaokao-gateway`) is a zero-dependency Go control plane that runs alongside the Python API gateway. In shadow mode it serves `/api/health` and optionally proxies allowed routes to the Python upstream. It does not own business logic, auth, CSRF, DB, or production traffic routing.

## Startup modes

### Shadow (no proxy)

```bash
make run-go-gateway-shadow
```

Serves `/api/health` only. No traffic proxying.

### Shadow with gaokao chat proxy

```bash
make run-go-gateway-shadow-proxy
```

Serves `/api/health` and proxies `POST /api/gaokao/chat` to Python.

### Shadow with admin POST proxy

```bash
make run-go-admin-shadow-proxy
```

Serves `/api/health` and proxies the 5 admin POST replacement routes. Deprecated GET aliases return `405 DEPRECATED_ROUTE_NOT_PROXIED`.

### Docker

```bash
make build-go-shadow-gateway
make shadow-up
```

`make shadow-up` starts with `SHADOW_PROXY_ENABLED=false` and an empty route allowlist. To opt into a shadow proxy route, pass both env vars explicitly:

```bash
SHADOW_PROXY_ENABLED=true \
SHADOW_PROXY_ROUTES="POST /api/gaokao/chat" \
make shadow-up
```

The Make targets use Docker Compose v2 by default (`docker compose`). Override with `DOCKER_COMPOSE=docker-compose` if your host uses the legacy binary.

## Environment / flags

| Flag | Env var | Default | Description |
|------|---------|---------|-------------|
| `--listen` | `LISTEN_ADDR` | `:8788` | Listen address |
| `--routes` | `ROUTES_CONTRACT_PATH` | `contracts/routes.yaml` | Route contract path |
| `--python-base-url` | `PYTHON_GATEWAY_BASE_URL` | `http://localhost:8787` | Python upstream |
| `--shadow-mode` | `SHADOW_MODE` | `true` | Shadow vs active mode |
| `--shadow-proxy-enabled` | `SHADOW_PROXY_ENABLED` | `false` | Enable proxy routes |
| `--shadow-proxy-routes` | `SHADOW_PROXY_ROUTES` | `""` | Comma-separated allowlist |
| `--log-level` | `LOG_LEVEL` | `info` | silent \| error \| warn \| info \| debug |

## Health check

```
GET /api/health
```

Expected response:

```json
{
  "status": "ok",
  "service": "gaokao-gateway",
  "mode": "shadow",
  "routes_contract_loaded": true,
  "route_count": 115,
  "legacy_gap_count": 0,
  "deprecated_compatibility_alias_count": 5
}
```

## Smoke test

```bash
make smoke-go-shadow-gateway
```

Checks:

1. Builds the Docker image
2. Starts the container on port 18788
3. Verifies `/api/health` returns 200 with `route_count=115`, `legacy_gap_count=0`
4. Verifies a deprecated GET alias returns 405
5. Verifies a disabled proxy route returns `PROXY_ROUTE_DISABLED`
6. Stops and removes the container

## Troubleshooting

### Container won't start

Check that `contracts/routes.yaml` is present in the build context. The Dockerfile copies it at build time.

### Health endpoint returns 404

The mux only registers `/api/health` (no trailing slash). Ensure you are hitting the exact path.

### Proxy route returns PROXY_ROUTE_DISABLED

`SHADOW_PROXY_ENABLED` must be `true` and the route method+path must appear in `SHADOW_PROXY_ROUTES`.

### Deprecated GET returns 404 instead of 405

The deprecated alias deny only activates when at least one admin POST route is explicitly present in `SHADOW_PROXY_ROUTES`. Without an admin allowlist, the catch-all handler returns `ROUTE_NOT_FOUND`.

## Security

- No DB access.
- No auth, CSRF, or RBAC decisions made by the Go gateway.
- All forwarded requests carry `X-Gaokao-Gateway-Mode: shadow`.
- Container runs as non-root user `gaokao`.
- Docker compose defaults the Python upstream to `http://host.docker.internal:8787`; Linux users should override `PYTHON_GATEWAY_BASE_URL`.
