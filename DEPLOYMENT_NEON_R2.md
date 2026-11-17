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
    Render -->|S3 API / boto3 put_object| R2["Cloudflare R2 Bucket (brandmuse)"]
    Render -->|Persistent HTTPS| AI["Google Gemini / OpenAI"]
    User -->|Download Public Assets| R2Public["Cloudflare R2 Custom Domain (media.yourdomain.com)"]
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
3. Confirm the presence of these six tables:
   - `alembic_version`
   - `documents`
   - `chunks`
   - `brand_ontologies`
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
2. **Bucket name:** Enter `brandmuse`.
3. **Location:** Select **APAC (Asia-Pacific)** (immutable after creation).
4. Click **Create Bucket**.

### 3.3 Connect a Custom Domain (Production)
To serve public assets with Cloudflare Cache Rules, WAF protection, and zero `r2.dev` exposure:
1. Open bucket `brandmuse` -> **Settings** -> **Public access**.
2. Leave **R2.dev subdomain** **Disabled** in production (only use `r2.dev` temporarily during local dev if needed).
3. Under **Custom Domains**, click **Add** and connect your subdomain (for example, `media.yourdomain.com`).
4. In your Cloudflare zone, configure a **Cache Rule** (`http.host eq "media.yourdomain.com"` -> **Eligible for cache**, Edge TTL **Override origin 1 year**, Browser TTL **Respect origin**) and a **WAF Custom Rule** for hotlink protection.
5. Save `https://media.yourdomain.com` for the `R2_PUBLIC_URL` environment variable.

### 3.4 Generate R2 API Token (S3 Credentials)
The FastAPI backend requires S3 credentials to write generated WebP image files:
1. Return to the main **R2** page in the left menu.
2. In the right panel, click **Manage R2 API Tokens**.
3. Click **Create API token**.
4. Configure the token settings:
   - **Token name:** `brandmuse-token`
   - **Permissions:** **Object Read & Write**
   - **Specify bucket(s):** Select **Apply to specific buckets only** and pick `brandmuse`.
   - **TTL:** Select **Forever** (rotate periodically per `docs/r2-hardening-status.md`).
5. Click **Create API Token**.
6. Securely record the output values:
   - **Access Key ID:** for example, `8f3a9b...`
   - **Secret Access Key:** for example, `c7e2d1...`
   - **Endpoint URL (S3):** `https://<ACCOUNT_ID>.r2.cloudflarestorage.com`
     *(Note: Account ID is the 32-character hexadecimal string preceding `.r2.cloudflarestorage.com`)*.

### 3.5 Configure CORS and Lifecycle on the R2 Bucket
To allow client browsers to load images and expose `ETag`:
1. Open bucket `brandmuse` -> select **Settings**.
2. Scroll to **CORS Policy** and click **Add CORS policy**:
   ```json
   [
     {
       "AllowedOrigins": [
         "https://brandmuse.pages.dev",
         "http://localhost:5173",
         "http://127.0.0.1:5173"
       ],
       "AllowedMethods": [
         "GET",
         "HEAD"
       ],
       "AllowedHeaders": [
         "*"
       ],
       "ExposeHeaders": [
         "ETag"
       ],
       "MaxAgeSeconds": 3600
     }
   ]
   ```
3. Under **Object lifecycle rules**, add a global rule to **Abort incomplete multipart uploads** after `1` day, and optionally a rule scoped to prefix `brandmuse-dev/` to delete test objects after `7` days. Do not add auto-delete rules to the `brandmuse/` production prefix.

---

## 4. Step 3: Deploy FastAPI Backend to Render

The FastAPI backend runs as a Web Service on **Render** (Python 3 / Docker, Free Tier).

### 4.1 Create Web Service on Render
1. Open [dashboard.render.com](https://dashboard.render.com) and click **New +** -> **Web Service**.
2. Connect your `brandmuse` GitHub repository.
3. Configure the Web Service:

   **Docker Runtime (Recommended, matches repository `./Dockerfile`):**
   - **Name:** `brandmuse-api`
   - **Region:** `Singapore` (matches Neon `ap-southeast-1` for lowest latency)
   - **Branch:** `main`
   - **Runtime:** `Docker`
   - **Dockerfile Path:** `./Dockerfile`
   - **Docker Context:** `.` (repository root)
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
| `R2_BUCKET_NAME` | `brandmuse` | Name of the configured R2 bucket |
| `R2_KEY_PREFIX` | `brandmuse` | Key prefix (`brandmuse` in production; `*-dev` outside production) |
| `R2_PUBLIC_URL` | `https://media.yourdomain.com` | Custom domain URL from Step 3.3 |
| `R2_APP_QUOTA_MB` | `2048` | Hard storage quota in MB for BrandMuse |
| `ADMIN_TOKEN` | `<random-64-hex>` | Bearer token for `GET /api/admin/usage` |
| `MEDIA_OWNER_SECRET` | `<random-64-hex>` | HMAC secret for hashing `X-Session-Id` in object keys |
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
{"status":"ok","database":"connected","providers":{"llm":"gemini","embeddings":"gemini","image":"mock"}}
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

## 7. Step 6: Smoke Test Suite

Run the built-in end-to-end smoke test script from the repository root:

```powershell
# PowerShell
.\scripts\smoke-test.ps1 -BaseUrl "https://brandmuse-13ck.onrender.com"
```

```bash
# Bash
bash scripts/smoke-test.sh "https://brandmuse-13ck.onrender.com"
```

When Stage 7 returns WebP `url` and `thumbnail_url` values pointing to your `R2_PUBLIC_URL` custom domain (`https://media.yourdomain.com/brandmuse/generations/...`), Cloudflare R2 integration is verified.

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
- **Cause:** Custom domain is inactive, `R2_PUBLIC_URL` does not match, or CORS/Hotlink WAF blocks the frontend origin.
- **Fix:**
  1. Open Cloudflare Dashboard -> R2 -> bucket `brandmuse` -> **Settings**.
  2. Confirm that **Custom Domains** lists your domain as **Active / Enabled**.
  3. Ensure `R2_PUBLIC_URL` in Render matches your custom domain exactly (example: `https://media.yourdomain.com`, without a trailing slash).
  4. Verify CORS configuration on the bucket (Step 3.5) and WAF Hotlink rule allow your frontend origin.

### Issue 4: Cross-Origin Resource Sharing (CORS) Blocks Frontend Requests
- **Cause:** The `CORS_ORIGIN` variable in Render Web Service does not match your Cloudflare Pages domain.
- **Fix:** In Render Dashboard -> Web Service `brandmuse-api` -> **Environment**, add your exact frontend origin (for example, `https://brandmuse.pages.dev`, without a trailing forward slash).
