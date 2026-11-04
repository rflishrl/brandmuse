.PHONY: help install dev dev-api dev-web lint typecheck test build api-generate migrate docker-up docker-down eval-retrieval eval-quantization smoke-test

SHELL := /bin/bash

help:
	@echo "BrandMuse Development Commands:"
	@echo "  make install        Install backend (uv) and frontend (bun) dependencies"
	@echo "  make dev-api        Run FastAPI backend dev server"
	@echo "  make dev-web        Run React/Vite frontend dev server"
	@echo "  make lint           Lint both backend (ruff) and frontend"
	@echo "  make typecheck      Run typecheckers (mypy on api, tsc on web)"
	@echo "  make test           Run backend tests with pytest"
	@echo "  make build          Build production artifacts"
	@echo "  make api-generate   Export OpenAPI schema and generate Orval client"
	@echo "  make migrate        Apply database migrations with Alembic"
	@echo "  make docker-up      Start PostgreSQL and services via docker compose"
	@echo "  make docker-down    Stop docker compose services"

install:
	cd apps/api && uv sync
	cd apps/web && bun install --frozen-lockfile

dev-api:
	cd apps/api && uv run uvicorn app.main:app --reload --port 8000

dev-web:
	cd apps/web && bun run dev

lint:
	cd apps/api && uv run ruff check .
	cd apps/api && uv run ruff format --check .

typecheck:
	cd apps/api && uv run mypy app
	cd apps/web && bun run typecheck

test:
	cd apps/api && uv run pytest

build:
	cd apps/web && bun run build

api-generate:
	cd apps/api && uv run python -m app.scripts.export_openapi
	cd apps/web && bun run api:generate

migrate:
	cd apps/api && uv run alembic upgrade head

eval-retrieval:
	cd apps/api && uv run python ../../eval/retrieval.py

eval-quantization:
	cd apps/api && uv run python ../../eval/quantization.py

smoke-test:
	bash scripts/smoke-test.sh $${BASE_URL:-http://localhost:8000}

docker-up:
	docker compose up -d

docker-down:
	docker compose down
