# ADR-0001: Preserve heterogeneous runtime boundaries

**Status**: Accepted
**Date**: 2026-05-28
**Deciders**: Architecture team
**Supersedes**: None

## Context

The repository (`opencampuslife/open-campus`) contains a multi-service AI agent platform for Gaokao admissions. The codebase has evolved with three runtimes:

- **Go** — control plane: routing, rate limiting, circuit breaking, shadow traffic, parity checking, evidence collection, canary, cutover readiness.
- **Python** — capability services: agent orchestration, RAG, LLM gateway, compliance, CRM, knowledge, recommendation, evaluation, mealbot, database policy.
- **TypeScript** — frontend: admin console, dashboard, operator UI.

The legacy `services/api-gateway` is a monolithic Python service (1,062 lines in `server.py`) that mixes control-plane and capability responsibilities. A migration to split it is ongoing, but there is recurring discussion about whether Python capability services should be rewritten to TypeScript for "runtime unification."

Recent dependency governance work (P0/P1/P1.5) revealed:
- 11 of 17 Python services have zero third-party dependencies (stdlib-only).
- The heaviest dependency (`docling` → `torch` → 390 MB) is isolated to `source-ingestion-service`.
- The packaging challenge is about **dependency boundary isolation**, not language unsuitability.
- A language-level rewrite would create massive risk with no corresponding architectural gain.

## Decision

**We will not rewrite Python capability services into TypeScript or any other language.**

Go remains the deterministic control plane. Python remains the capability layer for AI, RAG, policy, evaluation, compliance, recommendation, and domain services. TypeScript remains the UI/admin-console and type-boundary layer.

The legacy Python `api-gateway` may continue to be phased out, but through Go control-plane migration and service decomposition — not through a TypeScript rewrite.

Specifically:

| What | Decision |
|---|---|
| Python capability services | Retain. No rewrite to TS/JS/any. |
| Python `api-gateway` | Continue Strangler Fig migration to Go services. |
| TypeScript expansion | Admin console, OpenAPI client gen, route contract types, dashboard, workflow editor, operator console, BFF (only where UI aggregation required). |
| New DSL/anyscript | Not adopted. Only reconsider if a clear boundary (route/contract/evidence-verifiable) emerges that doesn't duplicate Python domain logic. |

## Consequences

### Positive

1. **Zero-regret migration**: The Strangler Fig pattern lets us validate each cutover with evidence/parity/canary. A rewrite would skip this validation and ship unknown risk.
2. **Dependency isolation** remains tractable: Python's heavy dependencies (torch, transformers, opencv) are already concentrated in one service; service-scoped `uv sync` can contain them further.
3. **TypeScript effort** goes to product value: generated clients, admin console features, contract types — not reproducing proven domain logic.
4. **Team leverage**: domain experts in AI/RAG/policy continue in Python; infrastructure engineers in Go; frontend engineers in TypeScript. No forced context-switch.

### Negative

1. **Three runtimes** must be maintained. CI must run three language toolchains. This is accepted as the cost of using the right tool for each domain.
2. **Python packaging debt** must still be paid: service-scoped sync, entrypoints, test fixtures, OpenAPI schema exports. This is P2+ work, not solved by language choice.
3. **Cross-runtime contract** verification (route contracts, parity checks) requires investment in tooling. Some of this exists (`contracts/routes.yaml`, evidence framework); more is needed.

### Risks

| Risk | Mitigation |
|---|---|
| Python dependency bloat spreads | Enforce service-scoped `uv sync`; isolate heavy deps in Docker multi-stage. |
| Go control-plane velocity slows | Continue per-service decomposition; avoid monolithic Go gateway. |
| TypeScript scope creep | Only UI/admin-console, BFF, generated clients. No domain logic in TS. |

## Alternatives Considered

### Rewrite Python services to TypeScript (rejected)
- **Why**: No incremental validation path. 11 stdlib-only services gain nothing from a rewrite. Heavy-dependency services (source-ingestion) would still pull the same weight in any language via equivalent libraries.
- **Risk**: Ship-stopping regression in AI/RAG behavior; 6-12 month distraction with zero user value.

### Unify on Python only (rejected)
- **Why**: Go's deterministic concurrency, fast startup, and static binary are correct for control-plane routing. Python's latency and GIL make it wrong for gateway-level request dispatch.

### Adopt Rust for control plane (deferred)
- **Why**: Go is already established and working. No sufficient pain to justify a migration. Revisit if Go's memory model or goroutine overhead becomes a bottleneck.

## References

- P0 packaging baseline: `main` (`ed2065c7`, `2d95b3a8`)
- P1 uv.lock baseline: PR #18 (`ece86ba1`)
- P1.5 blast radius evaluation: PR #19
- `reports/uv_sync_blast_radius.md`
- `reports/docling_dependency_impact.md`
- `contracts/service_ownership.json`
- `docs/architecture/service-ownership-matrix.md`
- `docs/architecture/code-health-review-2026-05-27.md`
