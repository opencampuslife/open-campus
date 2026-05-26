#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
PYTHON="python3"

usage() {
    echo "Usage: $0 <backup_archive.tar.gz> [--dry-run] [--force]"
    echo "  Restores a Gaokao Agent backup to the current environment."
    echo "  Requires DATABASE_URL_ADMIN for PostgreSQL restore."
    echo ""
    echo "  --dry-run   Validate archive without restoring"
    echo "  --force     Allow overwriting existing data"
    exit 1
}

if [ $# -lt 1 ]; then
    usage
fi

ARCHIVE="$1"
DRY_RUN=false
FORCE=false
shift
while [ $# -gt 0 ]; do
    case "$1" in
        --dry-run) DRY_RUN=true ;;
        --force) FORCE=true ;;
        *) echo "Unknown option: $1"; usage ;;
    esac
    shift
done

if [ ! -f "${ARCHIVE}" ]; then
    echo "ERROR: backup file not found: ${ARCHIVE}"
    exit 1
fi

# ── Validate archive ─────────────────────
echo "=== Gaokao Agent Restore ==="
echo "Source: ${ARCHIVE}"
echo "Dry run: ${DRY_RUN}"
echo "Force: ${FORCE}"
echo ""

RESTORE_DIR="/tmp/gaokao_restore_$$"
mkdir -p "${RESTORE_DIR}"

if ! tar -xzf "${ARCHIVE}" -C "${RESTORE_DIR}" 2>/dev/null; then
    echo "ERROR: invalid or corrupt archive"
    rm -rf "${RESTORE_DIR}"
    exit 1
fi

BACKUP_NAME="$(ls "${RESTORE_DIR}" | head -1)"
SRC="${RESTORE_DIR}/${BACKUP_NAME}"

if [ ! -d "${SRC}" ]; then
    echo "ERROR: archive does not contain expected backup directory"
    rm -rf "${RESTORE_DIR}"
    exit 1
fi

# ── Validate manifest ────────────────────
MANIFEST="${SRC}/manifest.json"
if [ ! -f "${MANIFEST}" ]; then
    echo "ERROR: manifest.json not found in backup"
    rm -rf "${RESTORE_DIR}"
    exit 1
fi

echo "[manifest] found"

# Validate manifest structure
"${PYTHON}" -c "
import json, sys
with open('${MANIFEST}') as f:
    m = json.load(f)
required = ['created_at', 'components', 'checksums', 'format_version']
for key in required:
    if key not in m:
        print(f'ERROR: manifest missing required field: {key}')
        sys.exit(1)
if not isinstance(m['components'], list):
    print('ERROR: manifest components must be a list')
    sys.exit(1)
if not isinstance(m['checksums'], dict):
    print('ERROR: manifest checksums must be a dict')
    sys.exit(1)
print(f'  created_at: {m[\"created_at\"]}')
print(f'  git_commit: {m.get(\"git_commit\", \"unknown\")}')
print(f'  format_version: {m[\"format_version\"]}')
print(f'  components ({len(m[\"components\"])}): {\", \".join(m[\"components\"])}')
print(f'  checksums: {len(m[\"checksums\"])} files')
" || { rm -rf "${RESTORE_DIR}"; exit 1; }

# ── Validate required components ─────────
REQUIRED_COMPONENTS=("postgres_dump" "knowledge_vault" "env_example")
for comp in "${REQUIRED_COMPONENTS[@]}"; do
    if ! "${PYTHON}" -c "
import json
with open('${MANIFEST}') as f:
    m = json.load(f)
components = m.get('components', [])
sys = __import__('sys')
if '${comp}' not in components:
    print(f'ERROR: required component \"${comp}\" missing from manifest')
    sys.exit(1)
" 2>/dev/null; then
        echo "WARNING: required component '${comp}' not in manifest"
    fi
done

# ── Validate checksums ───────────────────
echo ""
echo "[checksum] verifying..."

CHECKSUM_FAILED=false
"${PYTHON}" -c "
import json, hashlib, sys, os

with open('${MANIFEST}') as f:
    manifest = json.load(f)

failed = []
for rel_path, expected in manifest.get('checksums', {}).items():
    fpath = os.path.join('${SRC}', rel_path)
    if not os.path.isfile(fpath):
        print(f'  MISSING: {rel_path}')
        failed.append(rel_path)
        continue
    algo, _, expected_hash = expected.partition(':')
    h = hashlib.sha256() if algo == 'sha256' else hashlib.sha256()
    with open(fpath, 'rb') as f:
        while chunk := f.read(65536):
            h.update(chunk)
    actual = algo + ':' + h.hexdigest()
    if actual != expected:
        print(f'  MISMATCH: {rel_path}')
        failed.append(rel_path)

if failed:
    print(f'\nERROR: {len(failed)} checksum(s) failed')
    sys.exit(1)
print(f'  All {len(manifest.get(\"checksums\", {}))} checksums verified')
" || CHECKSUM_FAILED=true

if [ "${CHECKSUM_FAILED}" = true ]; then
    rm -rf "${RESTORE_DIR}"
    exit 1
fi

# ── Dry run ──────────────────────────────
if [ "${DRY_RUN}" = true ]; then
    echo ""
    echo "[dry-run] archive validated successfully"
    echo "[dry-run] would restore:"
    find "${SRC}" -type f | sort | while read -r f; do
        echo "  ${f#${SRC}/}"
    done
    echo ""
    echo "Dry-run PASS — archive is valid"
    rm -rf "${RESTORE_DIR}"
    exit 0
fi

# ── Warn about overwrite ─────────────────
if [ "${FORCE}" != true ]; then
    echo ""
    echo "WARNING: This will overwrite existing data."
    echo "  Database tables will be dropped and recreated."
    echo "  File data (knowledge_vault, CRM, staging, etc.) will be replaced."
    echo ""
    echo "To proceed, use --force or set FORCE=true"
    rm -rf "${RESTORE_DIR}"
    exit 1
fi

# ── PostgreSQL restore ───────────────────
DB_URL="${DATABASE_URL_ADMIN:-}"
if [ -n "${DB_URL}" ]; then
    if [ -f "${SRC}/postgres.sql" ]; then
        echo "[postgres] restoring from SQL dump..."
        PGPASSWORD=$(echo "${DB_URL}" | sed -n 's/.*:\/\/[^:]*:\([^@]*\)@.*/\1/p')
        export PGPASSWORD
        if command -v psql &>/dev/null; then
            psql "${DB_URL}" -f "${SRC}/postgres.sql" 2>&1 | head -5
            echo "[postgres] restored"
        else
            echo "[postgres] psql not available — manual restore required: ${SRC}/postgres.sql"
        fi
    elif [ -f "${SRC}/postgres_fallback.json" ]; then
        echo "[postgres] manual restore from JSON not implemented — re-run: make migrate-db-policy sync-db-index"
    else
        echo "[postgres] no dump found in backup — skipping"
    fi
else
    echo "[postgres] DATABASE_URL_ADMIN not set — skipping DB restore"
fi

# ── File data restore ────────────────────
RESTORE_NAMES=(knowledge_vault crm staging graph_runs audit published)
RESTORE_PATHS=(
    "knowledge_vault"
    "data/crm"
    "data/staging"
    "data/graph-runs"
    "data/audit"
    "data/published"
)

for i in "${!RESTORE_NAMES[@]}"; do
    comp="${RESTORE_NAMES[$i]}"
    dest_rel="${RESTORE_PATHS[$i]}"
    src_dir="${SRC}/${comp}"
    dest_dir="${ROOT}/${dest_rel}"

    if [ -d "${src_dir}" ]; then
        echo "[${comp}] restoring to ${dest_rel}..."
        mkdir -p "${dest_dir}"
        cp -r "${src_dir}/"* "${dest_dir}/" 2>/dev/null || true
        echo "[${comp}] done"
    else
        echo "[${comp}] not in backup — skipping"
    fi
done

rm -rf "${RESTORE_DIR}"

echo ""
echo "Restore complete."
echo ""
echo "Post-restore checklist:"
echo "  1. bash scripts/check_runtime.sh"
echo "  2. make sync-db-index"
echo "  3. make test-db-policy-live"
echo "  4. make release-check"
