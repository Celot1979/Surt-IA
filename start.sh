#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
FRONTEND_DIR="$ROOT/frontend"
BACKEND_DIR="$ROOT/backend"

echo "╔══════════════════════════════════════╗"
echo "║    Surt IA - Pipeline de Auditoría  ║"
echo "╚══════════════════════════════════════╝"

cd "$FRONTEND_DIR"

if [ ! -d "node_modules" ]; then
    echo "[*] Instalando dependencias del frontend..."
    npm install --silent
fi

echo "[*] Construyendo frontend..."
npm run build --silent

cd "$BACKEND_DIR"

if [ ! -d "venv" ]; then
    echo "[*] Creando virtualenv e instalando dependencias..."
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt --quiet
else
    source venv/bin/activate
fi

echo ""
echo "[*] Servidor listo en http://localhost:8000"
echo ""

exec uvicorn main:app --host 0.0.0.0 --port 8000 --reload
