#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

APP_ENV="${GAOKAO_ENV:-production}"
DB_URL="${DATABASE_URL_ADMIN:-}"
PYTHON="python3"

echo "=== Gaokao Agent Runtime Check ==="
echo "Root: ${ROOT}"
echo "Env:  ${APP_ENV}"
echo ""

failures=0

sep() { echo "---"; }

# ── Python ───────────────────────────────────
sep
echo -n "[python] "
if command -v "${PYTHON}" &>/dev/null; then
    ver=$("${PYTHON}" --version 2>&1)
    echo "OK (${ver})"
else
    echo "MISSING"
    ((failures++))
fi

# ── Docker / compose ─────────────────────────
sep
echo -n "[docker] "
if command -v docker &>/dev/null; then
    echo "OK ($(docker --version 2>&1))"
else
    echo "MISSING"
    ((failures++))
fi

# ── PostgreSQL ───────────────────────────────
sep
echo -n "[postgres/pg_isready] "
if command -v pg_isready &>/dev/null; then
    echo "OK"
else
    echo "NOT FOUND (local pg_isready not required if using docker)"
fi

# ── pgvector extension ───────────────────────
sep
echo -n "[pgvector extension] "
if [ -n "${DB_URL}" ]; then
    if "${PYTHON}" -c "
import psycopg2
conn = psycopg2.connect('${DB_URL}')
conn.autocommit = True
cur = conn.cursor()
cur.execute(\"SELECT 1 FROM pg_extension WHERE extname = 'vector'\")
ok = cur.fetchone() is not None
conn.close()
exit(0 if ok else 1)
" 2>/dev/null; then
        echo "INSTALLED"
    else
        echo "MISSING — run: CREATE EXTENSION vector;"
        ((failures++))
    fi
else
    echo "SKIPPED (DATABASE_URL_ADMIN not set)"
fi

# ── RLS enforcement ──────────────────────────
sep
echo -n "[RLS on knowledge_documents] "
if [ -n "${DB_URL}" ]; then
    if "${PYTHON}" -c "
import psycopg2
conn = psycopg2.connect('${DB_URL}')
conn.autocommit = True
cur = conn.cursor()
cur.execute(\"\"\"
    SELECT 1 FROM pg_class c
    JOIN pg_namespace n ON c.relnamespace = n.oid
    WHERE n.nspname = 'public' AND c.relname = 'knowledge_documents' AND c.relforcerowsecurity
\"\"\")
ok = cur.fetchone() is not None
conn.close()
exit(0 if ok else 1)
" 2>/dev/null; then
        echo "ENABLED"
    else
        echo "NOT ENABLED"
        ((failures++))
    fi
else
    echo "SKIPPED (DATABASE_URL_ADMIN not set)"
fi

# ── search_accessible_chunks ─────────────────
sep
echo -n "[search_accessible_chunks function] "
if [ -n "${DB_URL}" ]; then
    if "${PYTHON}" -c "
import psycopg2
conn = psycopg2.connect('${DB_URL}')
conn.autocommit = True
cur = conn.cursor()
cur.execute(\"\"\"
    SELECT 1 FROM pg_proc p
    JOIN pg_namespace n ON p.pronamespace = n.oid
    WHERE n.nspname = 'public' AND p.proname = 'search_accessible_chunks'
\"\"\")
ok = cur.fetchone() is not None
conn.close()
exit(0 if ok else 1)
" 2>/dev/null; then
        echo "EXISTS"
    else
        echo "MISSING — run: make migrate-db-policy"
        ((failures++))
    fi
else
    echo "SKIPPED (DATABASE_URL_ADMIN not set)"
fi

# ── Migrations applied ───────────────────────
sep
echo -n "[DB migrations] "
if [ -n "${DB_URL}" ]; then
    if "${PYTHON}" -c "
import psycopg2
conn = psycopg2.connect('${DB_URL}')
conn.autocommit = True
cur = conn.cursor()
cur.execute(\"SELECT to_regclass('public.knowledge_documents')\")
ok = cur.fetchone()[0] is not None
conn.close()
exit(0 if ok else 1)
" 2>/dev/null; then
        echo "APPLIED"
    else
        echo "NOT APPLIED — run: make migrate-db-policy"
        ((failures++))
    fi
else
    echo "SKIPPED (DATABASE_URL_ADMIN not set)"
fi

# ── Knowledge vault ──────────────────────────
sep
echo -n "[knowledge_vault/] "
if [ -d "${ROOT}/knowledge_vault" ]; then
    if [ -w "${ROOT}/knowledge_vault" ]; then
        echo "OK (writable)"
    else
        echo "NOT WRITABLE"
        ((failures++))
    fi
else
    echo "MISSING"
    ((failures++))
fi

# ── Data directories ─────────────────────────
sep
for d in data/crm data/staging data/ingestion data/graph-runs data/audit_logs data/published; do
    echo -n "[${d}] "
    if [ -d "${ROOT}/${d}" ]; then
        if [ -w "${ROOT}/${d}" ]; then
            echo "OK"
        else
            echo "NOT WRITABLE"
            ((failures++))
        fi
    else
        echo "MISSING — creating"
        mkdir -p "${ROOT}/${d}"
    fi
done

# ── Configs ──────────────────────────────────
sep
echo -n "[configs/] "
if [ -d "${ROOT}/configs" ] && [ "$(ls -A "${ROOT}/configs" 2>/dev/null)" ]; then
    echo "OK"
else
    echo "EMPTY OR MISSING"
    ((failures++))
fi

# ── Security defaults ────────────────────────
sep
echo -n "[remote URL ingestion] "
if [ "${ENABLE_REMOTE_URL_INGESTION:-0}" = "1" ]; then
    echo "ENABLED ⚠"
else
    echo "DISABLED ✓"
fi

echo -n "[CSRF token secret] "
if [ -n "${CSRF_TOKEN_SECRET:-}" ] && [ "${#CSRF_TOKEN_SECRET}" -ge 32 ]; then
    echo "CONFIGURED"
else
    echo "MISSING — generate with: python3 -c 'import secrets; print(secrets.token_hex(32))'"
    ((failures++))
fi

echo -n "[identity override] "
if [ "${APP_ENV}" = "production" ]; then
    if [ "${ALLOW_DEV_IDENTITY_OVERRIDE:-0}" = "1" ]; then
        echo "ENABLED ⚠ (should be 0 in production)"
    else
        echo "DISABLED ✓"
    fi
else
    echo "enabled (non-production)"
fi

# ── .env check ───────────────────────────────
sep
echo -n "[.env file] "
if [ -f "${ROOT}/.env" ]; then
    echo "EXISTS"
    echo -n "[.env contains DEEPSEEK_API_KEY] "
    if grep -q '^DEEPSEEK_API_KEY=' "${ROOT}/.env" 2>/dev/null; then
        echo "YES (value hidden)"
    else
        echo "NO"
    fi
else
    echo "MISSING — copy from .env.example and fill in secrets"
    ((failures++))
fi

# ── Result ───────────────────────────────────
sep
echo ""
if [ "${failures}" -eq 0 ]; then
    echo "✓ ALL CHECKS PASSED"
    exit 0
else
    echo "✗ ${failures} check(s) failed"
    exit 1
fi
