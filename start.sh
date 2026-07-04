#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
echo "Surt IA - http://localhost:8000"
cd "$ROOT/backend"
[ ! -d venv ] && python3 -m venv venv && venv/bin/pip install -r requirements.txt --quiet
exec venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000
