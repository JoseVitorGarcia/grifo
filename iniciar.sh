#!/usr/bin/env bash
# Sobe a aplicacao web (backend FastAPI + front estatico).
set -euo pipefail

PORTA="${PORTA:-8000}"
cd "$(dirname "$0")"

if [ ! -d .venv ]; then
  echo "Ambiente Python nao encontrado. Rode ./setup.sh primeiro." >&2
  exit 1
fi

echo "Aplicacao em http://localhost:${PORTA}"
exec ./.venv/bin/python -m uvicorn servidor.api:app --host 127.0.0.1 --port "${PORTA}" "$@"
