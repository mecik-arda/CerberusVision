#!/usr/bin/env bash
set -euo pipefail

if ! grep -qi microsoft /proc/sys/kernel/osrelease; then
  echo "This setup script must run inside WSL2." >&2
  exit 1
fi

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
UV_VERSION="${UV_VERSION:-0.11.28}"
UV_BIN="${UV_BIN:-$HOME/.local/bin/uv}"

if [[ ! -x "$UV_BIN" ]]; then
  echo "Installing uv $UV_VERSION into $HOME/.local/bin..."
  installer="$(mktemp)"
  trap 'rm -f "$installer"' EXIT
  curl -LsSf "https://astral.sh/uv/${UV_VERSION}/install.sh" -o "$installer"
  UV_INSTALL_DIR="$HOME/.local/bin" sh "$installer"
fi

echo "Installing managed Python 3.12..."
"$UV_BIN" python install 3.12

echo "Creating project environment..."
if [[ ! -x "$ROOT/.venv/bin/python" ]]; then
  "$UV_BIN" venv --python 3.12 "$ROOT/.venv"
else
  python_minor="$($ROOT/.venv/bin/python -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
  if [[ "$python_minor" != "3.12" ]]; then
    echo "Existing .venv uses Python $python_minor; expected 3.12." >&2
    echo "Remove $ROOT/.venv and run this script again." >&2
    exit 1
  fi
fi
"$UV_BIN" pip install --python "$ROOT/.venv/bin/python" -r "$ROOT/requirements-wsl.txt"

mkdir -p "$ROOT/logs" "$ROOT/uploads" "$ROOT/models"
if [[ ! -f "$ROOT/.env" ]]; then
  cp "$ROOT/.env.example" "$ROOT/.env"
fi
chmod +x "$ROOT"/scripts/wsl_*.sh

echo
echo "WSL environment ready."
echo "Python: $($ROOT/.venv/bin/python --version)"
echo "Project: $ROOT"
echo "Run tests: $ROOT/.venv/bin/python -m pytest -q"
echo "Run app:   $ROOT/scripts/wsl_run.sh"
