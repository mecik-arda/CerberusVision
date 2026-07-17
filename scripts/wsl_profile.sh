#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$ROOT/.env"

if [[ ! -f "$ENV_FILE" ]]; then
  cp "$ROOT/.env.example" "$ENV_FILE"
fi

set_env() {
  local name="$1"
  local value="$2"
  if grep -q "^${name}=" "$ENV_FILE"; then
    sed -i "s#^${name}=.*#${name}=${value}#" "$ENV_FILE"
  else
    printf '%s=%s\n' "$name" "$value" >>"$ENV_FILE"
  fi
}

case "${1:-show}" in
  gpu)
    set_env QWEN_MODEL_PATH "$ROOT/models/Qwen-2.5-7B-Instruct-INT4"
    set_env OPENVINO_DEVICE GPU
    ;;
  quality|14b)
    set_env QWEN_MODEL_PATH "$ROOT/models/Qwen-2.5-14B-Instruct-INT4"
    set_env OPENVINO_DEVICE CPU
    ;;
  show)
    ;;
  *)
    echo "Usage: $0 [gpu|quality|show]" >&2
    exit 2
    ;;
esac

grep -E '^(QWEN_MODEL_PATH|OPENVINO_DEVICE)=' "$ENV_FILE"
