#!/usr/bin/env bash
# Sobe o Ollama em container e baixa o modelo. Idempotente: pode rodar de novo.
set -euo pipefail

MODELO="${OLLAMA_MODELO:-gemma3:4b}"
URL="${OLLAMA_URL:-http://localhost:11434}"

echo "==> Subindo o container do Ollama"
docker compose up -d

echo "==> Aguardando a API responder em ${URL}"
for _ in $(seq 1 60); do
  if curl -sf "${URL}/api/tags" >/dev/null 2>&1; then
    echo "    API no ar."
    break
  fi
  sleep 2
done

if ! curl -sf "${URL}/api/tags" >/dev/null 2>&1; then
  echo "!! O Ollama nao respondeu. Veja os logs com: docker compose logs ollama" >&2
  exit 1
fi

if docker compose exec -T ollama ollama list | awk 'NR>1 {print $1}' | grep -qx "${MODELO}"; then
  echo "==> Modelo ${MODELO} ja esta baixado."
else
  echo "==> Baixando o modelo ${MODELO} (alguns GB, so na primeira vez)"
  docker compose exec -T ollama ollama pull "${MODELO}"
fi

echo "==> Ambiente Python"
if [ ! -d .venv ]; then
  python3 -m venv .venv
fi
./.venv/bin/pip install -q --upgrade pip
./.venv/bin/pip install -q -r requirements-dev.txt

echo
echo "Tudo pronto. Duas formas de rodar:"
echo "  docker compose up -d    # tudo em container  -> http://localhost:8000"
echo "  ./iniciar.sh --reload   # app no venv, recarregando ao editar o codigo"
