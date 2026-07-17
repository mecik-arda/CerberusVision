#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PORT="${CERBERUS_SMOKE_PORT:-18000}"
REQUIRE_READY=false
PDF_PATH=""
while (( $# > 0 )); do
  case "$1" in
    --require-ready)
      REQUIRE_READY=true
      shift
      ;;
    --pdf)
      if (( $# < 2 )); then
        echo "--pdf requires a file path." >&2
        exit 2
      fi
      PDF_PATH="$2"
      shift 2
      ;;
    *)
      echo "Unknown argument: $1" >&2
      exit 2
      ;;
  esac
done

TMP_DIR="$(mktemp -d)"
SERVER_PID=""
cleanup() {
  if [[ -n "$SERVER_PID" ]]; then
    kill "$SERVER_PID" 2>/dev/null || true
    wait "$SERVER_PID" 2>/dev/null || true
  fi
  rm -rf "$TMP_DIR"
}
trap cleanup EXIT

CERBERUS_PORT="$PORT" "$ROOT/scripts/wsl_run.sh" >"$TMP_DIR/server.log" 2>&1 &
SERVER_PID=$!

root_status="000"
for _ in {1..30}; do
  root_status="$(
    curl -sS -o "$TMP_DIR/index.html" -w '%{http_code}' \
      "http://127.0.0.1:$PORT/" 2>/dev/null || true
  )"
  [[ "$root_status" == "200" ]] && break
  sleep 1
done

if [[ "$root_status" != "200" ]]; then
  echo "API root check failed (HTTP $root_status)." >&2
  cat "$TMP_DIR/server.log" >&2
  exit 1
fi

health_status="$(
  curl -sS -o "$TMP_DIR/health.json" -w '%{http_code}' \
    "http://127.0.0.1:$PORT/health"
)"

echo "root_status=$root_status"
echo "health_status=$health_status"
cat "$TMP_DIR/health.json"
echo

if [[ "$REQUIRE_READY" == true && "$health_status" != "200" ]]; then
  echo "Readiness check failed; inspect the health report above." >&2
  exit 1
fi
if [[ "$health_status" != "200" && "$health_status" != "503" ]]; then
  echo "Unexpected health status: $health_status" >&2
  exit 1
fi

if [[ -n "$PDF_PATH" ]]; then
  if [[ ! -f "$PDF_PATH" ]]; then
    echo "PDF not found: $PDF_PATH" >&2
    exit 1
  fi
  pipeline_status="$(
    curl -sS -o "$TMP_DIR/pipeline.sse" -w '%{http_code}' \
      -F "file=@$PDF_PATH;type=application/pdf" \
      "http://127.0.0.1:$PORT/api/upload-and-stream"
  )"
  echo "pipeline_status=$pipeline_status"
  pipeline_events="$(
    grep -oE '"status": "[A-Z_]+"' "$TMP_DIR/pipeline.sse" \
      | sed -E 's/"status": "([A-Z_]+)"/\1/' \
      | paste -sd ',' - || true
  )"
  echo "pipeline_events=$pipeline_events"

  if [[ "$pipeline_status" != "200" ]]; then
    cat "$TMP_DIR/pipeline.sse" >&2
    exit 1
  fi
  if grep -q '"status": "ERROR"' "$TMP_DIR/pipeline.sse"; then
    cat "$TMP_DIR/pipeline.sse" >&2
    exit 1
  fi
  if ! grep -Eq '"status": "(DRAFT|COMPLETED)"' "$TMP_DIR/pipeline.sse"; then
    cat "$TMP_DIR/pipeline.sse" >&2
    echo "Pipeline did not emit a final document status." >&2
    exit 1
  fi
fi
