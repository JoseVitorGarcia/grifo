.PHONY: setup up down logs run dev test pull build ps

up:         ## Sobe a aplicacao inteira em container -> http://localhost:8000
	docker compose up -d

build:      ## Reconstroi a imagem da aplicacao
	docker compose build app

down:       ## Derruba os containers (os modelos ficam no volume)
	docker compose down

ps:         ## Estado dos containers
	docker compose ps -a

logs:       ## Acompanha os logs (use S=ollama para filtrar um servico)
	docker compose logs -f $${S:-}

pull:       ## Baixa/atualiza o modelo configurado
	docker compose exec ollama ollama pull $${OLLAMA_MODELO:-gemma3:4b}

setup:      ## Prepara o ambiente local (Ollama + modelo + venv) para desenvolver
	./setup.sh

dev:        ## Ollama em container, app no venv com recarga automatica
	docker compose up -d ollama && ./iniciar.sh --reload

run:        ## App no venv, sem recarga
	./iniciar.sh

test:       ## Roda a suite de testes
	./.venv/bin/python -m pytest
