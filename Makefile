.DEFAULT_GOAL := help
COMPOSE = docker compose --env-file .env -f infrastructure/compose.yaml

.PHONY: help setup install dev-api dev-web check check-api check-web contracts contracts-check db-up up down compose-check migrate migration-check db-current runtime-setup test-db seed-demo e2e
help:
	@echo "setup install dev-api dev-web check test-db migrate runtime-setup db-current migration-check contracts contracts-check db-up up down compose-check e2e"
setup:
	python3 scripts/setup_local.py
install:
	uv sync --locked --all-packages --all-groups
	npm ci
dev-api:
	uv run --locked --package orqentra-api uvicorn orqentra.main:app --host 127.0.0.1 --port 8000 --reload --no-access-log
dev-web:
	npm run dev
check-api:
	uv run --locked --package orqentra-api ruff check apps/api scripts
	uv run --locked --package orqentra-api ruff format --check apps/api scripts
	uv run --locked --package orqentra-api mypy --config-file apps/api/pyproject.toml apps/api/src
	uv run --locked --package orqentra-api pytest -c apps/api/pyproject.toml apps/api/tests
check-web:
	node --test infrastructure/web_security.test.mjs
	npm run lint
	npm run typecheck
	npm test
	npm run build
check: check-api check-web contracts-check
contracts:
	uv run --locked --package orqentra-api python scripts/export_openapi.py
	npm run contracts:generate
contracts-check:
	uv run --locked --package orqentra-api python scripts/check_contracts.py
compose-check:
	$(COMPOSE) config --quiet
db-up:
	$(COMPOSE) up -d --wait postgres
up:
	$(COMPOSE) build postgres
	$(COMPOSE) build api
	$(COMPOSE) build web
	$(COMPOSE) up --no-build -d --wait
down:
	$(COMPOSE) down
migrate:
	uv run --locked --package orqentra-api python scripts/migrate_database.py --local upgrade
migration-check:
	uv run --locked --package orqentra-api python scripts/migrate_database.py --local check
db-current:
	uv run --locked --package orqentra-api python scripts/migrate_database.py --local current
runtime-setup:
	uv run --locked --package orqentra-api python scripts/provision_runtime.py
test-db:
	uv run --locked --package orqentra-api python scripts/test_database.py
seed-demo:
	python3 scripts/seed_demo.py
e2e:
	npm run test:e2e

.PHONY: ai-up
ai-up:
	$(COMPOSE) build postgres
	$(COMPOSE) build api
	$(COMPOSE) build web
	$(COMPOSE) --profile ai up --no-build -d --wait
