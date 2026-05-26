# Gaokao Q&A Agent

This scaffold turns OpenHuman-style memory, Markdown wiki, tools, and model routing into a repeat-school admissions Q&A system.

It is intentionally separate from the existing OpenHuman desktop assistant code. Treat it as the business-domain layer to implement after the P0 survey.

## Shape

- `apps/`: Web chat, sales console, and admin console entry points.
- `services/`: service boundaries for API, auth, permissions, orchestrator, knowledge, RAG, CRM, audit, and evaluation.
- `packages/`: shared business logic such as prompt policy, tool registry, memory tree adaptation, document parsing, compliance, and types.
- `knowledge_vault/`: Markdown knowledge base with public, protected, internal, and admin areas.
- `configs/`: role, data-level, retrieval, model-routing, and compliance policies.
- `tests/`: permission, compliance, RAG, and benchmark cases.

## Production Rule

The agent must filter by permission before retrieval, filter again after retrieval, generate from allowed evidence only, and run output compliance checks before responding.

## Quick Start

```bash
make db-up
make migrate-db-policy
make test-db-policy-live
make test
make benchmark
make demo-api
```

## What Is Implemented

- zero-dependency Markdown knowledge ingestion and local JSON index
- permission scope builder and post-retrieval access checks
- RAG retrieval with production guard for PostgreSQL-only mode
- agent pipeline with audit logging
- isolated LLM gateway with prompt guard and fallback
- compliance service for output screening and rewrite
- API gateway for `/api/gaokao/chat`, `/api/gaokao/sessions`, `/api/gaokao/handoff`
- campus workflow MVP for `/api/campus/*` including WeCom callback, leaves, meals, repairs, and daily report
- CRM handoff summary persistence
- benchmark runner that writes `data/reports/benchmark_report.json`

## Campus MVP

The repo now also contains a single-school campus operations MVP with:

- `services/auth-service/src/campus_auth.py`
- `services/workflow-service/src/campus_domain.py`
- `services/wecom-adapter/src/wecom_adapter.py`
- `services/wecom-aibot-bridge` for WeCom smart-bot WebSocket messages
- `services/api-gateway/src/campus_gateway.py`
- `apps/admin-console` campus pages
- `apps/h5-campus/index.html` H5 shell

Useful commands:

```bash
make test-campus-auth
make test-wecom-adapter
make test-wecom-aibot
make test-campus-flow
make test-campus-rls-live
```
