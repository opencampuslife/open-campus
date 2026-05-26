#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
BACKUP_DIR="${ROOT}/data/backups"
TIMESTAMP="$(date -u +%Y%m%d_%H%M%S)"
BACKUP_NAME="${TIMESTAMP}"
PYTHON="python3"
COMPONENTS=()

mkdir -p "${BACKUP_DIR}"

echo "=== Gaokao Agent Backup ==="
echo "Timestamp: ${TIMESTAMP}"
echo "Backup dir: ${BACKUP_DIR}/${BACKUP_NAME}"
echo ""

mkdir -p "${BACKUP_DIR}/${BACKUP_NAME}"

# ── Git commit ──────────────────────────
GIT_COMMIT="unknown"
if command -v git &>/dev/null && git -C "${ROOT}" rev-parse --short HEAD &>/dev/null; then
    GIT_COMMIT="$(git -C "${ROOT}" rev-parse --short HEAD)"
    echo "[git] commit: ${GIT_COMMIT}"
else
    echo "[git] no git available — skipping"
fi

# ── PostgreSQL dump ──────────────────────
DB_URL="${DATABASE_URL_ADMIN:-}"
if [ -n "${DB_URL}" ]; then
    echo "[postgres] dumping..."
    PGPASSWORD=$(echo "${DB_URL}" | sed -n 's/.*:\/\/[^:]*:\([^@]*\)@.*/\1/p')
    export PGPASSWORD

    if command -v pg_dump &>/dev/null; then
        pg_dump "${DB_URL}" \
            --format=plain \
            --file="${BACKUP_DIR}/${BACKUP_NAME}/postgres.sql" \
            --no-owner --no-acl \
            2>/dev/null && echo "[postgres] dumped to postgres.sql" && COMPONENTS+=("postgres_dump") || echo "[postgres] pg_dump FAILED"
    else
        echo "[postgres] pg_dump not found — using Python fallback"
        "${PYTHON}" -c "
import psycopg2, json
conn = psycopg2.connect('${DB_URL}')
cur = conn.cursor()
tables = ['knowledge_documents', 'knowledge_chunks', 'ingestion_runs', 'graph_runs']
dump = {}
for t in tables:
    try:
        cur.execute(f'SELECT * FROM {t}')
        cols = [d[0] for d in cur.description]
        rows = [dict(zip(cols, row)) for row in cur.fetchall()]
        dump[t] = rows
    except Exception:
        pass
cur.close()
conn.close()
with open('${BACKUP_DIR}/${BACKUP_NAME}/postgres_fallback.json', 'w') as f:
    json.dump(dump, f, default=str, indent=2)
" 2>/dev/null && echo "[postgres] fallback saved to postgres_fallback.json" && COMPONENTS+=("postgres_dump") || echo "[postgres] backup FAILED"
    fi
else
    echo "[postgres] DATABASE_URL_ADMIN not set — skipping"
fi

# ── File data ────────────────────────────
FILE_DIR_NAMES=(knowledge_vault crm staging graph_runs audit published)
FILE_DIR_PATHS=(
    "${ROOT}/knowledge_vault"
    "${ROOT}/data/crm"
    "${ROOT}/data/staging"
    "${ROOT}/data/graph-runs"
    "${ROOT}/data/audit"
    "${ROOT}/data/published"
)

for i in "${!FILE_DIR_NAMES[@]}"; do
    comp="${FILE_DIR_NAMES[$i]}"
    src="${FILE_DIR_PATHS[$i]}"
    dst="${BACKUP_DIR}/${BACKUP_NAME}/$(echo "${comp}" | tr '/' '_')"
    if [ -d "${src}" ]; then
        echo "[${comp}] copying..."
        cp -r "${src}" "${dst}" 2>/dev/null || true
        echo "[${comp}] done"
        COMPONENTS+=("${comp}")
    else
        echo "[${comp}] not found — skipping"
    fi
done

# ── .env.example (never backup real .env) ─
if [ -f "${ROOT}/.env.example" ]; then
    cp "${ROOT}/.env.example" "${BACKUP_DIR}/${BACKUP_NAME}/.env.example"
    echo "[.env.example] copied (real .env NOT included)"
    COMPONENTS+=("env_example")
fi

# ── Generate manifest.json ───────────────
MANIFEST="${BACKUP_DIR}/${BACKUP_NAME}/manifest.json"
echo "[manifest] generating..."

"${PYTHON}" -c "
import json, hashlib, os, datetime

backup_name = '${BACKUP_DIR}/${BACKUP_NAME}'
components = ${COMPONENTS[@]+$(printf '%s\n' "${COMPONENTS[@]}" | "${PYTHON}" -c "import sys,json; print(json.dumps([l.strip() for l in sys.stdin.readlines()]))")}
components = components if isinstance(components, list) else []

checksums = {}
for root, dirs, files in os.walk(backup_name):
    for fname in sorted(files):
        fpath = os.path.join(root, fname)
        rel = os.path.relpath(fpath, backup_name)
        if rel == 'manifest.json':
            continue
        h = hashlib.sha256()
        with open(fpath, 'rb') as f:
            while chunk := f.read(65536):
                h.update(chunk)
        checksums[rel] = 'sha256:' + h.hexdigest()

manifest = {
    'created_at': datetime.datetime.utcnow().isoformat() + 'Z',
    'backup_name': os.path.basename(backup_name),
    'git_commit': '${GIT_COMMIT}',
    'app_version': '0.3.0',
    'components': sorted(components),
    'checksums': checksums,
    'format_version': 1,
}

with open(os.path.join(backup_name, 'manifest.json'), 'w') as f:
    json.dump(manifest, f, indent=2, ensure_ascii=False)
print('[manifest] written with ' + str(len(checksums)) + ' checksums')
" 2>/dev/null || echo "[manifest] generation FAILED"

# ── Package ──────────────────────────────
ARCHIVE="${BACKUP_DIR}/backup_${BACKUP_NAME}.tar.gz"
tar -czf "${ARCHIVE}" -C "${BACKUP_DIR}" "${BACKUP_NAME}" 2>/dev/null
echo ""
echo "Backup complete: ${ARCHIVE}"
echo "  Size: $(du -sh "${ARCHIVE}" | cut -f1)"
echo "  Components: ${COMPONENTS[*]}"
echo ""
echo "Verify with: bash scripts/restore.sh ${ARCHIVE} --dry-run"
echo "           make check-backup BACKUP_FILE=${ARCHIVE}"
