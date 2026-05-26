#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
PYTHON="python3"

echo "=== Gaokao Agent Recovery Drill ==="
echo "Root: ${ROOT}"
echo ""

DRILL_DIR="/tmp/gaokao_recovery_drill_$$"
BACKUP_FILE=""
FAILURES=0

cleanup() {
    rm -rf "${DRILL_DIR}" 2>/dev/null || true
    [ -n "${BACKUP_FILE}" ] && rm -f "${BACKUP_FILE}" 2>/dev/null || true
}
trap cleanup EXIT

# ── Step 1: Create backup ────────────────
echo "── Step 1: Create backup ──"
BACKUP_FILE=$(mktemp "/tmp/gaokao_backup_drill_XXXXXX.tar.gz")

bash "${SCRIPT_DIR}/backup.sh" 2>&1 | grep -E '(Backup complete|Size:|ERROR)' || true

ARCHIVES=$(ls -t "${ROOT}/data/backups"/backup_*.tar.gz 2>/dev/null | head -1)
if [ -z "${ARCHIVES}" ]; then
    echo "ERROR: No backup archive found"
    ((FAILURES++))
else
    cp "${ARCHIVES}" "${BACKUP_FILE}"
    echo "[backup] copied to ${BACKUP_FILE}"
    BACKUP_FILE="${BACKUP_FILE}"
fi

# ── Step 2: Dry-run validation ───────────
echo ""
echo "── Step 2: Dry-run validation ──"
if bash "${SCRIPT_DIR}/restore.sh" "${BACKUP_FILE}" --dry-run 2>&1; then
    echo "[dry-run] PASS"
else
    echo "[dry-run] FAIL"
    ((FAILURES++))
fi

# ── Step 3: Restore to temp directory ────
echo ""
echo "── Step 3: Restore file data to temp directory ──"
mkdir -p "${DRILL_DIR}"

tar -xzf "${BACKUP_FILE}" -C "${DRILL_DIR}" 2>/dev/null
BACKUP_NAME="$(ls "${DRILL_DIR}" | head -1)"
DRILL_SRC="${DRILL_DIR}/${BACKUP_NAME}"

echo "[restore] extracted to ${DRILL_SRC}"

# ── Step 4: Verify file data ─────────────
echo ""
echo "── Step 4: Verify file components ──"

check_dir() {
    local name="$1"
    local path="$2"
    echo -n "[${name}] "
    if [ -d "${path}" ]; then
        count=$(find "${path}" -type f 2>/dev/null | wc -l | tr -d ' ')
        echo "OK (${count} files)"
        return 0
    else
        echo "MISSING"
        return 1
    fi
}

check_dir "knowledge_vault" "${DRILL_SRC}/knowledge_vault" || ((FAILURES++))
check_dir "crm" "${DRILL_SRC}/crm" || true
check_dir "staging" "${DRILL_SRC}/staging" || true
check_dir "graph_runs" "${DRILL_SRC}/graph_runs" || true
check_dir "audit" "${DRILL_SRC}/audit" || true
check_dir "published" "${DRILL_SRC}/published" || true

# ── Step 5: Verify manifest ──────────────
echo ""
echo "── Step 5: Verify manifest ──"
if [ -f "${DRILL_SRC}/manifest.json" ]; then
    echo "[manifest] present"

    "${PYTHON}" -c "
import json, sys
with open('${DRILL_SRC}/manifest.json') as f:
    m = json.load(f)
checks = []
checks.append(('created_at' in m, 'has created_at'))
checks.append(len(m.get('components', [])) > 0, 'has components')
checks.append(len(m.get('checksums', {})) > 0, 'has checksums')
checks.append(m.get('format_version', 0) == 1, 'format_version is 1')
all_ok = True
for ok, name in checks:
    status = 'OK' if ok else 'FAIL'
    if not ok: all_ok = False
    print(f'  [{status}] {name}')
sys.exit(0 if all_ok else 1)
" || ((FAILURES++))

    echo -n "[.env excluded] "
    if [ ! -f "${DRILL_SRC}/.env" ]; then
        echo "OK (not present)"
    else
        echo "FAIL (.env found in backup)"
        ((FAILURES++))
    fi

    echo -n "[.env.example included] "
    if [ -f "${DRILL_SRC}/.env.example" ]; then
        echo "OK"
    else
        echo "FAIL"
        ((FAILURES++))
    fi
else
    echo "ERROR: manifest.json missing"
    ((FAILURES++))
fi

# ── Step 6: Verify audit events readable ─
echo ""
echo "── Step 6: Verify audit events ──"
if [ -d "${DRILL_SRC}/audit" ]; then
    event_count=$(find "${DRILL_SRC}/audit" -name '*.jsonl' -exec wc -l {} + 2>/dev/null | tail -1 | awk '{print $1}' || echo "0")
    echo "[audit] ${event_count} lines found"
else
    echo "[audit] no audit directory — skipping"
fi

# ── Step 7: Verify integrity ─────────────
echo ""
echo "── Step 7: Verify checksum integrity ──"
"${PYTHON}" -c "
import json, hashlib, sys, os
with open('${DRILL_SRC}/manifest.json') as f:
    m = json.load(f)
bad = 0
for rel, expected in m.get('checksums', {}).items():
    fpath = os.path.join('${DRILL_SRC}', rel)
    if not os.path.isfile(fpath):
        bad += 1
        continue
    algo, _, _ = expected.partition(':')
    h = hashlib.sha256()
    with open(fpath, 'rb') as f:
        while chunk := f.read(65536):
            h.update(chunk)
    if algo + ':' + h.hexdigest() != expected:
        bad += 1
if bad > 0:
    print(f'  FAIL: {bad} checksum(s) mismatch')
    sys.exit(1)
print(f'  All checksums match')
" || ((FAILURES++))

# ── Result ────────────────────────────────
echo ""
echo "── Result ──"
if [ "${FAILURES}" -eq 0 ]; then
    echo ""
    echo "RECOVERY DRILL PASSED"
    echo ""
    echo "Successfully validated:"
    echo "  - backup creation"
    echo "  - archive structure"
    echo "  - manifest integrity"
    echo "  - checksum verification"
    echo "  - component completeness"
    echo "  - .env exclusion"
    echo "  - .env.example inclusion"
    exit 0
else
    echo ""
    echo "RECOVERY DRILL FAILED — ${FAILURES} failure(s)"
    exit 1
fi
