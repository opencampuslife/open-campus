#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
DATE="${1:-$(date +%Y-%m-%d)}"
WARNINGS=0
FAILURES=0

warn() { echo "  ⚠  WARN: $1"; WARNINGS=$((WARNINGS + 1)); }
fail() { echo "  ✗  FAIL: $1"; FAILURES=$((FAILURES + 1)); }
ok()   { echo "  ✓  $1"; }

echo "============================================================"
echo "  Gaokao Agent Pilot Daily Report — ${DATE}"
echo "============================================================"
echo ""

# ── Environment check ────────────────────────
echo "── Environment ──"

APP_ENV="${GAOKAO_ENV:-development}"
echo "  GAOKAO_ENV:            ${APP_ENV}"
[ "${APP_ENV}" = "production" ] && ok "production mode" || warn "not production (GAOKAO_ENV=${APP_ENV})"

RAG_SRC="${RAG_SOURCE:-json}"
echo "  RAG_SOURCE:            ${RAG_SRC}"
[ "${RAG_SRC}" = "postgres" ] && ok "RAG from postgres" || warn "RAG_SOURCE=${RAG_SRC} (should be postgres in production)"

REMOTE_INGEST="${ENABLE_REMOTE_URL_INGESTION:-0}"
echo "  Remote URL ingestion:  ${REMOTE_INGEST}"
[ "${REMOTE_INGEST}" = "0" ] && ok "remote ingestion disabled" || warn "remote ingestion ENABLED"

DEV_ID="${ALLOW_DEV_IDENTITY_OVERRIDE:-0}"
[ "${DEV_ID}" = "1" ] && warn "dev identity override enabled (should be 0 in production)" || true

CSRF="${CSRF_TOKEN_SECRET:-}"
if [ -z "${CSRF}" ]; then
    warn "CSRF_TOKEN_SECRET not set"
elif [ "${#CSRF}" -lt 32 ]; then
    warn "CSRF_TOKEN_SECRET too short (< 32 chars)"
fi

PROXY="${TRUSTED_PROXY_TOKEN:-}"
if [ -z "${PROXY}" ]; then
    warn "TRUSTED_PROXY_TOKEN not set"
elif [ "${#PROXY}" -lt 32 ]; then
    warn "TRUSTED_PROXY_TOKEN too short (< 32 chars)"
fi

echo ""

# ── Health check ─────────────────────────────
echo ""
echo "── Health ──"
API_URL="${API_URL:-http://localhost:8787}"
HEALTH=$(curl -sf --connect-timeout 3 --max-time 5 "${API_URL}/api/health" 2>/dev/null && echo "ok" || echo "fail")
echo "  API /health:           ${HEALTH}"
[ "${HEALTH}" != "fail" ] && ok "API healthy" || fail "API unreachable"

# ── Knowledge index check ────────────────────
echo ""
echo "── Knowledge ──"

DB_URL="${DATABASE_URL_ADMIN:-}"

# Count knowledge_vault docs
if [ -d "${ROOT}/knowledge_vault" ]; then
    KV_DOCS=$(find "${ROOT}/knowledge_vault" -name '*.md' -not -path '*/metadata/*' 2>/dev/null | wc -l | tr -d ' ')
    echo "  Vault docs (md):       ${KV_DOCS}"
else
    KV_DOCS=0
    warn "knowledge_vault/ missing"
fi

# Count published docs
if [ -d "${ROOT}/data/published" ]; then
    PUB_DOCS=$(find "${ROOT}/data/published" -name '*.json' 2>/dev/null | wc -l | tr -d ' ')
else
    PUB_DOCS=0
fi

# Check PostgreSQL
PG_DOCS=0
PG_CHUNKS=0
DB_URL="${DATABASE_URL_ADMIN:-}"
if [ -n "${DB_URL}" ] && command -v psql &>/dev/null; then
    PGPASSWORD=$(echo "${DB_URL}" | sed -n 's/.*:\/\/[^:]*:\([^@]*\)@.*/\1/p') 2>/dev/null || true
    export PGPASSWORD
    PG_DOCS=$(psql "${DB_URL}" -t -c "SELECT count(*) FROM knowledge_docs" 2>/dev/null | tr -d ' ' || echo "0")
    PG_CHUNKS=$(psql "${DB_URL}" -t -c "SELECT count(*) FROM knowledge_chunks" 2>/dev/null | tr -d ' ' || echo "0")
fi

echo "  Published flat:        ${PUB_DOCS}"
echo "  PostgreSQL docs:       ${PG_DOCS}"
echo "  PostgreSQL chunks:     ${PG_CHUNKS}"

# Gate: PostgreSQL should have data
if [ "${PG_DOCS}" -gt 0 ] 2>/dev/null; then
    ok "PostgreSQL has ${PG_DOCS} docs"
else
    fail "PostgreSQL index empty — run: make sync-db-index"
fi

if [ "${PG_CHUNKS}" -gt 0 ] 2>/dev/null; then
    ok "PostgreSQL has ${PG_CHUNKS} chunks"
else
    fail "PostgreSQL chunks empty"
fi

# Gate: flat published should not be 0 if PG is alive
if [ "${PUB_DOCS}" -eq 0 ] && [ "${PG_DOCS}" -gt 0 ] 2>/dev/null; then
    warn "Flat published dir empty but PG has data (RAG from postgres is OK)"
fi

echo ""

# ── Sessions ─────────────────────────────────
echo "── Sessions ──"
SESSION_DIR="${ROOT}/data/sessions"
if [ -d "${SESSION_DIR}" ]; then
    TODAY_SESSIONS=$(find "${SESSION_DIR}" -name '*.json' -newermt "${DATE}" 2>/dev/null | wc -l | tr -d ' ')
    TOTAL_SESSIONS=$(find "${SESSION_DIR}" -name '*.json' 2>/dev/null | wc -l | tr -d ' ')
    echo "  Today:                 ${TODAY_SESSIONS}"
    echo "  Total:                 ${TOTAL_SESSIONS}"
else
    TODAY_SESSIONS=0
    echo "  Sessions:              0 (no session dir)"
fi

echo ""

# ── CRM / Leads ──────────────────────────────
echo "── CRM ──"
LEAD_DIR="${ROOT}/data/crm/leads"
if [ -d "${LEAD_DIR}" ]; then
    TODAY_LEADS=$(find "${LEAD_DIR}" -name '*.json' -newermt "${DATE}" 2>/dev/null | wc -l | tr -d ' ')
    TOTAL_LEADS=$(find "${LEAD_DIR}" -name '*.json' 2>/dev/null | wc -l | tr -d ' ')
    echo "  Today leads:           ${TODAY_LEADS}"
    echo "  Total leads:           ${TOTAL_LEADS}"
else
    echo "  Leads:                 0 (no lead dir)"
    TOTAL_LEADS=0
fi

echo ""

# ── Audit events ─────────────────────────────
echo "── Audit ──"
AUDIT_DIR="${ROOT}/data/audit"
if [ -d "${AUDIT_DIR}" ]; then
    AUDIT_TODAY=$(find "${AUDIT_DIR}" -name "events_*${DATE//-/}*.jsonl" 2>/dev/null)
    if [ -n "${AUDIT_TODAY}" ]; then
        AUDIT_COUNT=$(wc -l ${AUDIT_TODAY} 2>/dev/null | tail -1 | awk '{print $1}' || echo "0")
        HANDOFF_COUNT=$(grep -c 'handoff' ${AUDIT_TODAY} 2>/dev/null | awk -F: '{s+=$NF}END{print s+0}' || echo "0")
        CRISIS_COUNT=$(grep -c 'crisis' ${AUDIT_TODAY} 2>/dev/null | awk -F: '{s+=$NF}END{print s+0}' || echo "0")
    else
        AUDIT_COUNT=0; HANDOFF_COUNT=0; CRISIS_COUNT=0
    fi
    echo "  Today events:          ${AUDIT_COUNT}"
    echo "  Handoffs:              ${HANDOFF_COUNT}"
    echo "  Crisis:                ${CRISIS_COUNT}"

    if [ "${CRISIS_COUNT}" -gt 0 ] 2>/dev/null; then
        warn "Crisis events detected (${CRISIS_COUNT}) — review all crisis conversations"
    fi
else
    echo "  Audit:                 no audit dir"
    AUDIT_COUNT=0
fi

echo ""

# ── Backup check ─────────────────────────────
echo "── Backup ──"
BACKUP_DIR="${ROOT}/data/backups"
if [ -d "${BACKUP_DIR}" ]; then
    LATEST_BACKUP=$(ls -t "${BACKUP_DIR}"/backup_*.tar.gz 2>/dev/null | head -1 || echo "")
    if [ -n "${LATEST_BACKUP}" ]; then
        BACKUP_SIZE=$(du -sh "${LATEST_BACKUP}" 2>/dev/null | cut -f1 || echo "?")
        echo "  Latest:                ${BACKUP_SIZE}"
        ok "Backup exists"
    else
        warn "No backup found — run: make backup"
    fi
else
    warn "No backup directory"
fi

echo ""

# ── Staging ──────────────────────────────────
echo "── Staging ──"
STAGING_DIR="${ROOT}/data/staging"
if [ -d "${STAGING_DIR}" ]; then
    STAGING_COUNT=$(find "${STAGING_DIR}" -name '*.json' 2>/dev/null | wc -l | tr -d ' ')
    echo "  Staging docs:          ${STAGING_COUNT}"
else
    echo "  Staging docs:          0"
fi

echo ""

# ── Rate limits / CSRF check ────────────────
echo ""
echo "── Security Signals ──"
CSRF_TEST=$(curl -sf --connect-timeout 3 --max-time 5 "${API_URL}/api/csrf-token" 2>/dev/null && echo "ok" || echo "fail")
echo "  CSRF token endpoint:   ${CSRF_TEST}"
[ "${CSRF_TEST}" != "fail" ] && ok "CSRF endpoint working" || warn "CSRF token endpoint not working"

# ── Tone quality check ───────────────────────
echo ""
echo "── Tone Quality ──"
if [ -f "${ROOT}/services/evaluation-service/src/benchmark_tone_quality.py" ]; then
    TONE_OUT=$(python3 "${ROOT}/services/evaluation-service/src/benchmark_tone_quality.py" 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin).get('pass_rate',0))" 2>/dev/null || echo "0")
    echo "  Tone pass rate:        ${TONE_OUT}%"
    if [ "$(echo "${TONE_OUT:-0} >= 80" | bc 2>/dev/null)" = "1" ]; then
        ok "Tone quality above threshold"
    else
        warn "Tone quality below 80% (${TONE_OUT}%)"
    fi
else
    echo "  Tone benchmark:        not available"
fi

echo ""

# ── Gate summary ─────────────────────────────
echo "============================================================"
echo "  Gate Result"
echo "============================================================"
echo "  Warnings:               ${WARNINGS}"
echo "  Failures:               ${FAILURES}"
echo ""

if [ "${FAILURES}" -gt 0 ]; then
    echo "  ✗  GATE FAILED — ${FAILURES} critical issue(s)"
    echo "  Fix failures before starting pilot"
    echo ""
    echo "  Quick fix checklist:"
    echo "    make sync-db-index"
    echo "    make backup"
    echo "    make benchmark-tone-quality"
    exit 1
elif [ "${WARNINGS}" -gt 0 ]; then
    echo "  ⚠  GATE WARN — ${WARNINGS} warning(s)"
    echo "  Review warnings, pilot can proceed with caution"
    exit 0
else
    echo "  ✓  GATE PASS — all checks green"
    exit 0
fi

echo ""
echo "  Generated: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "============================================================"
