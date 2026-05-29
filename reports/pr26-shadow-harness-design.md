# PR #26: TypeScript Parity Shadow Harness

## Status

- **Design**: v1.0
- **PR**: #26
- **Depends on**: PR #25 (merged `d1776db2`)

## Purpose

Provide a disabled-by-default infrastructure to run Python vs TypeScript shadow comparisons for migrated modules. The harness records redacted diffs to a gitignored JSONL directory. It never affects production responses.

## Architecture

```
Caller code
    │
    ▼
runShadow(config, moduleName, input)
    │
    ├─ config.modules[moduleName].enabled? ──no──▸ return (no-op)
    │
    ▼ yes
    ├─ hash input → input_hash
    ├─ call compareFn(input) → {python, ts}
    ├─ hash python_output → python_output_hash
    ├─ hash ts_output → ts_output_hash
    ├─ compare hashes → match
    ├─ if !match: compute diff → truncate + redact
    └─ write JSONL report → shadow-reports/shadow-YYYY-MM-DD.jsonl
```

## Schema

```typescript
interface ShadowReport {
  module: string;              // e.g. "markdown_normalizer"
  input_hash: string;          // sha256(stableJson(input))[:16]
  python_output_hash: string;  // sha256(stableJson(python_output))[:16]
  ts_output_hash: string;      // sha256(stableJson(ts_output))[:16]
  match: boolean;              // python_output_hash === ts_output_hash
  diff_truncated: string|null; // "python:{py}|ts:{ts}" if !match, redacted + truncated to 2KB
  timestamp: string;           // ISO 8601 with microsecond precision
}
```

## Files

| File | Role |
|------|------|
| `ts-migration/src/shadow.ts` | Core harness: types, hashing, diff, redaction, JSONL writer, `runShadow()` |
| `ts-migration/tests/shadow.test.ts` | 27 tests covering all harness functions |
| `shadow-reports/.gitkeep` | Keep empty directory in git |
| `.gitignore` | `shadow-reports/*.jsonl` excluded |
| `reports/pr26-shadow-harness-design.md` | This document |

## Configuration

```typescript
interface ShadowConfig {
  reportsDir: string;          // path to JSONL output directory
  modules: Record<string, {   // per-module enable switch
    enabled: boolean;
    module: string;
    compareFn: (input: unknown) => { python: unknown; ts: unknown };
  }>;
}
```

All modules default to `enabled: false`. To enable:

```typescript
shadowConfig.modules.markdown_normalizer.enabled = true;
```

## Security

- **Redaction**: API keys (`sk-*`, `api_key=`), bearer tokens are redacted from diff output
- **No exfiltration**: Reports stay in local `shadow-reports/`, gitignored
- **No data return**: `runShadow` returns `void`; shadow result never reaches caller

## Error Handling

- `compareFn` throws → caught by `runShadow` → returns silently (no crash)
- JSONL write failure → propagates naturally (caller can wrap in try/catch)
- Mismatch never throws

## Rollback

1. Set `enabled: false` on all modules (already the default)
2. Delete `shadow-reports/` directory contents (gitignored, no trace)
3. Revert the PR if needed

## Module Integration Plan

| Module | Risk | Priority | Harness Ready |
|--------|------|----------|---------------|
| markdown_normalizer | Low | P0 | ✅ This PR |
| citation_builder | Low | P1 | Next PR |
| compliance_checker | Medium | P1 | Next PR |
| recommendation_model | Medium | P2 | Later |
| permission_service | High | P2 | Later |
| metadata_filter | Medium | P2 | Later |
| gateway | High | P3 | After integration |

## Acceptance Criteria

- [x] `shadow-reports/` gitignored
- [x] Shadow report schema with TS types
- [x] JSONL writer (1 file per day, append)
- [x] Stable JSON hashing (deterministic, key-sorted)
- [x] Hash comparison for match detection
- [x] Diff truncation at 2 KB
- [x] Diff redaction (API keys, tokens)
- [x] `runShadow` no-op when module disabled
- [x] `runShadow` writes report when enabled
- [x] `runShadow` handles errors silently
- [x] Example module: `markdown_normalizer`
- [x] 27 tests passing
- [x] No changes to Python source, contracts, configs, or production paths
