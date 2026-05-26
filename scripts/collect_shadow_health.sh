#!/usr/bin/env bash
set -euo pipefail

SHADOW_URL="${SHADOW_URL:-http://localhost:8788}"
OUTPUT="${1:-/dev/stdout}"

echo "collect-shadow-health: probing ${SHADOW_URL}/api/health" >&2

if command -v curl &>/dev/null; then
  if curl -sf "${SHADOW_URL}/api/health" > "${OUTPUT}" 2>/dev/null; then
    echo "collect-shadow-health: OK" >&2
    python3 -c "import json; print(json.dumps(json.load(open('${OUTPUT}')), indent=2))" >&2
    exit 0
  else
    echo "collect-shadow-health: FAIL" >&2
    exit 1
  fi
else
  if python3 -c "
import urllib.request, json, sys
try:
    resp = urllib.request.urlopen('${SHADOW_URL}/api/health', timeout=5)
    data = json.loads(resp.read())
    with open('${OUTPUT}', 'w') as f:
        json.dump(data, f)
    print('collect-shadow-health: OK', file=sys.stderr)
    json.dump(data, sys.stderr, indent=2)
except Exception as e:
    print(f'collect-shadow-health: FAIL ({e})', file=sys.stderr)
    sys.exit(1)
"; then
    exit 0
  else
    exit 1
  fi
fi
