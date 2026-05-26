# Staging Ingress Config (Disabled by Default)

## Scope

This directory contains staging ingress configuration for the Go shadow gateway.
**The config is disabled by default (`enabled: false`, `default_weight: 0`).**

No production traffic is affected. No staging traffic is enabled until an explicit
flip is made (future PR).

## File Structure

```
deploy/staging/ingress/
├── go-gateway-shadow.example.yaml   # Example staging ingress config
└── README.md                        # This file
```

## Config Requirements

| Requirement | Value |
|-------------|-------|
| `mode` | `staging_only` |
| `enabled` | `false` (default) |
| `default_weight` | `0` |
| Routes | Only those in `cutover_policy.yaml` `allowed_cutover_routes` |
| Wildcards | Forbidden (`/api/*`, `/api/admin/*`) |
| Production host | Not allowed |
| GET `/api/admin/**` | Blocked |

## Validation

```bash
make check-staging-ingress-config
```

## Enabling Staging Traffic (Future)

When all gates pass and staging evidence is ready, an authorized operator may:

1. Set `enabled: true` for specific routes (never all at once)
2. Set `weight: 1` (per cutover_policy.yaml `max_initial_percent: 1`)
3. Run `make check-staging-ingress-config --allow-enabled --allow-weight`
4. Monitor `observability_contract` metrics
5. Roll back immediately if `rollback_triggers` fire

**This PR does NOT enable traffic. It only prepares the config structure.**
