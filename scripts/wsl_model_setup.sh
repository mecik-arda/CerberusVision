#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MODEL_ID="${QWEN_MODEL_ID:-OpenVINO/Qwen2.5-7B-Instruct-int4-ov}"
MODEL_DIR="${QWEN_MODEL_PATH:-$ROOT/models/Qwen-2.5-7B-Instruct-INT4}"

if ! grep -qi microsoft /proc/sys/kernel/osrelease; then
  echo "This model setup script must run inside WSL2." >&2
  exit 1
fi
if [[ ! -x "$ROOT/.venv/bin/hf" ]]; then
  echo "WSL environment is missing or outdated. Run scripts/wsl_setup.sh first." >&2
  exit 1
fi

if [[ -f "$MODEL_DIR/openvino_model.xml" && -f "$MODEL_DIR/openvino_model.bin" ]]; then
  echo "OpenVINO model already exists: $MODEL_DIR"
  exit 0
fi

available_kib="$(df -Pk "$ROOT" | awk 'NR == 2 {print $4}')"
required_kib=$((12 * 1024 * 1024))
if (( available_kib < required_kib )); then
  echo "At least 12 GiB free space is required for the model download." >&2
  exit 1
fi

mkdir -p "$MODEL_DIR"
echo "Downloading $MODEL_ID to $MODEL_DIR ..."
"$ROOT/.venv/bin/hf" download "$MODEL_ID" --local-dir "$MODEL_DIR"

if [[ ! -f "$MODEL_DIR/openvino_model.xml" || ! -f "$MODEL_DIR/openvino_model.bin" ]]; then
  echo "Model download completed without the required OpenVINO IR files." >&2
  exit 1
fi

echo "Model ready: $MODEL_DIR ($(du -sh "$MODEL_DIR" | cut -f1))"
