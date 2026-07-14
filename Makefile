.PHONY: help install install-evals install-observability lint typecheck test api-dev web-dev infra-up infra-down

help:
	@echo "AegisOps commands"
	@echo "  make install     Install workspace dependencies"
	@echo "  make install-evals Install optional eval dependencies"
	@echo "  make install-observability Install optional observability dependencies"
	@echo "  make web-dev     Start the visual command center"
	@echo "  make api-dev     Start the API service after implementation"
	@echo "  make infra-up    Start local Postgres, Redis, and OPA"
	@echo "  make infra-down  Stop local infrastructure"
	@echo "  make lint        Run linters"
	@echo "  make typecheck   Run type checks"
	@echo "  make test        Run tests"

install:
	pnpm install
	python3 -m venv services/api/.venv
	services/api/.venv/bin/python -m pip install --upgrade pip
	services/api/.venv/bin/python -m pip install -e "services/api[dev]"

install-evals:
	services/api/.venv/bin/python -m pip install -e "services/api[evals]"

install-observability:
	services/api/.venv/bin/python -m pip install -e "services/api[observability]"

web-dev:
	pnpm dev:web

api-dev:
	cd services/api && .venv/bin/uvicorn aegisops_api.main:app --reload

infra-up:
	docker compose -f infra/docker-compose.yml up -d

infra-down:
	docker compose -f infra/docker-compose.yml down

lint:
	pnpm lint
	cd services/api && .venv/bin/ruff check .

typecheck:
	pnpm typecheck
	cd services/api && .venv/bin/mypy .

test:
	pnpm test
	cd services/api && .venv/bin/pytest
