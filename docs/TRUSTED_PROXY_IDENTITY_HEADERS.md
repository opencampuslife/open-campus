# Trusted Proxy: Identity Header Security

## Architecture

```
External Request
    │
    ▼
┌──────────┐
│   Edge   │  ← Strips ALL x-gaokao-* headers from external
└────┬─────┘
     │
     ▼
┌──────────────┐
│ Auth Service  │  ← Authenticates user, generates identity
└──────┬───────┘
     │
     ▼
┌──────────────────┐
│ Internal Gateway  │  ← Injects x-gaokao-* + x-gaokao-trusted-proxy
└──────┬───────────┘
     │
     ▼
┌──────────────┐
│  Gaokao API  │  ← Validates x-gaokao-trusted-proxy token
└──────────────┘
```

## Rules

1. **Edge MUST strip** all `x-gaokao-*` headers from external requests
2. **Auth service** authenticates the user and produces an identity
3. **Internal gateway** injects:
   - `x-gaokao-user-id`
   - `x-gaokao-role`
   - `x-gaokao-campus`
   - `x-gaokao-trusted-proxy: <TRUSTED_PROXY_TOKEN>`
4. **Gaokao API** validates `x-gaokao-trusted-proxy` before trusting identity headers

## Environment Variables

```
TRUSTED_PROXY_TOKEN=<random-secret-at-least-32-chars>
```

Generate with: `python3 -c 'import secrets; print(secrets.token_hex(32))'`

Set the same value on both the internal gateway and the Gaokao API.

## Enforcement

When `x-gaokao-*` identity headers are present but `x-gaokao-trusted-proxy` is missing or incorrect:

- HTTP 403 Forbidden is returned
- Error: `{"error": "untrusted_proxy", "detail": "untrusted proxy: x-gaokao-* identity headers require x-gaokao-trusted-proxy token"}`
- Connection is closed

## Production Checklist

- [ ] Edge strips `x-gaokao-*` from external requests
- [ ] `TRUSTED_PROXY_TOKEN` set (same value on gateway + API)
- [ ] Internal gateway injects `x-gaokao-trusted-proxy` header
- [ ] Integration test: request with identity headers but no trusted proxy token → 403
- [ ] Integration test: request without identity headers → works as anonymous visitor
