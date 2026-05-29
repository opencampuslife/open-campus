# Phase 3 Readiness Checklist

**Date**: 2026-05-29  
**Status**: Not started — Phase 2 is frozen  

---

## 1. Remaining Risk Register

| ID | Risk | Severity | Module | Mitigation |
|----|------|----------|--------|------------|
| RISK-1 | Chinese quotation marks (`\u201c\u201d`) in system prompt — must not regress to ASCII `"` | Low | gateway.ts | Add a CI lint rule to forbid `"内部参考"` (ASCII quotes around Chinese text) in gateway.ts |
| RISK-2 | Evidence formatting via `pyRepr()` must match Python dataclass `asdict()` repr exactly | Medium | gateway.ts | Add a character-level snapshot test that compares full message strings against Python fixture output |
| RISK-3 | Production `defaultTransport` (fetch + AbortController) only exercised in real API calls, not in tests | Medium | providerDeepseek.ts | Add an integration test with a local HTTP mock server (e.g., `nock` or `msw`) that tests the default transport path |
| RISK-4 | Environment variables (`DEEPSEEK_API_KEY`, `DEEPSEEK_BASE_URL`, `DEEPSEEK_MODEL`, `DEEPSEEK_ENABLE_LLM`) scattered across 4 modules | Low | cross-cutting | Centralize env var reads into a single config module (e.g., `ts-src/config.ts`) before production cutover |
| RISK-5 | `gateway.py::_clean_chunk()` is dead code — defined but never called in `generate_admissions_answer` | Low | gateway.py | Review and remove if confirmed dead; no TS migration needed |
| RISK-6 | Zod `.strict()` rejects extra fields that Python dataclass silently ignores | Medium | schemas.ts | Audit all callers for extra field usage; if any pass extra fields, they must be removed before cutover |

---

## 2. Phase 3 Prerequisites

### Production Cutover

- [ ] Centralize env var reads (`DEEPSEEK_API_KEY`, `DEEPSEEK_BASE_URL`, `DEEPSEEK_MODEL`, `DEEPSEEK_ENABLE_LLM`) into `ts-src/config.ts`
- [ ] Add `nock`/`msw` integration test for `defaultTransport` (fetch path)
- [ ] Verify Zod strict mode compatibility with all production callers
- [ ] Test with real `DEEPSEEK_API_KEY` in staging environment
- [ ] Verify SSL/certificate handling in `defaultTransport` matches Python's `certifi`
- [ ] Add request retry logic (Python has none; evaluate if needed)

### TypeScript-Only Path

- [ ] Create a `gateway.ts` entry point that does NOT require Python-side `sys.path.append`
- [ ] Ensure `LLMRequestSchema.parse()` handles all production data shapes
- [ ] Add request timeout configuration (currently hardcoded 30s in providerDeepseek)
- [ ] Add graceful shutdown / cancellation support
- [ ] Add metrics/monitoring hooks (currently none in TS path)

### Testing Expansion

- [ ] Add character-level snapshot test for `buildMessages()` output
- [ ] Add default transport integration test (local HTTP mock)
- [ ] Add load/capacity test for `llmLogger.ts` (JSONL append in concurrent scenarios)
- [ ] Add permission-service: test `policyLoader.ts` with real configs (not just error paths)
- [ ] Add permission-service: verify `scopeBuilder.ts` with all known role values

### Documentation

- [ ] Add JSDoc comments to all exported public functions
- [ ] Document `Transport` interface for third-party integration
- [ ] Document env var requirements per module
- [ ] Add migration guide for teams consuming these modules

---

## 3. Python → TS Cutover Strategy

### Option A: Side-by-Side (Recommended)
```
gateway.py (Python)         → production (current)
gateway.ts (TypeScript)     → shadow mode, log-only
                            → after N days of shadow parity validation
                            → switch production to TS
```

### Option B: Feature-Flagged
```
if LLM_GATEWAY_USE_TS == "1":
    return generateAdmissionsAnswer_ts(...)
else:
    return generateAdmissionsAnswer_py(...)
```

### Option C: Direct Cutover
```
Replace import in caller code:
- from gateway import generate_admissions_answer
+ import { generateAdmissionsAnswer } from "./ts-src/gateway.js"
```
Requires Node.js runtime in the caller service.

---

## 4. Remaining Work by Service

| Service | Phase 1 | Phase 2 | Remaining for Phase 3 |
|---------|---------|---------|----------------------|
| source-ingestion-service | ✅ 1 file | — | None |
| rag-service | ✅ 2 files | ✅ 2 files | None |
| recommendation-service | ✅ 4 files | — | None |
| compliance-service | ✅ 1 file | — | None |
| permission-service | ✅ 3 files | — | None |
| llm-gateway | — | ✅ 7 files | **Potential shadow cutover** |
| **Unmigrated services** | — | — | auth-service, crm-service, db-policy-service, knowledge-service, knowledge-graph-service, wecom-adapter, wecom-aibot-bridge, api-gateway, etc. |

---

## 5. Technical Debt Log

| Item | Impact | Suggested Action |
|------|--------|-----------------|
| `noUncheckedIndexedAccess` requires `!` assertions in providerDeepseek.ts | Type safety but verbose | Accept; matches Python's strict access behavior |
| `pyRepr()` in gateway.ts is fragile — depends on JS property order matching Python dataclass field order | Silent mismatch risk | Add snapshot tests comparing Python vs TS message output |
| `llmLogger.ts` uses synchronous `appendFileSync` | Blocks event loop | Consider async write with drain buffer for production |
| No request ID tracing across gateway → provider → logger | Debugging difficulty | Add optional `requestId` passthrough in Phase 3 |
| Fixtures under `ts-migration/fixtures/` are versioned JSON | Large files, merge conflicts | Consider moving to a fixture generation CI pipeline |
| Python tests still import from `src/` via `sys.path.append` | Legacy pattern | Tracked in AGENTS.md as frozen debt |
