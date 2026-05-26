#!/usr/bin/env bash
set -euo pipefail

ROOT="${ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
REPORT_DIR="${ROOT}/reports/shadow"
SHADOW_PORT="${SHADOW_PORT:-8788}"
SHADOW_URL="${SHADOW_URL:-http://localhost:${SHADOW_PORT}}"
PYTHON_URL="${PYTHON_URL:-http://localhost:8787}"
SHADOW_PROXY_ENABLED="${SHADOW_PROXY_ENABLED:-false}"
SHADOW_PROXY_ROUTES="${SHADOW_PROXY_ROUTES:-${ADMIN_PROXY_ROUTES:-}}"
COMPOSE_FILE="${ROOT}/docker-compose.shadow.yml"
PY="${PY:-python3}"
GO="${GO:-go}"

if [ -n "${COMPOSE_CMD:-}" ]; then
  read -r -a COMPOSE_ARGS <<< "${COMPOSE_CMD}"
elif command -v docker-compose &>/dev/null; then
  COMPOSE_ARGS=(docker-compose)
else
  COMPOSE_ARGS=(docker compose)
fi

echo "=== shadow dry-run ==="
echo "  root: ${ROOT}"
echo "  shadow port: ${SHADOW_PORT}"
echo "  python upstream: ${PYTHON_URL}"
echo "  shadow proxy enabled: ${SHADOW_PROXY_ENABLED}"
echo "  shadow proxy routes: ${SHADOW_PROXY_ROUTES:-<none>}"
echo "  report dir: ${REPORT_DIR}"
echo ""

mkdir -p "${REPORT_DIR}"

step_info() {
  echo "--- step: $1 ---"
}

fail() {
  echo "FATAL: $1" >&2
  exit 1
}

warn() {
  echo "WARN: $1" >&2
}

# ── Step 0: pre-flight ──────────────────────────────────────
step_info "pre-flight"

if ! "${COMPOSE_ARGS[@]}" version &>/dev/null; then
  fail "${COMPOSE_ARGS[*]} not available"
fi

if ! "${PY}" -c "import requests" 2>/dev/null && ! command -v curl &>/dev/null; then
  fail "need python3 requests or curl"
fi

if ! curl -sf "${PYTHON_URL}/api/health" > /dev/null 2>&1; then
  warn "python gateway not reachable at ${PYTHON_URL} — live parity will be skipped"
  PYTHON_AVAILABLE=false
else
  echo "  python gateway: reachable"
  PYTHON_AVAILABLE=true
fi

# ── Step 1: start shadow gateway ─────────────────────────────
step_info "start shadow gateway"

docker stop gaokao-agent-go-shadow 2>/dev/null || true

SHADOW_PROXY_ROUTES="${SHADOW_PROXY_ROUTES}" \
SHADOW_PROXY_ENABLED="${SHADOW_PROXY_ENABLED}" \
SHADOW_PORT="${SHADOW_PORT}" \
PYTHON_GATEWAY_BASE_URL="${PYTHON_GATEWAY_BASE_URL:-http://host.docker.internal:8787}" \
"${COMPOSE_ARGS[@]}" -f "${COMPOSE_FILE}" up -d --build

# ── Step 2: health check ─────────────────────────────────────
step_info "health check"

for i in $(seq 1 30); do
  if curl -sf "${SHADOW_URL}/api/health" > "${REPORT_DIR}/health.json" 2>/dev/null; then
    echo "  health: OK after ${i}s"
    break
  fi
  if [ $i -eq 30 ]; then
    fail "shadow gateway health check failed after 30s"
  fi
  sleep 1
done

"${PY}" -c "
import json
d = json.load(open('${REPORT_DIR}/health.json'))
assert d['status'] == 'ok', f'status={d[\"status\"]}'
assert d['route_count'] == 115, f'route_count={d[\"route_count\"]}'
print(f'  route_count={d[\"route_count\"]} legacy_gap_count={d[\"legacy_gap_count\"]} deprecated_alias_count={d[\"deprecated_compatibility_alias_count\"]}')
"

# ── Step 3: route inventory ─────────────────────────────────
step_info "route inventory"

if "${PY}" "${ROOT}/tools/check_route_contract.py" --root "${ROOT}" --inventory 2>/dev/null | "${PY}" -c "
import sys, json
lines = sys.stdin.read().strip().split('\n')
inv = {}
for line in lines:
    if ':' in line:
        k, v = line.split(':', 1)
        inv[k.strip()] = v.strip()
json.dump(inv, open('${REPORT_DIR}/inventory.json', 'w'))
"; then
  echo "  inventory: collected"
else
  warn "inventory collection failed, continuing"
fi

# ── Step 4: legacy usage summary ─────────────────────────────
step_info "legacy usage summary"

bash "${ROOT}/scripts/collect_legacy_usage_summary.sh" > "${REPORT_DIR}/legacy_usage.json" 2>&1 || true
echo "  legacy usage: collected"

# ── Step 5: live parity ──────────────────────────────────────
step_info "live parity"

PARITY_PASS="true"
PARITY_RAN="false"
CHAT_PARITY_ENABLED=false
ADMIN_PARITY_ENABLED=false

if [ "${SHADOW_PROXY_ENABLED}" = "true" ]; then
  case ",${SHADOW_PROXY_ROUTES}," in
    *"POST /api/gaokao/chat"*) CHAT_PARITY_ENABLED=true ;;
  esac
  case ",${SHADOW_PROXY_ROUTES}," in
    *"POST /api/admin/ingestion/runs/{run_id}/cancel"*|*"POST /api/admin/staging/docs/{doc_id}/"*) ADMIN_PARITY_ENABLED=true ;;
  esac
fi

if [ "${PYTHON_AVAILABLE}" = "true" ]; then
  if [ "${CHAT_PARITY_ENABLED}" = "true" ]; then
    PARITY_RAN="true"
    echo "  running chat parity..."
    cd "${ROOT}/control-plane" && \
    GO_SHADOW_BASE_URL="${SHADOW_URL}" \
    PYTHON_LEGACY_BASE_URL="${PYTHON_URL}" \
    PARITY_FIXTURE_PATH="${ROOT}/tests/parity/gaokao_chat.yaml" \
    "${GO}" test ./tests -run TestParityGaokaoChatLive -count=1 -json > "${REPORT_DIR}/chat_parity.jsonl" 2>/dev/null || {
      warn "chat parity had failures (see ${REPORT_DIR}/chat_parity.jsonl)"
      PARITY_PASS="false"
    }
    echo "  chat parity: done"
  else
    echo "  chat parity: skipped (POST /api/gaokao/chat not explicitly enabled)"
    echo '{"status":"skipped","reason":"proxy route not enabled","passed":0,"failed":0,"skipped":0,"latency_warns":0}' > "${REPORT_DIR}/chat_parity.jsonl"
  fi

  if [ "${ADMIN_PARITY_ENABLED}" = "true" ]; then
    PARITY_RAN="true"
    echo "  running admin parity..."
    cd "${ROOT}/control-plane" && \
    GO_SHADOW_BASE_URL="${SHADOW_URL}" \
    PYTHON_LEGACY_BASE_URL="${PYTHON_URL}" \
    "${GO}" test ./tests -run TestParityAdminPostLive -count=1 -json > "${REPORT_DIR}/admin_parity.jsonl" 2>/dev/null || {
      warn "admin parity had failures (see ${REPORT_DIR}/admin_parity.jsonl)"
      PARITY_PASS="false"
    }
    echo "  admin parity: done"
  else
    echo "  admin parity: skipped (admin POST routes not explicitly enabled)"
    echo '{"status":"skipped","reason":"admin proxy routes not enabled","passed":0,"failed":0,"skipped":0,"latency_warns":0}' > "${REPORT_DIR}/admin_parity.jsonl"
  fi
else
  echo "  parity: skipped (python upstream not available)"
  echo '{"status":"skipped","passed":0,"failed":0,"skipped":0,"latency_warns":0}' > "${REPORT_DIR}/chat_parity.jsonl"
  echo '{"status":"skipped","passed":0,"failed":0,"skipped":0,"latency_warns":0}' > "${REPORT_DIR}/admin_parity.jsonl"
fi

# ── Step 6: generate report ──────────────────────────────────
step_info "generate report"

"${PY}" "${ROOT}/tools/shadow_dry_run_report.py" --root "${ROOT}"

echo ""
if [ "${PARITY_PASS}" = "true" ] && [ "${PYTHON_AVAILABLE}" = "true" ] && [ "${PARITY_RAN}" = "true" ]; then
  echo "=== shadow dry-run: PASS ==="
else
  echo "=== shadow dry-run: DONE (warnings noted) ==="
fi
