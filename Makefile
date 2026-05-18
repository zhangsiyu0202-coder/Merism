# Merism dev convenience targets.
#
# `make` alone prints the list; prefer these over remembering each command.

.PHONY: help setup up down migrate superuser seed dev api web worker beat \
        test test-backend test-frontend lint lint-backend lint-frontend \
        typecheck build clean

help:  ## Show this help
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

# ── Environment ────────────────────────────────────────────

setup:  ## Full bootstrap — docker + uv sync + migrate + seed + smoke
	./bin/setup-dev.sh

up:  ## Start postgres + redis + minio
	docker compose up -d --wait

down:  ## Stop all services
	docker compose down

migrate:  ## Apply Django migrations (needs `make up`)
	DJANGO_SETTINGS_MODULE=merism.settings.dev .venv/bin/python manage.py migrate

superuser:  ## Ensure the dev superuser exists (admin@merism.test / merism-dev)
	DJANGO_SETTINGS_MODULE=merism.settings.dev .venv/bin/python manage.py ensure_superuser

seed:  ## Seed the demo org + team + 3 studies
	DJANGO_SETTINGS_MODULE=merism.settings.dev .venv/bin/python manage.py seed_demo

# ── Runtime ────────────────────────────────────────────────

api:  ## Run the Django dev server on :8000
	bash bin/clear-dev-ports.sh 8000 5173
	DJANGO_SETTINGS_MODULE=merism.settings.dev .venv/bin/python manage.py runserver 8000

web:  ## Run the Vite frontend dev server on :5173
	bash bin/clear-dev-ports.sh 8000 5173
	cd frontend && pnpm dev

worker:  ## Run one Celery worker
	DJANGO_SETTINGS_MODULE=merism.settings.dev .venv/bin/celery -A merism worker -l info

beat:  ## Run Celery beat scheduler
	DJANGO_SETTINGS_MODULE=merism.settings.dev .venv/bin/celery -A merism beat -l info --scheduler redbeat.RedBeatScheduler

# ── Test ──────────────────────────────────────────────────

test: test-backend test-frontend  ## Run all tests
test-e2e:  ## Run frontend Playwright E2E against Django + Vite
	cd frontend && pnpm test:e2e

test-backend:  ## Run backend pytest
	.venv/bin/pytest

test-frontend:  ## Run frontend vitest
	cd frontend && pnpm test

# ── Lint / typecheck ──────────────────────────────────────

lint: lint-backend lint-frontend  ## Run all linters

lint-backend:
	.venv/bin/ruff check . --fix && .venv/bin/ruff format .

lint-frontend:
	cd frontend && pnpm lint && pnpm format

typecheck:  ## Frontend tsc + backend pyright
	cd frontend && pnpm typecheck
	.venv/bin/pyright merism

# ── Build ─────────────────────────────────────────────────

build:  ## Build the frontend for production
	cd frontend && pnpm build

codegen:  ## Regenerate frontend API types from the Django OpenAPI schema
	mkdir -p frontend/src/generated
	DJANGO_SETTINGS_MODULE=merism.settings.test .venv/bin/python manage.py spectacular \
		--format openapi-json --file frontend/src/generated/openapi.json
	cd frontend && pnpm codegen

clean:  ## Remove build artefacts + caches
	rm -rf frontend/dist frontend/storybook-static
	find . -name __pycache__ -type d -not -path './.venv/*' -exec rm -rf {} +
	find . -name '*.pyc' -delete
