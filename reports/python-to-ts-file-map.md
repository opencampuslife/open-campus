# Python → TypeScript File Mapping (Phase 1 + Phase 2)

**Date**: 2026-05-29  
**Total**: 21 Python files → 22 TypeScript files across 7 service packages  
**Total tests**: 516 across 19 test files

---

## Phase 1 Migration (11 Python → 12 TS)

| # | Round | Service | Python File | TypeScript File | TS Tests | Status |
|---|-------|---------|-------------|-----------------|----------|--------|
| 1 | P1-1 | source-ingestion-service | `src/markdown_normalizer.py` | `ts-src/markdownNormalizer.ts` | 11 | ✅ |
| 2 | P1-2 | rag-service | `src/citation_builder.py` | `ts-src/citationBuilder.ts` | 11 | ✅ |
| 3 | P1-3a | recommendation-service | `src/recommendation_model.py` | `ts-src/recommendationModel.ts` | — | ✅ |
| 4 | P1-3b | recommendation-service | `src/class_rules.py` | `ts-src/classRules.ts` | — | ✅ |
| 5 | P1-3c | recommendation-service | `src/recommendation_engine.py` | `ts-src/recommendationEngine.ts` | 10 | ✅ |
| 6 | P1-3d | recommendation-service | `src/recommendation_explainer.py` | `ts-src/recommendationExplainer.ts` | 12 | ✅ |
| 7 | P1-4 | compliance-service | `src/checker.py` | `ts-src/checker.ts` | 48 | ✅ |
| 8 | P1-5a | rag-service | `src/metadata_filter.py` | `ts-src/metadataFilter.ts` | 33 | ✅ |
| 9 | P1-5b | permission-service | `src/policy_loader.py` | `ts-src/policyLoader.ts` | 31 | ✅ |
| 10 | P1-5c | permission-service | `src/scope_builder.py` | `ts-src/scopeBuilder.ts` | 39 | ✅ |
| 11 | P1-5d | permission-service | `src/access_checker.py` | `ts-src/accessChecker.ts` | 67 | ✅ |

## Phase 2 Migration (10 Python → 10 TS)

| # | Round | Service | Python File | TypeScript File | TS Tests | Status |
|---|-------|---------|-------------|-----------------|----------|--------|
| 12 | P2-R1 | rag-service | `src/reranker.py` | `ts-src/reranker.ts` | 25 | ✅ |
| 13 | P2-R2 | llm-gateway | `src/schemas.py` | `ts-src/schemas.ts` | 24 | ✅ |
| 14 | P2-R3 | rag-service | `src/query_rewriter.py` | `ts-src/queryRewriter.ts` | 26 | ✅ |
| 15 | P2-R4 | llm-gateway | `src/redactor.py` | `ts-src/redactor.ts` | 34 | ✅ |
| 16 | P2-R5 | llm-gateway | `src/model_router.py` | `ts-src/modelRouter.ts` | 10 | ✅ |
| 17 | P2-R6 | llm-gateway | `src/prompt_guard.py` | `ts-src/promptGuard.ts` | 23 | ✅ |
| 18 | P2-R7 | llm-gateway | `src/llm_logger.py` | `ts-src/llmLogger.ts` | 22 | ✅ |
| 19 | P2-R8 | llm-gateway | `src/provider_deepseek.py` | `ts-src/providerDeepseek.ts` | 38 | ✅ |
| 20 | P2-R9 | llm-gateway | `src/gateway.py` | `ts-src/gateway.ts` | 33 | ✅ |

## Combined Summary

| Service Package | Phase 1 Files | Phase 2 Files | Total TS Files | Tests |
|----------------|---------------|---------------|----------------|-------|
| source-ingestion-service | 1 | 0 | 1 | 11 |
| rag-service | 2 | 2 | 4 | 97 |
| recommendation-service | 4 | 0 | 4 | 22 |
| compliance-service | 1 | 0 | 1 | 48 |
| permission-service | 3 | 0 | 3 | 148 |
| llm-gateway | 0 | 7 | 7 | 184 |
| ts-migration (smoke) | — | — | 0 | 6 |
| **Total** | **12** | **10** | **22** | **516** |

## Service Dependency Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                   llm-gateway (7 TS files)                   │
│                                                              │
│  gateway.ts (orchestrator)                                   │
│    ├── schemas.ts ──────────── EvidenceChunk, LLMRequest     │
│    ├── modelRouter.ts ──────── routeModel()                  │
│    ├── promptGuard.ts ──────── validateLlmRequest()          │
│    ├── providerDeepseek.ts ─── chatCompletion() + Transport  │
│    └── llmLogger.ts ────────── logLlmCall()                  │
│          └── redactor.ts ───── redactPayload(), redactText() │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────┐
│              rag-service (4 TS files)         │
│                                               │
│  reranker.ts                                  │
│  queryRewriter.ts                             │
│  citationBuilder.ts                           │
│  metadataFilter.ts                            │
└─────────────────────────────────────────────┘
```

## File Locations

```
services/
├── llm-gateway/
│   ├── ts-src/
│   │   ├── index.ts              (re-exports all modules)
│   │   ├── schemas.ts            ← schemas.py
│   │   ├── redactor.ts           ← redactor.py
│   │   ├── modelRouter.ts        ← model_router.py
│   │   ├── promptGuard.ts        ← prompt_guard.py
│   │   ├── llmLogger.ts          ← llm_logger.py
│   │   ├── providerDeepseek.ts   ← provider_deepseek.py
│   │   └── gateway.ts            ← gateway.py
│   └── ts-tests/
│       ├── schemas.test.ts
│       ├── redactor.test.ts
│       ├── modelRouter.test.ts
│       ├── promptGuard.test.ts
│       ├── llmLogger.test.ts
│       ├── providerDeepseek.test.ts
│       └── gateway.test.ts
├── rag-service/
│   ├── ts-src/
│   │   ├── reranker.ts           ← reranker.py
│   │   ├── queryRewriter.ts      ← query_rewriter.py
│   │   ├── citationBuilder.ts    ← citation_builder.py
│   │   └── metadataFilter.ts     ← metadata_filter.py
│   └── ts-tests/
│       ├── reranker.test.ts
│       ├── queryRewriter.test.ts
│       ├── citationBuilder.test.ts
│       └── metadataFilter.test.ts
├── permission-service/            [Phase 1, 3 TS files]
├── compliance-service/            [Phase 1, 1 TS file]
├── recommendation-service/        [Phase 1, 4 TS files]
├── source-ingestion-service/      [Phase 1, 1 TS file]
ts-migration/
└── fixtures/
    ├── reranker.json
    ├── llm_gateway_schemas.json
    ├── query_rewriter.json
    ├── redactor.json
    ├── model_router.json
    ├── prompt_guard.json
    ├── llm_logger.json
    ├── provider_deepseek.json
    ├── gateway.json
    ├── citation_builder.json
    ├── metadata_filter.json
    ├── permission_service.json
    ├── compliance_checker.json
    └── recommendation_model.json
```
