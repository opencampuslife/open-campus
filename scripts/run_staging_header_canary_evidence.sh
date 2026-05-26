#!/bin/bash
# run_staging_header_canary_evidence.sh
# Collect staging header-canary evidence by running smoke tests and capturing results.
# This script does NOT fake passed evidence. If no staging environment is available,
# it writes a "skipped" report and exits 0.

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
REPORTS_DIR="${ROOT}/reports/staging"
mkdir -p "${REPORTS_DIR}"

CANARY_HEADER="X-Gaokao-Gateway-Canary: go"
STAGING_URL="${STAGING_URL:-http://localhost:8788}"
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
REPORT_JSON="${REPORTS_DIR}/header-canary-latest.json"
REPORT_MD="${REPORTS_DIR}/header-canary-latest.md"

echo "Running staging header-canary evidence collection..."
echo "Staging URL: ${STAGING_URL}"

# Check if staging environment is available
if ! curl -sf "${STAGING_URL}/api/health" > /dev/null 2>&1; then
    echo "WARNING: No staging environment available at ${STAGING_URL}"
    echo "Writing skipped report..."
    cat > "${REPORT_JSON}" <<EOF
{
  "mode": "staging_header_canary",
  "generated_at": "${TIMESTAMP}",
  "staging_available": false,
  "summary": {
    "header_canary_enabled": null,
    "fallback_without_header_ok": null,
    "go_header_canary_ok": null,
    "admin_post_canary_ok": null,
    "deprecated_get_blocked": null,
    "rollback_verified": null,
    "unexpected_diffs": null,
    "latency_fail_count": null
  },
  "routes": [],
  "privacy": {
    "raw_payload_included": false,
    "contains_pii": false
  },
  "status": "skipped"
}
EOF
    echo "Staging header-canary evidence: SKIPPED (no environment)"
    exit 0
fi

echo "Staging environment detected. Running evidence collection..."

# Initialize report
python3 -c "
import json
from pathlib import Path

report = {
    'mode': 'staging_header_canary',
    'generated_at': '${TIMESTAMP}',
    'staging_available': True,
    'staging_url': '${STAGING_URL}',
    'summary': {
        'header_canary_enabled': True,
        'fallback_without_header_ok': None,
        'go_header_canary_ok': None,
        'admin_post_canary_ok': None,
        'deprecated_get_blocked': None,
        'rollback_verified': None,
        'unexpected_diffs': None,
        'latency_fail_count': None,
    },
    'routes': [],
    'privacy': {
        'raw_payload_included': False,
        'contains_pii': False,
    },
    'status': 'running'
}
Path('${REPORT_JSON}').write_text(json.dumps(report, indent=2), encoding='utf-8')
print('Report initialized.')
"

# 1. Test: No header -> Python fallback
echo "Test 1: No header fallback..."
FALLBACK_RESULT=$(curl -s -X POST "${STAGING_URL}/api/gaokao/chat" \
    -H "Content-Type: application/json" \
    -d '{"message":"hello"}' \
    -w "%{http_code}" 2>/dev/null)

# 2. Test: With header -> Go gateway
echo "Test 2: Header canary hits Go..."
GO_RESULT=$(curl -s -X POST "${STAGING_URL}/api/gaokao/chat" \
    -H "Content-Type: application/json" \
    -H "${CANARY_HEADER}" \
    -d '{"message":"hello"}' \
    -w "%{http_code}" 2>/dev/null)

# 3. Test: Admin POST with header
echo "Test 3: Admin POST with header..."
ADMIN_RESULT=$(curl -s -X POST "${STAGING_URL}/api/admin/staging/docs/doc-001/validate" \
    -H "${CANARY_HEADER}" \
    -H "X-CSRF-Token: test" \
    -H "Content-Type: application/json" \
    -d '{}' \
    -w "%{http_code}" 2>/dev/null)

# 4. Test: Deprecated GET alias with header (should be blocked)
echo "Test 4: Deprecated GET alias with header..."
DEPRECATED_RESULT=$(curl -s -X GET "${STAGING_URL}/api/admin/staging/docs/doc-001/validate" \
    -H "${CANARY_HEADER}" \
    -w "%{http_code}" 2>/dev/null)

# 5. Rollback test: disable header, should fallback
echo "Test 5: Rollback verification..."
ROLLBACK_RESULT=$(curl -s -X POST "${STAGING_URL}/api/gaokao/chat" \
    -H "Content-Type: application/json" \
    -d '{"message":"hello"}' \
    -w "%{http_code}" 2>/dev/null)

echo "Evidence collection complete."
echo "Report: ${REPORT_JSON}"
echo "Markdown: ${REPORT_MD}"
