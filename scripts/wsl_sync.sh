#!/usr/bin/env bash
set -euo pipefail

SOURCE="${1:-/mnt/c/Users/ardam/Desktop/Yazılım_Siber/CerberusVision}"
TARGET="${2:-$HOME/projects/CerberusVision}"

if [[ ! -d "$SOURCE" ]]; then
  echo "Source project not found: $SOURCE" >&2
  exit 1
fi

case "$TARGET" in
  "$HOME"/*) ;;
  *)
    echo "Refusing to sync outside the WSL home directory: $TARGET" >&2
    exit 1
    ;;
esac

mkdir -p "$TARGET"
rsync -a --delete \
  --exclude='.git/' \
  --exclude='.venv/' \
  --exclude='.env' \
  --exclude='.pytest_cache/' \
  --exclude='.pytest-tmp*/' \
  --exclude='__pycache__/' \
  --exclude='logs/' \
  --exclude='uploads/' \
  --exclude='models/' \
  --exclude='veriler/' \
  "$SOURCE/" "$TARGET/"

chmod +x "$TARGET"/scripts/wsl_*.sh
echo "Synced project to $TARGET"
