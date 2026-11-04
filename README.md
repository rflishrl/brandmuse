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

## Quickstart & Verification (Local Development)

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

---

## Production Deployment Guide (Phase 1b Walking Skeleton)

The production infrastructure is fixed:
- **Database & Storage:** Supabase (Singapore Region)
- **API Web Service:** Render (Docker Web Service, Starter Instance, Singapore Region)
- **Frontend SPA:** Cloudflare Pages

### 1. Supabase Setup
1. Create a project on [Supabase](https://supabase.com) in the **Singapore (ap-southeast-1)** region.
2. In the Supabase Dashboard, navigate to **Database -> Extensions** and ensure `vector` is enabled.
3. Retrieve two connection strings:
   - **Transaction Pooler Connection String (Port 6543):** Used by the deployed API on Render, because Render provides IPv4 outbound connectivity whereas direct Supabase connections use IPv6.
     - Set `DATABASE_URL=postgresql+asyncpg://postgres.[ref]:[password]@aws-0-ap-southeast-1.pooler.supabase.com:6543/postgres`
     - Set `DB_POOLER_MODE=true` (disables prepared statements `statement_cache_size=0` and uses `NullPool`).
   - **Migration Connection String (Port 5432 or Session Mode):** Used to execute Alembic migrations from your local machine.
     - Set `MIGRATION_DATABASE_URL=postgresql+asyncpg://postgres:[password]@db.[ref].supabase.co:5432/postgres`
4. Apply migrations manually before deploying:
   ```bash
   MIGRATION_DATABASE_URL="postgresql+asyncpg://..." make migrate
   ```
   *(Note: Migrations are intentionally run manually from local or release steps; do not rely on Render pre-deploy commands).*
5. **Storage Bucket:** Create a bucket named `brandmuse-images` in Supabase Storage. Set the bucket to **Public Read**. The API uploads using the Supabase Service Role key (server-side environment variable only).

### 2. Render Setup (API Service)
1. Create a **Web Service** on [Render](https://render.com) in the **Singapore** region connected to the GitHub repository.
2. Configure settings:
   - **Environment:** Docker
   - **Dockerfile Path:** `apps/api/Dockerfile`
   - **Instance Type:** Starter (512 MB RAM)
   - **Health Check Path:** `/api/health`
3. Configure Environment Variables on Render:

| Variable | Description | Example / Default |
|---|---|---|
| `PORT` | Listening port set by Render | `8000` |
| `ENVIRONMENT` | Runtime environment | `production` |
| `DATABASE_URL` | Supabase IPv4 Transaction Pooler | `postgresql+asyncpg://...:6543/postgres` |
| `DB_POOLER_MODE` | Disables prepared statement cache for pooler | `true` |
| `FTS_CONFIG` | Full-text search dictionary | `english` |
| `EMBEDDING_DIM` | Embedding dimension | `1536` |
| `LLM_PROVIDER` | Active LLM provider | `openai` |
| `EMBEDDING_PROVIDER` | Active embedding provider | `openai` |
| `IMAGE_PROVIDER` | Active image generation provider | `stability` |
| `OPENAI_API_KEY` | OpenAI API key | `sk-...` |
| `STABILITY_API_KEY` | Stability AI API key | `sk-...` |
| `SUPABASE_URL` | Supabase project URL | `https://[ref].supabase.co` |
| `SUPABASE_SERVICE_ROLE_KEY` | Server-only key for Storage uploads | `eyJ...` |
| `SUPABASE_STORAGE_BUCKET` | Image asset bucket name | `brandmuse-images` |
| `LANGFUSE_PUBLIC_URL` | Public Langfuse URL for trace links | `https://cloud.langfuse.com` |
| `CORS_ORIGIN` | Exact Cloudflare Pages domain (no wildcard) | `https://brandmuse.pages.dev` |

### 3. Cloudflare Pages Setup (Web Frontend)
1. Create a new Pages project on [Cloudflare Dashboard](https://dash.cloudflare.com) connected to the GitHub repository.
2. Configure build settings:
   - **Framework preset:** None
   - **Build command:** `bun run build`
   - **Build output directory:** `dist`
   - **Root directory:** `apps/web`
3. Environment variables on Cloudflare Pages:
   - `BUN_VERSION`: `1.4.4`
   - `VITE_API_URL`: Your Render Web Service URL (e.g. `https://brandmuse-api.onrender.com`)
4. **SPA Hard Refresh:** Handled automatically by `apps/web/public/_redirects` (`/* /index.html 200`), guaranteeing that deep routes (`/ask`, `/campaign`, etc.) resolve on hard refresh.

### 4. CORS Finalization & Production Smoke Test
1. Once Cloudflare Pages deploys, copy the canonical domain (e.g. `https://brandmuse.pages.dev`).
2. Update `CORS_ORIGIN` on Render to `https://brandmuse.pages.dev` and trigger redeploy.
3. Verify live production health:
   ```bash
   scripts/smoke-test.sh https://brandmuse-api.onrender.com
   ```
