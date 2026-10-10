#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
mkdir -p .runtime
if ! command -v uv >/dev/null 2>&1; then
  python3 -m pip install --target .runtime/uv uv
  uv_bin="$PWD/.runtime/uv/bin/uv"
else
  uv_bin=$(command -v uv)
fi
export UV_CACHE_DIR="$PWD/.runtime/uv-cache"
export UV_PYTHON_INSTALL_DIR="$PWD/.runtime/python"
"$uv_bin" venv --python 3.11 .venv
"$uv_bin" pip install --python .venv/bin/python -r requirements.lock
npm ci --cache .runtime/npm-cache
export HF_HUB_DISABLE_XET=1
export HF_HUB_DOWNLOAD_TIMEOUT=60
export HF_HUB_ETAG_TIMEOUT=60
.venv/bin/python scripts/download_models.py
