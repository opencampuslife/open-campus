#!/usr/bin/env bash
set -eu

ROOT="${ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"

echo "collect-legacy-usage: scanning structured logs for legacy_admin_get_mutation_used" >&2

LEGACY_LOG_DIR="${LEGACY_LOG_DIR:-${ROOT}/data/audit_logs}"
EVENT_COUNT=0

if [ -d "${LEGACY_LOG_DIR}" ]; then
  EVENT_COUNT=$(grep -rl '"event".*"legacy_admin_get_mutation_used"' "${LEGACY_LOG_DIR}" 2>/dev/null | wc -l | tr -d ' ') || EVENT_COUNT=0
fi

echo "collect-legacy-usage: ${EVENT_COUNT} legacy GET usage event(s)" >&2

cat <<EOF
{
  "event_type": "legacy_admin_get_mutation_used",
  "count": ${EVENT_COUNT},
  "source": "structured_log",
  "notes": "count of structured-log files containing legacy GET usage events"
}
EOF
