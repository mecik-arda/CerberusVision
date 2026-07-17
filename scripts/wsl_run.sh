#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ ! -x "$ROOT/.venv/bin/uvicorn" ]]; then
  echo "WSL environment is missing. Run scripts/wsl_setup.sh first." >&2
  exit 1
fi

if [[ -f "$ROOT/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT/.env"
  set +a
fi

cd "$ROOT"
exec "$ROOT/.venv/bin/uvicorn" app.main:app \
  --host "${CERBERUS_HOST:-0.0.0.0}" \
  --port "${CERBERUS_PORT:-8000}"
