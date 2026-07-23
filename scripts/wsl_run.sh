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
HOST="${CERBERUS_HOST:-127.0.0.1}"
case "$HOST" in
  127.0.0.1|localhost|::1) ;;
  *)
    if [[ -z "${CERBERUS_API_KEY:-}" ]]; then
      echo "CERBERUS_API_KEY is required when listening on a non-loopback host." >&2
      exit 1
    fi
    ;;
esac
exec "$ROOT/.venv/bin/uvicorn" app.main:app \
  --host "$HOST" \
  --port "${CERBERUS_PORT:-8000}"
