#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/../../.." && pwd)"
CONTAINER_NAME="gaokao-agent-postgres"
IMAGE="pgvector/pgvector:pg16"
DB_NAME="gaokao_agent_test"
DB_PORT="54329"

if command -v docker >/dev/null 2>&1; then
  if docker compose version >/dev/null 2>&1; then
    cd "${ROOT_DIR}"
    exec docker compose "$@"
  fi
fi

if command -v docker-compose >/dev/null 2>&1; then
  cd "${ROOT_DIR}"
  exec docker-compose "$@"
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "No supported container runtime found. Install Docker Desktop or provide docker-compose." >&2
  exit 1
fi

subcommand="${1:-}"
shift || true

case "${subcommand}" in
  up)
    if [[ "${1:-}" == "-d" ]]; then
      shift
    fi
    if [[ "${1:-}" == "postgres" ]]; then
      if docker ps -a --format '{{.Names}}' | grep -Fxq "${CONTAINER_NAME}"; then
        docker start "${CONTAINER_NAME}" >/dev/null
      else
        docker run -d \
          --name "${CONTAINER_NAME}" \
          -e POSTGRES_USER=postgres \
          -e POSTGRES_PASSWORD=postgres \
          -e POSTGRES_DB="${DB_NAME}" \
          -p "${DB_PORT}:5432" \
          "${IMAGE}" >/dev/null
      fi
      exit 0
    fi
    ;;
  down)
    if docker ps -a --format '{{.Names}}' | grep -Fxq "${CONTAINER_NAME}"; then
      docker rm -f "${CONTAINER_NAME}" >/dev/null
    fi
    exit 0
    ;;
  ps)
    docker ps "$@"
    exit 0
    ;;
  exec)
    if [[ "${1:-}" == "-T" ]]; then
      shift
    fi
    if [[ "${1:-}" == "postgres" ]]; then
      shift
      exec docker exec -i "${CONTAINER_NAME}" "$@"
    fi
    ;;
esac

echo "Unsupported compose fallback invocation: ${subcommand}" >&2
exit 1
