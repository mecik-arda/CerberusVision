#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if ! grep -qi microsoft /proc/sys/kernel/osrelease; then
  echo "CerberusVision must be managed inside WSL2." >&2
  exit 1
fi

case "$ROOT" in
  "$HOME"/*) ;;
  *)
    echo "Project must live inside the WSL home directory: $ROOT" >&2
    exit 1
    ;;
esac

if [[ ! -d "$ROOT/.git" ]]; then
  echo "Git metadata is missing from $ROOT." >&2
  exit 1
fi

chmod +x "$ROOT"/scripts/wsl_*.sh
echo "CerberusVision is WSL-native: $ROOT"
echo "No Windows-to-WSL synchronization is required."
