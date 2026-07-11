#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if ! command -v python3.11 >/dev/null 2>&1; then
  echo "Error: python3.11 is required but was not found in PATH." >&2
  exit 1
fi

if ! command -v node >/dev/null 2>&1; then
  echo "Error: node is required but was not found in PATH." >&2
  exit 1
fi

if [[ ! -d .venv ]]; then
  echo "Creating Python virtual environment in .venv"
  python3.11 -m venv .venv
else
  echo "Using existing Python virtual environment in .venv"
fi

# shellcheck disable=SC1091
source .venv/bin/activate

python -m pip install --upgrade pip
pip install -r backend/requirements.txt -r backend/requirements-dev.txt

if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "Created .env from .env.example"
else
  echo ".env already exists; leaving it unchanged"
fi

(
  cd dashboard
  npm install
)

echo
echo "Development environment is ready. Next steps:"
echo "  1. Start supporting services: docker compose up -d postgres redis minio"
echo "  2. Apply database migrations: alembic -c backend/alembic.ini upgrade head"
echo "  3. Run the API: uvicorn backend.main:app --reload"
echo "  4. Run the dashboard: cd dashboard && npm run dev"
