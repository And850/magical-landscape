#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
mkdir -p .runtime
if [ ! -x .venv/bin/python ]; then
  echo 'Run scripts/setup.sh first.' >&2
  exit 1
fi
.venv/bin/python -m uvicorn backend.api:create_app --factory --host 127.0.0.1 --port 8000 &
backend_pid=$!
trap 'kill "$backend_pid" 2>/dev/null || true' EXIT INT TERM
npm run dev
