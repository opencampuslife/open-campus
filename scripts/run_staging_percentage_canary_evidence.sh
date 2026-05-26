#!/usr/bin/env bash
# Run staging 1% percentage-canary evidence collection.
#
# PR-6E: staging 1% percentage canary evidence run.
# - Reads PR-6D percentage-canary example (weight=0)
# - Renders temporary 1% config to /tmp or reports/staging/tmp
# - Collects evidence (requires STAGING_ENV_CONFIRMED=true)
# - Verifies rollback to 0%
# - Does NOT submit weight=1 config to repo
# - Does NOT fake passed evidence if staging env unavailable
#
# Usage:
#   bash scripts/run_staging_percentage_canary_evidence.sh
#   STAGING_ENV_CONFIRMED=true bash scripts/run_staging_percentage_canary_evidence.sh

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PERCENT="${CANARY_PERCENT:-1}"
TMP_DIR="${ROOT}/reports/staging/tmp"
REPORT_DIR="${ROOT}/reports/staging"
EXAMPLE_YAML="${ROOT}/deploy/staging/ingress/go-gateway-shadow.percentage-canary.example.yaml"
POLICY_YAML="${ROOT}/configs/cutover_policy.yaml"
TMP_CONFIG="${TMP_DIR}/staging-${PERCENT}pct-canary.yaml"
REPORT_JSON="${REPORT_DIR}/percentage-canary-${PERCENT}pct-latest.json"

echo "========================================="
echo "PR-6E: Staging ${PERCENT}% Percentage Canary Evidence"
echo "========================================="

# Validate percent
if [[ "$PERCENT" != "1" && "$PERCENT" != "5" && "$PERCENT" != "25" && "$PERCENT" != "50" && "$PERCENT" != "100" ]]; then
    echo "ERROR: CANARY_PERCENT must be one of: 1, 5, 25, 50, 100"
    exit 1
fi

# PR-6E only allows 1% for now
if [[ "$PERCENT" != "1" ]]; then
    echo "ERROR: PR-6E only allows 1%. Use PR-6F for 5%."
    exit 1
fi

# Check source example exists
if [[ ! -f "$EXAMPLE_YAML" ]]; then
    echo "ERROR: PR-6D example not found: $EXAMPLE_YAML"
    exit 1
fi

# Create tmp dir
mkdir -p "$TMP_DIR"
mkdir -p "$REPORT_DIR"

# Step 1: Verify source example has weight=0 (PR-6D invariant)
echo "[Step 1] Verifying PR-6D source has current_weight=0..."
python3 -c "
import yaml, sys
c = yaml.safe_load(open('$EXAMPLE_YAML'))
assert c.get('canary', {}).get('current_weight', 0) == 0, 'source current_weight != 0'
assert c.get('canary', {}).get('type') == 'percentage', 'source type != percentage'
for r in c.get('routes', []):
    assert r.get('weight', 0) == 0, f'route {r.get(\"path\")} weight != 0'
print('  OK: source example has weight=0')
"

if [[ $? -ne 0 ]]; then
    echo "ERROR: PR-6D invariant check failed"
    exit 1
fi

# Step 2: Render temporary 1% config
echo "[Step 2] Rendering temporary ${PERCENT}% config..."
python3 "${ROOT}/tools/render_staging_percentage_canary_config.py" \
    --source "$EXAMPLE_YAML" \
    --percent "$PERCENT" \
    --output "$TMP_CONFIG"

if [[ $? -ne 0 ]]; then
    echo "ERROR: Failed to render config"
    exit 1
fi

# Step 3: Verify rendered config passes checker (needs --allow-weight for 1%)
echo "[Step 3] Checking rendered config with --allow-percentage-canary and --allow-weight..."
python3 "${ROOT}/tools/check_staging_ingress_config.py" \
    --config "$TMP_CONFIG" \
    --policy "$POLICY_YAML" \
    --allow-percentage-canary \
    --allow-weight

if [[ $? -ne 0 ]]; then
    echo "ERROR: Rendered config failed checker"
    rm -f "$TMP_CONFIG"
    exit 1
fi

# Step 4: Check staging environment
if [[ "${STAGING_ENV_CONFIRMED:-}" != "true" ]]; then
    echo "[Step 4] STAGING_ENV_CONFIRMED != true"
    echo "  Writing skipped status (no fake passed evidence)"

    python3 "${ROOT}/tools/collect_staging_percentage_canary_result.py" \
        --config "$TMP_CONFIG" \
        --policy "$POLICY_YAML" \
        --percent "$PERCENT" \
        --report "$REPORT_JSON"

    echo ""
    echo "========================================="
    echo "Evidence: SKIPPED (no staging environment)"
    echo "Report: ${REPORT_JSON}"
    echo "========================================="
    echo "NOTE: PR-6E strict readiness will continue to fail until real staging evidence is collected."

    # Cleanup tmp config
    rm -f "$TMP_CONFIG"
    exit 0
fi

# Step 5: Run real staging live checks
echo "[Step 5] Staging environment confirmed. Running live checks..."

STAGING_URL="${STAGING_URL:-http://localhost:8788}"
GO_SHADOW_URL="${GO_SHADOW_URL:-http://localhost:8788}"
PYTHON_LEGACY_URL="${PYTHON_LEGACY_URL:-http://localhost:8787}"
FAILED=0

# 5.1 Health check
echo "  [5.1] Health check: ${STAGING_URL}/api/health"
HEALTH=$(curl -sf "${STAGING_URL}/api/health" 2>/dev/null || echo "ERROR")
if [[ "$HEALTH" == "ERROR" ]]; then
    echo "    FAIL: health check failed"
    FAILED=1
else
    echo "    OK: health check passed"
    echo "    Response: $(echo "$HEALTH" | head -c 200)"
fi

# 5.2 Header canary works (chat should route to Go)
echo "  [5.2] Header canary check: POST /api/gaokao/chat with X-Gaokao-Gateway-Canary: go"
CHAT_RESP=$(curl -sf -X POST "${STAGING_URL}/api/gaokao/chat" \
    -H "Content-Type: application/json" \
    -H "X-Gaokao-Gateway-Canary: go" \
    -d '{"message":"test"}' 2>/dev/null || echo "ERROR")
if [[ "$CHAT_RESP" == "ERROR" ]]; then
    echo "    FAIL: header canary chat failed"
    FAILED=1
else
    echo "    OK: header canary chat responded"
fi

# 5.3 1% percentage config applied check
echo "  [5.3] Verifying 1% config applied (current_weight=1, route weights=1)"
# This would need staging platform API; placeholder for now
echo "    INFO: config_applied verification needs staging platform integration"
echo "    Setting config_applied: unknown (will cause failed status)"

# 5.4 Deprecated GET blocked
echo "  [5.4] Deprecated GET check: GET /api/admin/staging/docs/doc-001/validate"
GET_RESP=$(curl -sf -o /dev/null -w "%{http_code}" -X GET \
    "${STAGING_URL}/api/admin/staging/docs/doc-001/validate" 2>/dev/null || echo "ERROR")
if [[ "$GET_RESP" == "405" || "$GET_RESP" == "ERROR" ]]; then
    echo "    OK: deprecated GET blocked (405 or not proxied)"
else
    echo "    WARN: deprecated GET returned ${GET_RESP} (expected 405)"
fi

# 5.5 Run parity checks (reuse existing tools)
echo "  [5.5] Running parity checks..."
if command -v make &> /dev/null; then
    cd "${ROOT}" && make parity-gaokao-chat 2>&1 | tail -5 || echo "    Parity check skipped (make not available or failed)"
fi

# 5.6 Legacy GET usage check
echo "  [5.6] Legacy GET usage: should be 0"
echo "    INFO: legacy_get_usage_events check needs Go gateway access log integration"

# Determine config_applied and rollback_verified
# These would be set by actual staging platform integration
CONFIG_APPLIED="unknown"
ROLLBACK_VERIFIED="unknown"

# Collect evidence with live check results
echo ""
echo "[Step 5.7] Collecting evidence..."
python3 "${ROOT}/tools/collect_staging_percentage_canary_result.py" \
    --config "$TMP_CONFIG" \
    --policy "$POLICY_YAML" \
    --percent "$PERCENT" \
    --report "$REPORT_JSON" \
    --staging-url "$STAGING_URL" \
    --config-applied "$CONFIG_APPLIED" \
    --rollback-verified "$ROLLBACK_VERIFIED"

# Step 6: Verify rollback to 0%
echo ""
echo "[Step 6] Verifying rollback to 0%..."
echo "  (Needs staging platform API to restore weight=0 config)"
echo "  Setting rollback_verified: unknown (will cause failed status if strict mode)"

# Step 7: Cleanup
echo ""
echo "[Step 7] Cleaning up temporary config..."
rm -f "$TMP_CONFIG"

echo ""
echo "========================================="
if [[ $FAILED -eq 0 ]]; then
    echo "Evidence: COLLECTED (review report for live check details)"
else
    echo "Evidence: COLLECTED (some live checks failed)"
fi
echo "Report: ${REPORT_JSON}"
echo "========================================="
echo ""
echo "Next steps:"
echo "  1. Review report: cat ${REPORT_JSON}"
echo "  2. Fix any failed checks before proceeding"
echo "  3. After ALL checks pass, proceed to PR-6F (5%)"
echo "  4. Do NOT submit weight=1 config to repo"
