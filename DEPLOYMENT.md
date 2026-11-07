# Production Deployment Guide: Cloudflare Pages + Supabase + Render

> **Multi-Cloud Alternative:** If your Supabase account hits quota or project limits, refer to [DEPLOYMENT_NEON_R2.md](file:///C:/Projects/brandmuse/DEPLOYMENT_NEON_R2.md) for an unmetered setup using **Neon.tech (serverless PostgreSQL with pgvector)** and **Cloudflare R2 (10 GB free tier, zero egress fees)**.

Step-by-step guide to deploying the **BrandMuse** application to cloud production:
- **Frontend SPA:** Cloudflare Pages
- **Database & Storage:** Supabase (PostgreSQL 15 + pgvector + Object Storage)
- **Backend API:** Render (Docker Web Service, Starter 512 MB RAM, Singapore region)

---

## Architecture and Communication Flow

```
[User Browser]
       │
       ▼ (HTTPS)
[Cloudflare Pages] (apps/web: React 18, Bun, Tailwind CSS)
       │
       ▼ (REST / SSE Streaming with X-Session-Id header)
[Render API Service] (apps/api: FastAPI, Python 3.12, Uvicorn)
       │
       ├─────────────────────────────┬─────────────────────────────┐
       ▼ (Pooler Port 6543 IPv4)      ▼ (HTTPS REST / S3 API)       ▼ (HTTPS)
  [Supabase DB]                [Supabase Storage]              [OpenAI / Stability]
(pgvector + tsvector)          (bucket: brandmuse-images)     (gpt-4o-mini / SDXL 1.0)
```

---

## Step 1: Database and Storage Setup on Supabase

### 1.1 Create a New Supabase Project
1. Log in to the [Supabase Dashboard](https://supabase.com/dashboard).
2. Click **New Project**.
3. Select Region: **Singapore (`ap-southeast-1`)** to maintain sub-10 ms latency to the Render instance in Singapore.
4. Store your database password in a secure password manager.

### 1.2 Enable the `vector` Extension
1. In the Supabase sidebar, open **Database** -> **Extensions**.
2. Search for `vector` (pgvector).
3. Confirm that status is **Enabled** (Alembic migrations also issue `CREATE EXTENSION IF NOT EXISTS vector;`).

### 1.3 Retrieve the Two Connection Strings
Supabase provides two distinct connection endpoints. Distinguishing them is critical:

1. **Transaction Pooler URL (Port 6543, IPv4):**
   - Required by the **Backend API on Render**, because Render uses IPv4 networking whereas direct Supabase connections use IPv6.
   - Navigate to **Project Settings** -> **Database** -> **Connection Pooling**.
   - Select mode: **Transaction** (Port `6543`).
   - Connection string format (use the `postgresql+asyncpg://` driver prefix):
     ```
     postgresql+asyncpg://postgres.[PROJECT_REF]:[PASSWORD]@aws-0-ap-southeast-1.pooler.supabase.com:6543/postgres
     ```

2. **Direct / Session URL (Port 5432):**
   - Used from your local machine to apply Alembic database schema migrations.
   - Format:
     ```
     postgresql+asyncpg://postgres:[PASSWORD]@db.[PROJECT_REF].supabase.co:5432/postgres
     ```

### 1.4 Run Database Schema Migrations from Local Machine
Execute migrations from your local terminal using the direct Port 5432 connection string:

```powershell
cd C:\Projects\brandmuse\apps\api

# Set the migration connection string and run Alembic upgrade
$env:MIGRATION_DATABASE_URL = "postgresql+asyncpg://postgres:[PASSWORD]@db.[PROJECT_REF].supabase.co:5432/postgres"
uv run alembic upgrade head
```

On Linux or macOS:
```bash
cd apps/api
export MIGRATION_DATABASE_URL="postgresql+asyncpg://postgres:[PASSWORD]@db.[PROJECT_REF].supabase.co:5432/postgres"
uv run alembic upgrade head
```

Upon success, the following four tables and their corresponding HNSW vector indexes and RLS policies are created:
- `documents` (brand guideline document metadata)
- `chunks` (text segments, 1536-dimensional vector embeddings, and GIN `tsvector` indexes)
- `generations` (campaign concept history and permanent image asset URLs)
- `usage_counters` (database-persisted global daily usage quotas)

### 1.5 Create Storage Bucket for Image Assets
1. In the Supabase dashboard, select **Storage**.
2. Click **New Bucket**.
3. Name the bucket: **`brandmuse-images`**.
4. Enable **Public bucket** (so user browsers can display and download generated images directly).
5. Click **Save**.
6. Retrieve API credentials:
   - Go to **Project Settings** -> **API**.
   - Copy the **Project URL** (example: `https://xyzcompany.supabase.co`).
   - Copy the **`service_role` secret key** (this key has administrative privileges; place it only in the Render environment, never in frontend code).

---

## Step 2: Deploy Backend API to Render

Cloudflare Pages serves static Single Page Applications (SPA), so the FastAPI backend is deployed to a container host such as Render.

### 2.1 Create a Web Service on Render
1. Log in to the [Render Dashboard](https://dashboard.render.com).
2. Click **New +** -> select **Web Service**.
3. Connect your `brandmuse` GitHub repository.
4. Set service name: for example, `brandmuse-api`.
5. Select Region: **Singapore**.
6. Select Runtime: **Docker**.
7. Configure build settings:
   - **Dockerfile Path:** `apps/api/Dockerfile`
   - **Docker Context Directory:** `.` (repository root)
8. Select Instance Type: **Starter** (512 MB RAM) or **Free**.
9. Set Health Check Path: **`/api/health`**.

### 2.2 Configure Environment Variables in Render
In the **Environment Variables** section, add the following variables:

| Variable Name | Example Value | Description |
| :--- | :--- | :--- |
| `PORT` | `8000` | Application port for FastAPI |
| `ENVIRONMENT` | `production` | Runtime mode |
| `DATABASE_URL` | `postgresql+asyncpg://postgres.[REF]:[PASS]@aws-0-ap-southeast-1.pooler.supabase.com:6543/postgres` | Supabase IPv4 Transaction Pooler on port 6543 |
| `DB_POOLER_MODE` | `true` | Required for port 6543 to disable prepared statements on transaction poolers |
| `FTS_CONFIG` | `english` | Full-text search dictionary configuration |
| `LLM_PROVIDER` | `openai` | OpenAI provider using gpt-4o-mini |
| `EMBEDDING_PROVIDER` | `openai` | Embedding provider using text-embedding-3-small |
| `EMBEDDING_DIM` | `1536` | Vector embedding dimension |
| `IMAGE_PROVIDER` | `stability` *(or `mock` if testing without keys)* | Image generation backend |
| `OPENAI_API_KEY` | `sk-...` | OpenAI API key |
| `STABILITY_API_KEY` | `sk-...` | Stability AI API key |
| `SUPABASE_URL` | `https://[PROJECT_REF].supabase.co` | Supabase project API URL |
| `SUPABASE_SERVICE_ROLE_KEY` | `eyJhbGciOi...` | Supabase service role secret key for storage uploads |
| `SUPABASE_STORAGE_BUCKET` | `brandmuse-images` | Name of the public storage bucket |
| `DAILY_LLM_LIMIT` | `200` | Global daily quota protecting budget |
| `DAILY_IMAGE_LIMIT` | `25` | Global daily limit for image generation |
| `SESSION_IMAGE_HOURLY_LIMIT` | `5` | Per-session hourly rate limit |
| `CORS_ORIGIN` | `http://localhost:5173` *(updated in Step 4 after Pages deploys)* | Allowed frontend origins |

10. Click **Create Web Service**.
11. Wait for the build to finish until status shows **Live**. Record your Render backend URL (example: `https://brandmuse-api.onrender.com`).

---

## Step 3: Deploy Frontend to Cloudflare Pages

### 3.1 Connect Repository to Cloudflare Pages
1. Log in to the [Cloudflare Dashboard](https://dash.cloudflare.com).
2. In the left navigation, select **Workers & Pages**.
3. Click **Create application** -> select the **Pages** tab -> click **Connect to Git**.
4. Select the `brandmuse` GitHub repository.

### 3.2 Configure Build Settings
Configure build parameters:
- **Project name:** `brandmuse` (or chosen project identifier)
- **Production branch:** `main`
- **Framework preset:** `None`
- **Root directory:** `apps/web`
- **Build command:** `bun run build`
- **Build output directory:** `dist`

### 3.3 Configure Environment Variables in Cloudflare Pages
Open **Environment variables (advanced)** and define:

| Variable | Value | Description |
| :--- | :--- | :--- |
| `BUN_VERSION` | `1.4.4` | Instructs the Cloudflare build runner to install Bun v1.4.4 |
| `VITE_API_URL` | `https://brandmuse-api.onrender.com` | Render Web Service URL from Step 2 |

### 3.4 Deep Route Handling for Single Page Applications
The frontend includes `apps/web/public/_redirects` containing:
```
/* /index.html 200
```
This rule copies to `dist/_redirects` during the build so that direct navigation or hard refreshes on routes such as `/ask`, `/campaign`, or `/gallery` resolve correctly without 404 errors.

### 3.5 Deploy
Click **Save and Deploy**. Cloudflare Pages pulls the repository, compiles the TypeScript codebase using Bun, and publishes the build to Cloudflare's global edge network. Record your assigned Pages URL (example: `https://brandmuse.pages.dev`).

---

## Step 4: Finalize CORS and Run Smoke Tests

### 4.1 Update CORS Origins in Render
1. Return to your Render Web Service dashboard.
2. In the **Environment Variables** section, update `CORS_ORIGIN`:
   ```env
   CORS_ORIGIN=https://brandmuse.pages.dev
   ```
   *(Important: Supply the full origin without a trailing slash. Do not use a wildcard `*` in production).*
3. Click **Save Changes**. Render restarts the service with the new policy.

### 4.2 Run End-to-End Smoke Tests
Verify all production endpoints directly against your live Render instance:

```powershell
# From local PowerShell:
.\scripts\smoke-test.ps1 -BaseUrl "https://brandmuse-api.onrender.com"

# Or from Git Bash / Linux:
./scripts/smoke-test.sh https://brandmuse-api.onrender.com
```

The script automatically validates 8 workflow stages:
1. `GET /api/health` returns 200 with standard security headers.
2. Session isolation via `X-Session-Id` header validation.
3. Ingestion of the sample brand guideline into Supabase.
4. Document listing verification.
5. Grounded Q&A chat with token streaming via Server-Sent Events (SSE).
6. Synthesis of 3 structured campaign concepts.
7. Image generation with automatic upload to the storage bucket.
8. Verification of the stored image in the session gallery.

---

## Operational Notes and Troubleshooting

1. **Why Port 6543 (`DB_POOLER_MODE=true`) is Required on Render:**
   Render communicates over IPv4. Direct connections to Supabase (port 5432) resolve to IPv6, which is unreachable from certain cloud networks. The Supabase Transaction Pooler on port 6543 provides an IPv4 gateway. When using port 6543, prepared statement caching must be disabled (`DB_POOLER_MODE=true`) so asyncpg does not encounter statement cache mismatch errors.
2. **Backend Cold Starts (Render Free / Starter Tier):**
   If an instance receives no incoming requests for 15 minutes, Render spins down the container. The BrandMuse frontend includes an automatic detection mechanism: if an initial API request takes longer than 5 seconds, an informational status bar notifies the user that the container is starting.
3. **Supabase Secret Key Protection:**
   The `SUPABASE_SERVICE_ROLE_KEY` bypasses PostgreSQL Row Level Security (RLS). This key must reside exclusively within the Render backend environment and must never be exposed to frontend code or client bundles.
