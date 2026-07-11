#!/usr/bin/env bash
# dev_up.sh - Start the full PlaySight docker-compose stack and initialize the DB.
#
# Usage:
#   ./scripts/dev_up.sh              # build + start + wait for API + init-db
#   ./scripts/dev_up.sh --no-build   # skip image rebuild
#
# Services: api (:8000), worker, dashboard (:3000), postgres (:5432),
# redis (:6379), minio (:9000 / console :9001).

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

TIMEOUT_SECONDS="${TIMEOUT_SECONDS:-180}"
BUILD_FLAG="--build"
if [[ "${1:-}" == "--no-build" ]]; then
    BUILD_FLAG=""
fi

echo "Starting docker-compose stack..."
# shellcheck disable=SC2086
docker compose up -d $BUILD_FLAG

HEALTH_URL="http://localhost:8000/api/v1/health/live"
echo "Waiting for the API at $HEALTH_URL ..."
deadline=$((SECONDS + TIMEOUT_SECONDS))
ready=0
while (( SECONDS < deadline )); do
    if curl -fsS --max-time 5 "$HEALTH_URL" >/dev/null 2>&1; then
        ready=1
        break
    fi
    sleep 3
done
if (( ! ready )); then
    echo "ERROR: API did not become healthy within ${TIMEOUT_SECONDS}s. Check: docker compose logs api" >&2
    exit 1
fi

# The API creates tables on startup; run init-db explicitly anyway (idempotent).
echo "Initializing the database (idempotent)..."
docker compose exec -T api playsight init-db

echo ""
echo "PlaySight stack is up:"
echo "  API        http://localhost:8000  (docs at /docs)"
echo "  Dashboard  http://localhost:3000"
echo "  MinIO      http://localhost:9001  (minioadmin / minioadmin)"
echo ""
echo "Stop with: docker compose down"
