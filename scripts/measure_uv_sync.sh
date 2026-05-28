#!/usr/bin/env bash
# Measure uv sync blast radius: cold/warm timing, package count, .venv size.
# Usage: bash scripts/measure_uv_sync.sh [--output reports/uv_sync_blast_radius.json]

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUTPUT="${1:-$ROOT/reports/uv_sync_blast_radius.json}"
OUTPUT_DIR="$(dirname "$OUTPUT")"
mkdir -p "$OUTPUT_DIR"
export PATH="$HOME/.local/bin:$PATH"

cold_start() {
    echo "=== COLD SYNC ==="
    # Remove any existing .venv to force cold install
    rm -rf "$ROOT/.venv"
    local start end elapsed
    start=$(date +%s.%N)
    uv sync --all-packages --frozen 2>&1 | tail -1
    end=$(date +%s.%N)
    elapsed=$(echo "$end - $start" | bc)
    echo "$elapsed"
}

warm_sync() {
    echo "=== WARM SYNC ==="
    local start end elapsed
    start=$(date +%s.%N)
    uv sync --all-packages --frozen 2>&1 | tail -1
    end=$(date +%s.%N)
    elapsed=$(echo "$end - $start" | bc)
    echo "$elapsed"
}

measure_venv() {
    local venv="$ROOT/.venv"
    if [ ! -d "$venv" ]; then
        echo '{"size_bytes": 0, "size_human": "0B", "file_count": 0, "lib_size_bytes": 0, "lib_size_human": "0B"}'
        return
    fi
    local size_bytes file_count lib_size_bytes
    size_bytes=$(du -sb "$venv" 2>/dev/null | awk '{print $1}')
    file_count=$(find "$venv" -type f 2>/dev/null | wc -l | tr -d ' ')
    local lib_dir
    lib_dir=$(find "$venv/lib" -maxdepth 1 -type d -name "python*" 2>/dev/null | head -1)
    if [ -n "$lib_dir" ]; then
        lib_size_bytes=$(du -sb "$lib_dir/site-packages" 2>/dev/null | awk '{print $1}')
    else
        lib_size_bytes=0
    fi
    local size_human lib_size_human
    size_human=$(du -sh "$venv" 2>/dev/null | awk '{print $1}')
    lib_size_human=$(du -sh "$lib_dir/site-packages" 2>/dev/null | awk '{print $1}' || echo "0B")
    echo "{\"size_bytes\": $size_bytes, \"size_human\": \"$size_human\", \"file_count\": $file_count, \"lib_size_bytes\": $lib_size_bytes, \"lib_size_human\": \"$lib_size_human\"}"
}

count_packages() {
    local venv="$ROOT/.venv"
    if [ ! -d "$venv" ]; then
        echo 0
        return
    fi
    local pip_cmd="$venv/bin/pip"
    if [ ! -f "$pip_cmd" ]; then
        pip_cmd=$(find "$venv" -name "pip" -type f 2>/dev/null | head -1)
    fi
    if [ -n "$pip_cmd" ] && [ -x "$pip_cmd" ]; then
        "$pip_cmd" list --format=json 2>/dev/null | python3 -c "import json,sys; print(len(json.load(sys.stdin)))" 2>/dev/null || echo "error"
    else
        python3 -c "
import sys
sys.path.insert(0, '$venv/lib/python3.11/site-packages')
import pkg_resources
print(len(list(pkg_resources.working_set)))
" 2>/dev/null || echo "error"
    fi
}

top_heaviest_packages() {
    local venv="$ROOT/.venv"
    local lib_dir
    lib_dir=$(find "$venv/lib" -maxdepth 1 -type d -name "python*" 2>/dev/null | head -1)
    if [ -z "$lib_dir" ]; then
        echo "[]"
        return
    fi
    python3 -c "
import json, os, sys
site_pkg = os.path.expanduser('$lib_dir/site-packages')
if not os.path.isdir(site_pkg):
    print('[]')
    sys.exit(0)
entries = []
for d in os.listdir(site_pkg):
    dpath = os.path.join(site_pkg, d)
    if not os.path.isdir(dpath) or d in ('__pycache__', 'pip', 'pip-*', '_distutils_hack'):
        continue
    if d.endswith('.dist-info') or d.endswith('.egg-info'):
        continue
    try:
        size = sum(os.path.getsize(os.path.join(r, f)) for r, _, fs in os.walk(dpath) for f in fs)
        entries.append((d, size))
    except (OSError, PermissionError):
        pass
entries.sort(key=lambda x: -x[1])
print(json.dumps([{'package': e[0], 'size_bytes': e[1], 'size_mb': round(e[1]/1024/1024, 2)} for e in entries[:15]]))
" 2>/dev/null || echo '[]'
}

service_scope_sync() {
    # Simulate service-scoped sync time by measuring uv sync for a specific package
    local pkg="$1"
    local start end elapsed
    start=$(date +%s.%N)
    uv sync --package "$pkg" --frozen 2>&1 | tail -1
    end=$(date +%s.%N)
    elapsed=$(echo "$end - $start" | bc)
    echo "$elapsed"
}

measure_service_venv() {
    local pkg="$1"
    local venv="$ROOT/.venv"
    if [ ! -d "$venv" ]; then
        echo '{"size_bytes": 0, "size_human": "0B"}'
        return
    fi
    local lib_dir
    lib_dir=$(find "$venv/lib" -maxdepth 1 -type d -name "python*" 2>/dev/null | head -1)
    if [ -z "$lib_dir" ]; then
        echo '{"size_bytes": 0, "size_human": "0B"}'
        return
    fi
    python3 -c "
import json, subprocess, sys
result = subprocess.run(
    ['uv', 'tree', '--package', '$pkg', '--depth', '99'],
    capture_output=True, text=True, cwd='$ROOT'
)
lines = result.stdout.strip().split('\n')
# Count packages (non-empty, non-indented lines minus first line)
pkgs = [l.strip() for l in lines if l.strip() and not l.strip().startswith('metacampus-')]
pkg_count = len([l for l in pkgs if l])
print(json.dumps({'total_tree_lines': len(lines), 'package_count': pkg_count}))
" 2>/dev/null || echo '{"error": true, "total_tree_lines": 0, "package_count": 0}'
}

# ---- Main ----
cd "$ROOT"

echo "=== uv version ==="
uv --version

# 1. Cold sync measurement
echo ""
echo "=== [1/5] Cold sync ==="
COLD_TIME=$(cold_start)
echo "Cold sync: ${COLD_TIME}s"

# 2. Measure .venv after cold sync
VENV_COLD=$(measure_venv)
PKG_COUNT_COLD=$(count_packages)
echo "Cold .venv: $VENV_COLD"
echo "Cold package count: $PKG_COUNT_COLD"
TOP_HEAVY=$(top_heaviest_packages)
echo "Top heaviest packages: $TOP_HEAVY"

# 3. Warm sync measurement
echo ""
echo "=== [2/5] Warm sync ==="
WARM_TIME=$(warm_sync)
echo "Warm sync: ${WARM_TIME}s"

# 4. Per-service scoped sync
echo ""
echo "=== [3/5] Service-scoped sync ==="
SERVICES=(
    "metacampus-api-gateway"
    "metacampus-agent-orchestrator"
    "metacampus-auth-service"
    "metacampus-crm-service"
    "metacampus-db-policy-service"
    "metacampus-evaluation-service"
    "metacampus-knowledge-graph-service"
    "metacampus-knowledge-service"
    "metacampus-llm-gateway"
    "metacampus-mealbot-service"
    "metacampus-permission-service"
    "metacampus-rag-service"
    "metacampus-recommendation-service"
    "metacampus-source-ingestion-service"
    "metacampus-wecom-adapter"
    "metacampus-workflow-service"
)
SERVICE_TIMES="["
SERVICE_DEPS="["
FIRST=true
for svc in "${SERVICES[@]}"; do
    dep_info=$(measure_service_venv "$svc")
    if [ "$FIRST" = true ]; then
        FIRST=false
    else
        SERVICE_TIMES+=","
        SERVICE_DEPS+=","
    fi
    SERVICE_TIMES+="{\"package\": \"$svc\", \"dependency_tree\": $dep_info}"
    SERVICE_DEPS+="{\"package\": \"$svc\", \"dependency_tree\": $dep_info}"
done
SERVICE_TIMES+="]"
SERVICE_DEPS+="]"

# 5. Docling-specific deep dive
echo ""
echo "=== [4/5] Docling weight ==="
DOCLING_TREE=$(uv tree --package metacampus-source-ingestion-service --depth 99 2>/dev/null | wc -l | tr -d ' ')
DOCLING_REFERENCES=$(grep -c "docling" "$ROOT/uv.lock" 2>/dev/null || echo "0")
echo "Docling tree lines: $DOCLING_TREE"
echo "Docling lockfile references: $DOCLING_REFERENCES"
DOCLING_DIRS=$(find "$ROOT/.venv" -type d -name "docling*" 2>/dev/null | wc -l || echo "0")
DOCLING_SIZE=$(du -sh "$ROOT/.venv/lib/python3.11/site-packages/docling_slim" 2>/dev/null | awk '{print $1}' || echo "0B")
echo "Docling dirs: $DOCLING_DIRS, size: $DOCLING_SIZE"

# 6. Package count breakdown
echo ""
echo "=== [5/5] Dependency summary ==="
python3 -c "
import json
# count deps per service
services = json.loads('$SERVICE_DEPS')
for s in services:
    name = s['package']
    tree = s['dependency_tree']
    print(f\"  {name:45s} {tree.get('package_count', '?'):>4d} packages\")
"

# Build full JSON report
python3 -c "
import json
report = {
    'schema_version': 1,
    'branch': '$(git rev-parse --abbrev-ref HEAD)',
    'commit': '$(git rev-parse HEAD)',
    'uv_version': '$(uv --version 2>/dev/null | head -1)',
    'measurements': {
        'cold_sync_seconds': $COLD_TIME,
        'cold_sync_seconds_rounded': $(printf "%.1f" "$COLD_TIME"),
        'warm_sync_seconds': $WARM_TIME,
        'cold_venv': $VENV_COLD,
        'cold_package_count': $PKG_COUNT_COLD,
        'top_heaviest_packages': $TOP_HEAVY,
        'service_scoped': {
            'count': ${#SERVICES[@]},
            'dependencies': $SERVICE_DEPS
        },
        'docling': {
            'tree_lines': $DOCLING_TREE,
            'lockfile_references': $DOCLING_REFERENCES,
            'installed_dirs': $DOCLING_DIRS,
            'site_packages_size': '$DOCLING_SIZE'
        }
    },
    'metadata': {
        'python_version': '$(python3 --version 2>/dev/null)',
        'os': '$(uname -s)',
        'arch': '$(uname -m)',
        'timestamp': '$(date -u +%Y-%m-%dT%H:%M:%SZ)'
    }
}
with open('$OUTPUT', 'w') as f:
    json.dump(report, f, indent=2)
print(f'Report written to $OUTPUT')
"

echo ""
echo "=== DONE ==="
