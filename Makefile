# Merism dev convenience targets.
#
# `make` alone prints the list; prefer these over remembering each command.

.PHONY: help setup dev stop status restart doctor reset reset-hard up down \
        migrate seed-dev superuser seed api web worker beat \
        test test-backend test-frontend test-e2e \
        lint lint-backend lint-frontend typecheck build codegen clean

help:  ## Show this help
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

# ── One-shot dev workflow ──────────────────────────────────

setup:  ## First-time bootstrap (uv sync + migrations + seed + smoke)
	./bin/setup-dev.sh

dev:  ## Start full dev stack (docker + backend + frontend + doctor)
	./bin/dev.sh start

stop:  ## Stop dev stack started by `make dev`
	./bin/dev.sh stop

status:  ## Show what's running
	./bin/dev.sh status

restart:  ## Stop + start
	./bin/dev.sh restart

doctor:  ## Run dev environment self-check (18 checks)
	./bin/doctor.sh

reset:  ## Soft reset — clear stale processes, queues, containers; re-seed
	./bin/reset.sh

reset-hard:  ## DESTRUCTIVE: drop & recreate the database
	./bin/reset.sh --hard

# ── Granular targets (if you need to run one piece at a time) ──

up:  ## Start docker compose only (postgres + redis + minio + celery)
	docker compose up -d --wait

down:  ## Stop docker compose
	docker compose down

migrate:  ## Apply Django migrations
	DJANGO_SETTINGS_MODULE=merism.settings.dev .venv/bin/python manage.py migrate

seed-dev:  ## Idempotent dev seed (admin + org membership; also re-runs seed_demo)
	DJANGO_SETTINGS_MODULE=merism.settings.dev .venv/bin/python manage.py seed_dev

superuser:  ## (Legacy) Ensure dev superuser exists — prefer `make seed-dev`
	DJANGO_SETTINGS_MODULE=merism.settings.dev .venv/bin/python manage.py ensure_superuser

seed:  ## (Legacy) Seed demo org + studies — prefer `make seed-dev`
	DJANGO_SETTINGS_MODULE=merism.settings.dev .venv/bin/python manage.py seed_demo

api:  ## Run only the Django dev server on :8000
	bash bin/clear-dev-ports.sh 8000
	DJANGO_SETTINGS_MODULE=merism.settings.dev .venv/bin/python manage.py runserver 0.0.0.0:8000

web:  ## Run only the Vite frontend on :5173
	bash bin/clear-dev-ports.sh 5173
	cd frontend && pnpm dev

worker:  ## Run a local Celery worker (in addition to the docker one)
	DJANGO_SETTINGS_MODULE=merism.settings.dev .venv/bin/celery -A merism worker -l info

beat:  ## Run a local Celery beat (in addition to the docker one)
	DJANGO_SETTINGS_MODULE=merism.settings.dev .venv/bin/celery -A merism beat -l info --scheduler redbeat.RedBeatScheduler

# ── Test ──────────────────────────────────────────────────

test: test-backend test-frontend  ## Run all tests

test-backend:  ## Backend pytest
	.venv/bin/pytest

test-frontend:  ## Frontend vitest
	cd frontend && pnpm test

test-e2e:  ## Frontend Playwright E2E (needs running dev stack)
	cd frontend && pnpm test:e2e

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
