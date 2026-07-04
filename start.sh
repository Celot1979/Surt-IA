#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"

fuser -k 8000/tcp 2>/dev/null || true
find "$ROOT/backend" -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

cd "$ROOT/backend"
[ ! -d venv ] && python3 -m venv venv
venv/bin/pip install -r requirements.txt --quiet 2>/dev/null || venv/bin/pip install -r requirements.txt

PORT="${PORT:-8000}"
exec venv/bin/uvicorn main:app --host 0.0.0.0 --port "$PORT" --reload
