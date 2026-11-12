# Production Deployment Guide: Neon + Cloudflare R2 + Render + Cloudflare Pages

Step-by-step guide to deploying the **BrandMuse** application with serverless database and S3-compatible storage:
- **Serverless Database:** Neon.tech (PostgreSQL 16 + native `pgvector`, 0.5 GiB free tier, automatic compute scale-to-zero without project inactivity pause)
- **Object Storage:** Cloudflare R2 (S3-compatible, 10 GB free storage per month, 1 million write operations, 10 million read operations, zero egress bandwidth fees)
- **Backend API:** Render (Web Service, FastAPI Python 3.12, Uvicorn, Free Tier)
- **Frontend SPA:** Cloudflare Pages (React 18, Bun v1.4.4, Tailwind CSS, Cloudflare global edge network)

---

## 1. Multi-Cloud Architecture and Data Flow

```mermaid
graph TD
    User["User Browser"] -->|HTTPS Global CDN| Pages["Cloudflare Pages (Frontend: React 18 / Bun)"]
    Pages -->|REST / SSE Streaming + X-Session-Id| Render["Render (FastAPI Web Service)"]
    Render -->|Pooled Connection / Port 5432 / ssl=require| Neon["Neon.tech (PostgreSQL 16 + pgvector)"]
    Render -->|S3 API / boto3 put_object| R2["Cloudflare R2 Bucket (brandmuse-images)"]
    Render -->|Persistent HTTPS| AI["Google Gemini 1.5 Flash / OpenAI"]
    User -->|Download Public Assets| R2Public["Cloudflare R2 Public CDN (pub-xxx.r2.dev)"]
```

---

## 2. Step 1: Set Up Neon.tech

Neon is a serverless PostgreSQL database with native `pgvector` support. Neon scales compute to zero during idle periods to preserve resources.

### 2.1 Create an Account and Project in Neon
1. Open [neon.tech](https://neon.tech) and sign up (GitHub OAuth is supported).
2. On the dashboard, click **Create a project**.
3. Configure the project:
   - **Project Name:** `brandmuse-db`
   - **Postgres version:** `16` (default stable release)
   - **Region:** Pilih **Asia Pacific (Singapore) - `aws-ap-southeast-1`** (atau sesuaikan dengan region Render Web Service Anda, misalnya Singapore, agar latensi database < 10ms vs ~250ms jika lintas benua).
4. Atur **Auto-suspend timeout**:
   - Buka menu **Settings** -> **Compute** di dashboard project Neon.
   - Ubah `Auto-suspend delay` dari bawaan 5 menit menjadi **30 menit** atau **60 menit**. Hal ini mencegah database sering tidur (cold start) saat pengguna sedang aktif menggunakan BrandMuse.
5. Klik **Create Project**.

### 2.2 Retrieve the Two Connection Strings
When the project is ready, Neon displays the **Connection Details** modal:

1. **Direct Connection (Used for local Alembic schema migrations):**
   - Ensure the **Connection pooling** toggle is set to **OFF**.
   - Copy the connection string:
     ```text
     postgresql://neondb_owner:PASSWORD@ep-dry-lake-123456.ap-southeast-1.aws.neon.tech/neondb?sslmode=require
     ```
   - Update the prefix to `postgresql+asyncpg://` and parameter to `ssl=require`:
     ```text
     postgresql+asyncpg://neondb_owner:PASSWORD@ep-dry-lake-123456.ap-southeast-1.aws.neon.tech/neondb?ssl=require
     ```

2. **Pooled Connection (Used by the production backend on Render):**
   - Toggle **Connection pooling** to **ON**.
   - The host name now includes a `-pooler` suffix, for example:
     `ep-dry-lake-123456-pooler.ap-southeast-1.aws.neon.tech`
   - Connection format for Render Web Service:
     ```text
     postgresql+asyncpg://neondb_owner:PASSWORD@ep-dry-lake-123456-pooler.ap-southeast-1.aws.neon.tech/neondb?ssl=require
     ```

### 2.3 Run Database Schema Migrations from Local Machine
Apply database tables, HNSW indexes, and vector extensions using your local terminal:

In PowerShell:
```powershell
cd C:\Projects\brandmuse\apps\api

# Set the Direct Neon connection string
$env:MIGRATION_DATABASE_URL = "postgresql+asyncpg://neondb_owner:PASSWORD@ep-dry-lake-123456.ap-southeast-1.aws.neon.tech/neondb?ssl=require"

# Execute Alembic migration
uv run alembic upgrade head
```

In Bash (Linux / macOS):
```bash
cd apps/api
export MIGRATION_DATABASE_URL="postgresql+asyncpg://neondb_owner:PASSWORD@ep-dry-lake-123456.ap-southeast-1.aws.neon.tech/neondb?ssl=require"
uv run alembic upgrade head
```

### 2.4 Verify Migrations in Neon SQL Editor
1. In the Neon dashboard, open **SQL Editor** from the left navigation.
2. Execute the verification query:
   ```sql
   SELECT table_name FROM information_schema.tables WHERE table_schema = 'public';
   ```
3. Confirm the presence of these five tables:
   - `alembic_version`
   - `documents`
   - `chunks`
   - `generations`
   - `usage_counters`
4. Confirm `vector` extension status:
   ```sql
   SELECT extname, extversion FROM pg_extension WHERE extname = 'vector';
   ```
   The extension must report version 0.7.x or later.

---

## 3. Step 2: Set Up Cloudflare R2

Cloudflare R2 is an S3-compatible object store with zero egress bandwidth charges.

### 3.1 Enable R2 in Cloudflare Dashboard
1. Open the [Cloudflare Dashboard](https://dash.cloudflare.com) and log in.
2. Select **R2** in the left navigation.
3. If activating R2 for the first time, complete card verification (usage under 10 GB per month is not charged).

### 3.2 Create the Storage Bucket
1. Click **Create bucket**.
2. **Bucket name:** Enter `brandmuse-images`.
3. **Location:** Select **Automatic** or **APAC (Asia-Pacific)**.
4. Click **Create Bucket**.

### 3.3 Enable Public Access
To allow browsers to load and download generated assets directly:
1. Open bucket `brandmuse-images`.
2. Select the **Settings** tab.
3. Scroll down to **Public access**.
4. In the **R2.dev subdomain** section, click **Allow Access**.
5. Enter the confirmation text `allow` and confirm.
6. Cloudflare provides the public bucket URL, for example:
   `https://pub-a1b2c3d4e5f6.r2.dev`
7. Save this URL for the `R2_PUBLIC_URL` environment variable.

*(Optional: If you use a custom domain on Cloudflare, click **Connect Domain** and assign a subdomain such as `assets.yourdomain.com`)*.

### 3.4 Generate R2 API Token (S3 Credentials)
The FastAPI backend requires S3 credentials to write generated image files:
1. Return to the main **R2** page in the left menu.
2. In the right panel, click **Manage R2 API Tokens**.
3. Click **Create API token**.
4. Configure the token settings:
   - **Token name:** `brandmuse-backend-token`
   - **Permissions:** **Object Read & Write** (or Admin Read & Write).
   - **Specify bucket(s):** Select **Apply to specific buckets only** and pick `brandmuse-images`.
   - **TTL:** Select **Forever** (does not expire).
5. Click **Create API Token**.
6. Securely record the output values:
   - **Access Key ID:** for example, `8f3a9b...`
   - **Secret Access Key:** for example, `c7e2d1...`
   - **Endpoint URL (S3):** `https://<ACCOUNT_ID>.r2.cloudflarestorage.com`
     *(Note: Account ID is the 32-character hexadecimal string preceding `.r2.cloudflarestorage.com`)*.

### 3.5 Configure CORS on the R2 Bucket
To allow client browsers to load images and canvas previews without cross-origin blocks:
1. Open bucket `brandmuse-images` -> select **Settings**.
2. Scroll to **CORS Policy** and click **Add CORS policy**.
3. Paste the following JSON configuration:
   ```json
   [
     {
       "AllowedOrigins": [
         "*"
       ],
       "AllowedMethods": [
         "GET",
         "HEAD"
       ],
       "AllowedHeaders": [
         "*"
       ],
       "ExposeHeaders": [],
       "MaxAgeSeconds": 3600
     }
   ]
   ```
4. Click **Save**.

---

## 4. Step 3: Deploy FastAPI Backend to Render

The FastAPI backend runs as a Web Service on **Render** (Python 3 / Docker, Free Tier).

### 4.1 Create Web Service on Render
1. Open [dashboard.render.com](https://dashboard.render.com) and click **New +** -> **Web Service**.
2. Connect your `brandmuse` GitHub repository.
3. Configure the Web Service:

   **Option A: Docker Runtime (Recommended, matches repository Dockerfile):**
   - **Name:** `brandmuse-api`
   - **Region:** `Singapore` (matches Neon `ap-southeast-1` for lowest latency)
   - **Branch:** `main`
   - **Runtime:** `Docker`
   - **Dockerfile Path:** `./Dockerfile`
   - **Docker Context:** `.` (repository root)
   - **Instance Type:** `Free` ($0/mo)

   **Option B: Native Python 3 Runtime (Alternative with Astral `uv`):**
   - **Name:** `brandmuse-api`
   - **Region:** `Singapore`
   - **Branch:** `main`
   - **Root Directory:** `apps/api`
   - **Runtime:** `Python 3`
   - **Build Command:** `pip install uv && uv sync --frozen --no-dev --no-install-project`
   - **Start Command:** `uv run uvicorn app.main:app --host 0.0.0.0 --port $PORT`
   - **Instance Type:** `Free` ($0/mo)

### 4.2 Configure Environment Variables in Render
In the service's **Environment** tab:

**Secrets (Sensitive Credentials):**
| Secret Key | Example Value | Notes |
| :--- | :--- | :--- |
| `DATABASE_URL` | `postgresql+asyncpg://neondb_owner:PASSWORD@ep-dry-lake-123456-pooler.ap-southeast-1.aws.neon.tech/neondb?ssl=require` | Pooled connection string from Neon |
| `R2_ACCOUNT_ID` | `abcdef1234567890abcdef1234567890` | Cloudflare Account ID |
| `R2_ACCESS_KEY_ID` | `8f3a9b0c1d2e3f4a5b6c7d8e` | R2 Access Key ID from Step 3.4 |
| `R2_SECRET_ACCESS_KEY` | `c7e2d1f0a9b8c7...` | R2 Secret Access Key from Step 3.4 |
| `R2_BUCKET_NAME` | `brandmuse-images` | Name of the configured R2 bucket |
| `R2_PUBLIC_URL` | `https://pub-a1b2c3d4e5f6.r2.dev` | Public URL from Step 3.3 |
| `GEMINI_API_KEY` | `AIzaSy...` | Google Gemini API key (LLM and Embeddings) |
| `OPENAI_API_KEY` | `sk-proj-...` | OpenAI API key (optional fallback) |
| `STABILITY_API_KEY` | `sk-...` | Stability AI API key (optional if using mock) |

**Variables (Runtime Config):**
| Variable Key | Value | Notes |
| :--- | :--- | :--- |
| `ENVIRONMENT` | `production` | Production runtime flag |
| `DB_POOLER_MODE` | `true` | Required for Neon serverless pooler |
| `STORAGE_PROVIDER` | `r2` | Activates Cloudflare R2 storage provider |
| `CORS_ORIGIN` | `https://brandmuse.pages.dev,http://localhost:5173` | Allowed frontend origins |
| `RATE_LIMIT_PER_MINUTE` | `30` | Per-IP rate limiter |
| `DAILY_LLM_LIMIT` | `200` | Global daily quota for LLM calls |
| `DAILY_IMAGE_LIMIT` | `25` | Global daily limit for image generations |
| `SESSION_IMAGE_HOURLY_LIMIT` | `5` | Per-session hourly generation cap |

4. Click **Deploy Web Service**.
5. Wait for the build to finish until status shows **Live**.
6. Copy your backend service URL (example: `https://brandmuse-13ck.onrender.com`).

### 4.3 Verify Backend Health
Test the health endpoint from terminal or browser:
```bash
curl https://brandmuse-13ck.onrender.com/api/health
```
Expected JSON response:
```json
{"status":"healthy","database":"connected","vector_extension":true}
```

---

## 5. Step 4: Deploy Frontend to Cloudflare Pages

### 5.1 Create Project in Cloudflare Pages
1. In [Cloudflare Dashboard](https://dash.cloudflare.com), click **Workers & Pages**.
2. Click **Create application**.
3. Select the **Pages** tab, then click **Connect to Git**.
4. Select the `brandmuse` repository and click **Begin setup**.

### 5.2 Configure Build and Environment
Set build configurations:
- **Project name:** `brandmuse` (maps to `https://brandmuse.pages.dev`)
- **Production branch:** `main`
- **Framework preset:** **None** (or Vite)
- **Build command:** `bun run build`
- **Build output directory:** `dist`
- **Root directory:** `apps/web`

Under **Environment variables (advanced)**, define:

| Variable Name | Value | Purpose |
| :--- | :--- | :--- |
| `BUN_VERSION` | `1.4.4` | Enforces Bun runtime version 1.4.4 |
| `VITE_API_URL` | `https://brandmuse-13ck.onrender.com` | Render Web Service backend URL |

Click **Save and Deploy**. Cloudflare Pages completes TypeScript compilation and Vite build in approximately 30 seconds.

---

## 6. Step 5: CORS Configuration and Handshake

After Cloudflare Pages finishes deployment, obtain your assigned domain (for example, `https://brandmuse.pages.dev`):

1. Open [dashboard.render.com](https://dashboard.render.com) -> select Web Service `brandmuse-api` -> **Environment**.
2. Update the `CORS_ORIGIN` variable to match the exact frontend domain:
   ```text
   CORS_ORIGIN=https://brandmuse.pages.dev,http://localhost:5173
   ```
   *(Security note: Never use a wildcard `*` in production; the custom `X-Session-Id` header requires explicit origin specification)*.
3. Render automatically redeploys the service with the updated configuration.

---

## 7. Step 6: Smoke Test Suite (8 Test Stages)

Execute the following PowerShell script to verify all services end-to-end:

```powershell
$API_URL = "https://brandmuse-13ck.onrender.com"
$SESSION_ID = [guid]::NewGuid().ToString()

Write-Host "=== 1. Health Check ===" -ForegroundColor Cyan
curl.exe -s "$API_URL/api/health"

Write-Host "`n=== 2. System Metrics ===" -ForegroundColor Cyan
curl.exe -s "$API_URL/api/metrics"

Write-Host "`n=== 3. Upload Sample PDF Guideline ===" -ForegroundColor Cyan
$pdfPath = "sample_test.pdf"
if (Test-Path "apps\api\sample_data\aura_living_brand_guidelines.pdf") {
    $pdfPath = "apps\api\sample_data\aura_living_brand_guidelines.pdf"
}
curl.exe -s -X POST "$API_URL/api/documents/upload" `
  -H "X-Session-Id: $SESSION_ID" `
  -F "file=@$pdfPath"

Write-Host "`n=== 4. Hybrid Retrieval RRF Query ===" -ForegroundColor Cyan
curl.exe -s -X POST "$API_URL/api/retrieve" `
  -H "Content-Type: application/json" `
  -H "X-Session-Id: $SESSION_ID" `
  -d '{"query":"What are the primary brand colors?","limit":3}'

Write-Host "`n=== 5. Grounded Chat SSE Stream ===" -ForegroundColor Cyan
curl.exe -N -s -X POST "$API_URL/api/ask" `
  -H "Content-Type: application/json" `
  -H "X-Session-Id: $SESSION_ID" `
  -d '{"question":"Can I use bright neon yellow on our posters?"}'

Write-Host "`n=== 6. Rate Limit Protection Check ===" -ForegroundColor Cyan
for ($i=1; $i -le 3; $i++) {
    curl.exe -s -o NUL -w "%{http_code} " "$API_URL/api/health"
}
Write-Host " (Expected 200 OK)"

Write-Host "`n=== 7. Campaign 3 Concepts Generation ===" -ForegroundColor Cyan
curl.exe -s -X POST "$API_URL/api/campaign/concepts" `
  -H "Content-Type: application/json" `
  -H "X-Session-Id: $SESSION_ID" `
  -d '{"campaign_brief":"Minimalist autumn ceramics collection launch","target_audience":"Urban homeowners"}'

Write-Host "`n=== 8. Image Generation and Cloudflare R2 Upload ===" -ForegroundColor Cyan
curl.exe -s -X POST "$API_URL/api/images" `
  -H "Content-Type: application/json" `
  -H "X-Session-Id: $SESSION_ID" `
  -d '{"prompt":"Earthy ceramic vase on limestone table with soft morning sunlight","mood":"warm minimalist"}'
```

When Stage 8 returns an asset URL containing your `https://pub-xxx.r2.dev/...` domain or valid image payload, Cloudflare R2 object storage integration is fully verified.

---

## 8. Troubleshooting and Reference

### Issue 1: `SSL connection has been closed unexpectedly` on Neon
- **Cause:** Neon enforces TLS/SSL encryption on all external network connections.
- **Fix:** Append the `?ssl=require` parameter to the database URL:
  `postgresql+asyncpg://user:pass@host/neondb?ssl=require`

### Issue 2: `password authentication failed for user "neondb_owner"`
- **Cause:** Special characters in the password (such as `#`, `@`, or `/`) were not URL-encoded in the connection string.
- **Fix:** URL-encode reserved characters (for example, replace `#` with `%23`), or copy the direct connection string directly from the Neon dashboard.

### Issue 3: R2 Assets Return Broken Images in Browser
- **Cause:** Public access is not permitted or the public URL prefix is configured incorrectly.
- **Fix:**
  1. Open Cloudflare Dashboard -> R2 -> bucket `brandmuse-images` -> **Settings**.
  2. Confirm that **R2.dev subdomain** status is **Allowed**.
  3. Ensure `R2_PUBLIC_URL` in Render Environment variables matches the subdomain exactly (example: `https://pub-xxxx.r2.dev`).
  4. Verify CORS configuration on the bucket as described in Step 3.5.

### Issue 4: Cross-Origin Resource Sharing (CORS) Blocks Frontend Requests
- **Cause:** The `CORS_ORIGIN` variable in Render Web Service does not match your Cloudflare Pages domain.
- **Fix:** In Render Dashboard -> Web Service `brandmuse-api` -> **Environment**, add your exact frontend origin (for example, `https://brandmuse.pages.dev`, without a trailing forward slash).
