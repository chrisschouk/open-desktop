#!/usr/bin/env bash
# One-command bootstrap for OpenDesktop + OpenWorker local dev
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "==> OpenDesktop bootstrap"

if ! command -v docker >/dev/null 2>&1; then
  echo "ERROR: Docker is required. Install Docker Desktop or docker-ce first."
  exit 1
fi

if [ ! -f .env ]; then
  echo "==> Creating .env from .env.example"
  cp .env.example .env
  echo "    Edit .env and add CHAT_API_KEY / VISION_API_KEY before chatting."
fi

echo "==> Building sandbox image (opendesktop-sandbox:latest)"
docker build -t opendesktop-sandbox:latest -f sandbox-engine/Dockerfile.sandbox sandbox-engine/

echo "==> Installing Python dependencies"
python3 -m pip install -q -r server/requirements.txt
python3 -m pip install -q -e ".[dev]" 2>/dev/null || python3 -m pip install -q -e .

mkdir -p data data/vault

echo ""
echo "Bootstrap complete."
echo ""
echo "Start the API server:"
echo "  uvicorn server.main:app --host 0.0.0.0 --port 8000 --reload"
echo ""
echo "Start the web client (another terminal):"
echo "  cd client && python3 -m http.server 8888"
echo ""
echo "Or use the CLI:"
echo "  openworker chat \"What can you do?\""
