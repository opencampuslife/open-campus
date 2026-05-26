#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/../../.." && pwd)"

if command -v psql >/dev/null 2>&1; then
  exec psql "$@"
fi

if "${SCRIPT_DIR}/compose.sh" ps >/dev/null 2>&1; then
  exec "${SCRIPT_DIR}/compose.sh" exec -T postgres psql "$@"
fi

echo "psql is not available on the host and no docker compose runtime was found." >&2
exit 1
