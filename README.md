# BrandMuse

> An AI brand assistant for creative teams to converse with brand guidelines and generate on-brand campaign concepts with permanent Stable Diffusion image assets.

---

## Architectural Note: Why FastAPI Over Express.js

While the agency job posting references Express.js, BrandMuse deliberately adopts **Python FastAPI** for its backend service. Python is the native home of modern AI engineering, offering first-class libraries for LangChain LCEL runnables, RAG pipelines, Pydantic v2 structured output validation, and quantization tooling. Adopting FastAPI enables direct integration with the AI ecosystem while maintaining high-performance async throughput and automatic OpenAPI contract generation for our React frontend.

---

## Tech Stack Overview

- **Backend (`apps/api`):** Python 3.12, FastAPI, Pydantic v2, Astral `uv`, SQLAlchemy 2.0 (async), Alembic, PostgreSQL with `pgvector`, LangChain, Langfuse, SlowAPI, Tenacity, Structlog.
- **Frontend (`apps/web`):** React 18, Vite, TypeScript (strict), Bun runtime & package manager, Tailwind CSS, shadcn/ui (Radix primitives), React Router v7 (declarative mode), TanStack Query v5, Orval OpenAPI generator.
- **Infrastructure:** Docker multi-stage builds, Docker Compose (PostgreSQL pgvector), Cloudflare Pages (Frontend), Render (API Web Service), Supabase (PostgreSQL + pgvector + Storage).

---

## Quickstart & Verification (Phase 1)

### 1. Requirements
- [Bun](https://bun.sh) (v1.4+)
- [Astral uv](https://github.com/astral-sh/uv) (v0.5+)
- Docker & Docker Compose

### 2. Local Setup
```bash
# Clone and enter directory
cd C:\Projects\brandmuse

# Install all backend and frontend dependencies
make install

# Start local PostgreSQL database with pgvector
docker compose up -d db

# Apply initial database migrations
make migrate

# Start FastAPI backend
make dev-api

# In another terminal, start React frontend
make dev-web
```

### 3. Verification Commands
```bash
make lint        # Ruff lint and format check
make typecheck   # Mypy on API and tsc on Web
make test        # Pytest on API (health and security tests)
make build       # Bun build for Web static assets
```
