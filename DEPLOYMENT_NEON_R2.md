# Panduan Deployment Produksi: Neon + Cloudflare R2 + Render + Cloudflare Pages

Panduan komprehensif langkah demi langkah untuk melakukan deploy penuh aplikasi **BrandMuse** dari awal tanpa bergantung pada kuota akun Supabase:
- **Database Serverless:** Neon.tech (PostgreSQL 16 + native `pgvector`, kuota gratis 0.5 GiB, auto-suspend tanpa batasan masa aktif)
- **Object Storage:** Cloudflare R2 (S3-compatible, gratis 10 GB per bulan, gratis 1 juta operasi tulis, gratis 10 juta operasi baca, $0 biaya bandwidth egress)
- **Backend API:** Render (Docker Web Service, FastAPI Python 3.12, Uvicorn, Region Singapore)
- **Frontend SPA:** Cloudflare Pages (React 18, Bun v1.4.4, Tailwind CSS, CDN global Cloudflare)

---

## 1. Arsitektur Multi-Cloud & Alur Data

```mermaid
graph TD
    User["Browser Pengguna"] -->|HTTPS CDN Global| Pages["Cloudflare Pages (Frontend React 18 / Bun)"]
    Pages -->|REST / SSE Streaming + X-Session-Id| Render["Render API (FastAPI / Docker di Singapore)"]
    Render -->|Pooled Connection / Port 5432 / ssl=require| Neon["Neon.tech (PostgreSQL 16 + pgvector)"]
    Render -->|S3 API / boto3 put_object| R2["Cloudflare R2 Bucket (brandmuse-images)"]
    Render -->|HTTPS API| AI["OpenAI (Embeddings) & Stability AI (SDXL)"]
    User -->|Download Gambar Publik| R2Public["Cloudflare R2 Public CDN (pub-xxx.r2.dev)"]
```

---

## 2. Langkah 1: Setup Neon.tech dari Awal

Neon adalah database PostgreSQL serverless yang mendukung ekstensi `pgvector` secara native. Neon secara otomatis menskalakan komputasi ke 0 saat tidak ada traffic sehingga kuota gratis Anda tidak cepat habis.

### 2.1 Buat Akun & Project Baru di Neon
1. Buka [neon.tech](https://neon.tech) dan klik **Sign Up** (Anda dapat masuk langsung menggunakan akun GitHub).
2. Di halaman dashboard, klik **Create a project**.
3. Isi konfigurasi project:
   - **Project Name:** `brandmuse-db`
   - **Postgres version:** `16` (versi default yang stabil)
   - **Region:** Pilih **Asia Pacific (Singapore) - `aws-ap-southeast-1`** (Penting: pilih Singapore agar latensi jaringan antara backend Render di Singapore dan database Neon tetap di bawah 15 ms).
4. Klik **Create Project**.

### 2.2 Salin Dua Jenis Connection String
Setelah project dibuat, Neon akan menampilkan dialog **Connection Details**:

1. **Direct Connection (Digunakan untuk Migrasi Skema Alembic dari Lokal):**
   - Pastikan toggle **Connection pooling** dalam keadaan **OFF**.
   - Salin connection string yang berformat:
     ```text
     postgresql://neondb_owner:PASSWORD@ep-dry-lake-123456.ap-southeast-1.aws.neon.tech/neondb?sslmode=require
     ```
   - Ubah prefix `postgresql://` menjadi `postgresql+asyncpg://` dan ganti `sslmode=require` menjadi `ssl=require`:
     ```text
     postgresql+asyncpg://neondb_owner:PASSWORD@ep-dry-lake-123456.ap-southeast-1.aws.neon.tech/neondb?ssl=require
     ```

2. **Pooled Connection (Digunakan oleh Backend Render di Produksi):**
   - Aktifkan toggle **Connection pooling** menjadi **ON**.
   - Host akan berubah memiliki akhiran `-pooler`, misalnya:
     `ep-dry-lake-123456-pooler.ap-southeast-1.aws.neon.tech`
   - Format untuk Render:
     ```text
     postgresql+asyncpg://neondb_owner:PASSWORD@ep-dry-lake-123456-pooler.ap-southeast-1.aws.neon.tech/neondb?ssl=require
     ```

### 2.3 Jalankan Migrasi Skema Database dari Komputer Lokal
Jalankan migrasi tabel Alembic dari komputer Anda untuk membuat seluruh tabel, indeks HNSW, dan ekstensi vektor di database Neon:

Buka terminal PowerShell di folder project:
```powershell
cd C:\Projects\brandmuse\apps\api

# Masukkan connection string Direct Neon Anda
$env:MIGRATION_DATABASE_URL = "postgresql+asyncpg://neondb_owner:PASSWORD@ep-dry-lake-123456.ap-southeast-1.aws.neon.tech/neondb?ssl=require"

# Jalankan migrasi Alembic
uv run alembic upgrade head
```

Jika menggunakan Linux atau macOS:
```bash
cd apps/api
export MIGRATION_DATABASE_URL="postgresql+asyncpg://neondb_owner:PASSWORD@ep-dry-lake-123456.ap-southeast-1.aws.neon.tech/neondb?ssl=require"
uv run alembic upgrade head
```

### 2.4 Verifikasi Hasil Migrasi di Neon SQL Editor
1. Di dashboard Neon, klik menu **SQL Editor** pada sidebar kiri.
2. Jalankan query berikut:
   ```sql
   SELECT table_name FROM information_schema.tables WHERE table_schema = 'public';
   ```
3. Pastikan 5 entitas berikut terdaftar:
   - `alembic_version`
   - `documents`
   - `chunks`
   - `generations`
   - `usage_counters`
4. Cek ekstensi `vector`:
   ```sql
   SELECT extname, extversion FROM pg_extension WHERE extname = 'vector';
   ```
   Ekstensi vector harus aktif (versi 0.7.x atau lebih baru).

---

## 3. Langkah 2: Setup Cloudflare R2 dari Awal

Cloudflare R2 adalah object storage yang kompatibel 100% dengan Amazon S3 API, tanpa biaya egress bandwidth sama sekali ($0 per GB transfer keluar).

### 3.1 Aktifkan R2 di Cloudflare Dashboard
1. Buka [Cloudflare Dashboard](https://dash.cloudflare.com) dan login ke akun Anda.
2. Di menu sidebar kiri, klik **R2**.
3. Jika ini pertama kali Anda menggunakan R2, Cloudflare akan meminta verifikasi kartu (tidak ada biaya penagihan selama pemakaian di bawah 10 GB per bulan).

### 3.2 Buat Bucket untuk Gambar BrandMuse
1. Klik tombol **Create bucket**.
2. **Bucket name:** Ketik `brandmuse-images`.
3. **Location:** Pilih **Automatic** atau **APAC (Asia-Pacific)**.
4. Klik **Create Bucket**.

### 3.3 Aktifkan Akses Publik (Public Access)
Agar gambar yang di-generate dapat diakses, dilihat, dan diunduh langsung oleh browser pengguna:
1. Masuk ke dalam bucket `brandmuse-images`.
2. Klik tab **Settings**.
3. Gulir ke bawah ke bagian **Public access**.
4. Di bagian **R2.dev subdomain**, klik tombol **Allow Access**.
5. Ketikkan kata konfirmasi `allow`, lalu klik **Allow**.
6. Cloudflare akan menampilkan URL publik bucket Anda, contoh:
   `https://pub-a1b2c3d4e5f6.r2.dev`
7. Simpan URL ini, ini adalah nilai untuk environment variable `R2_PUBLIC_URL`.

*(Opsional: Jika Anda memiliki domain kustom di Cloudflare, Anda dapat mengklik **Connect Domain** dan memasukkan subdomain seperti `assets.namadomain.com`)*.

### 3.4 Buat R2 API Token (Kredensial S3)
Backend FastAPI membutuhkan API Token S3 untuk mengunggah gambar hasil generasi:
1. Kembali ke halaman utama **R2** (klik R2 di sidebar kiri).
2. Di panel sebelah kanan, klik **Manage R2 API Tokens**.
3. Klik tombol **Create API token**.
4. Isi formulir token:
   - **Token name:** `brandmuse-backend-token`
   - **Permissions:** Pilih **Object Read & Write** (atau Admin Read & Write).
   - **Specify bucket(s):** Pilih opsi **Apply to specific buckets only** lalu pilih `brandmuse-images` (atau Apply to all buckets).
   - **TTL:** Pilih **Forever** (tidak kedaluwarsa).
5. Klik **Create API Token**.
6. Simpan nilai-nilai berikut dengan aman:
   - **Access Key ID:** contoh: `8f3a9b...`
   - **Secret Access Key:** contoh: `c7e2d1...`
   - **Endpoint URL S3:** `https://<ACCOUNT_ID>.r2.cloudflarestorage.com`
     *(Catatan: Account ID adalah 32 karakter hex di depan `.r2.cloudflarestorage.com`)*.

### 3.5 Atur CORS pada Bucket R2
Agar browser pengguna dapat memuat gambar dan preview kanvas tanpa terblokir keamanan browser:
1. Masuk ke bucket `brandmuse-images` -> tab **Settings**.
2. Gulir ke bagian **CORS Policy** dan klik **Add CORS policy**.
3. Tempel konfigurasi JSON berikut:
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
4. Klik **Save**.

---

## 4. Langkah 3: Deploy Backend FastAPI ke Render

Backend FastAPI dideploy sebagai container Docker di Render (Region Singapore) agar selalu berdekatan dengan database Neon.

### 4.1 Buat Web Service Baru di Render
1. Buka [dashboard.render.com](https://dashboard.render.com).
2. Klik **New +** di pojok kanan atas, lalu pilih **Web Service**.
3. Pilih opsi **Build and deploy from a Git repository**.
4. Pilih repositori GitHub `brandmuse` Anda (klik *Configure account* jika repositori belum muncul).
5. Isi konfigurasi dasar:
   - **Name:** `brandmuse-api`
   - **Region:** **Singapore (Southeast Asia)**
   - **Branch:** `main`
   - **Runtime:** **Docker**
   - **Dockerfile Path:** `./apps/api/Dockerfile`
   - **Docker Context:** `./apps/api`
   - **Instance Type:** **Starter** (512 MB RAM, $7/bulan) atau **Free tier** (512 MB RAM).

### 4.2 Masukkan Environment Variables di Render
Di bagian **Environment Variables**, tambahkan baris-baris berikut:

| Key | Value Contoh | Keterangan |
| :--- | :--- | :--- |
| `DATABASE_URL` | `postgresql+asyncpg://neondb_owner:PASSWORD@ep-xxx-pooler.ap-southeast-1.aws.neon.tech/neondb?ssl=require` | Connection string Pooled Neon |
| `DB_POOLER_MODE` | `false` | NullPool mode (opsional `true` jika PgBouncer strict) |
| `STORAGE_PROVIDER` | `r2` | Mengaktifkan provider Cloudflare R2 |
| `R2_ACCOUNT_ID` | `abcdef1234567890abcdef1234567890` | Cloudflare Account ID Anda |
| `R2_ACCESS_KEY_ID` | `8f3a9b0c1d2e3f4a5b6c7d8e` | R2 Access Key ID dari Langkah 3.4 |
| `R2_SECRET_ACCESS_KEY` | `c7e2d1f0a9b8c7...` | R2 Secret Access Key dari Langkah 3.4 |
| `R2_BUCKET_NAME` | `brandmuse-images` | Nama bucket R2 yang dibuat |
| `R2_PUBLIC_URL` | `https://pub-a1b2c3d4e5f6.r2.dev` | URL publik R2 dari Langkah 3.3 |
| `OPENAI_API_KEY` | `sk-proj-...` | API Key OpenAI (untuk Chat dan Embeddings) |
| `STABILITY_API_KEY` | `sk-...` | API Key Stability AI (untuk image generation) |
| `ENVIRONMENT` | `production` | Mode runtime produksi |
| `CORS_ORIGIN` | `https://brandmuse.pages.dev,http://localhost:5173` | Domain Cloudflare Pages (dapat disesuaikan) |
| `RATE_LIMIT_PER_MINUTE` | `30` | Pembatasan rate limit IP |
| `DAILY_LLM_LIMIT` | `200` | Batas harian panggilan LLM |
| `DAILY_IMAGE_LIMIT` | `25` | Batas harian generasi gambar |
| `SESSION_IMAGE_HOURLY_LIMIT` | `5` | Batas per sesi pengguna per jam |

6. Klik **Create Web Service**.
7. Tunggu sekitar 2 hingga 3 menit hingga status berubah menjadi **Live**.
8. Salin URL backend Anda, misalnya: `https://brandmuse-api.onrender.com`.

### 4.3 Uji Endpoint Health Backend
Buka browser atau terminal dan uji endpoint health:
```bash
curl https://brandmuse-api.onrender.com/api/health
```
Output yang diharapkan:
```json
{"status":"healthy","database":"connected","vector_extension":true}
```

---

## 5. Langkah 4: Deploy Frontend ke Cloudflare Pages

Cloudflare Pages menyajikan Single Page Application (SPA) React dengan kompresi Brotli, caching global edge, dan waktu load sub-detik secara gratis.

### 5.1 Buat Project di Cloudflare Pages
1. Di [Cloudflare Dashboard](https://dash.cloudflare.com), klik menu **Workers & Pages** di sidebar kiri.
2. Klik tombol **Create application**.
3. Pilih tab **Pages**, lalu klik **Connect to Git**.
4. Pilih repositori GitHub `brandmuse` Anda dan klik **Begin setup**.

### 5.2 Konfigurasi Build & Environment
Isi pengaturan build sebagai berikut:
- **Project name:** `brandmuse` (akan menghasilkan URL `https://brandmuse.pages.dev`)
- **Production branch:** `main`
- **Framework preset:** Pilih **None** (atau Vite)
- **Build command:** `bun run build`
- **Build output directory:** `dist`
- **Root directory:** `apps/web`

Klik bagian **Environment variables (advanced)** dan tambahkan dua variabel:

| Variable Name | Value | Keterangan |
| :--- | :--- | :--- |
| `BUN_VERSION` | `1.4.4` | Menginstruksikan builder Cloudflare untuk memakai Bun v1.4.4 |
| `VITE_API_URL` | `https://brandmuse-api.onrender.com` | URL Web Service Render dari Langkah 4.2 |

Klik **Save and Deploy**. Cloudflare Pages akan menjalankan kompilasi TypeScript dan Vite build dalam waktu sekitar 30 detik.

---

## 6. Langkah 5: Penyelarasan CORS & Handshake Terakhir

Setelah Cloudflare Pages selesai melakukan deployment, Anda memiliki domain produksi frontend (misalnya `https://brandmuse.pages.dev`):

1. Buka dashboard Render -> Web Service `brandmuse-api` -> tab **Environment**.
2. Perbarui variabel `CORS_ORIGIN` dengan domain persis dari Cloudflare Pages:
   ```text
   CORS_ORIGIN=https://brandmuse.pages.dev,http://localhost:5173
   ```
   *(Peringatan keamanan: Jangan gunakan wildcard `*` di produksi karena header kustom `X-Session-Id` memerlukan origin spesifik)*.
3. Klik **Save Changes**. Render akan otomatis merestart container dalam hitungan detik.

---

## 7. Langkah 6: Smoke Test Komprehensif (8 Alur Pengujian)

Jalankan skrip pengujian berikut di PowerShell untuk memverifikasi seluruh komponen bekerja sinkron:

```powershell
$API_URL = "https://brandmuse-api.onrender.com"
$SESSION_ID = [guid]::NewGuid().ToString()

Write-Host "=== 1. Health Check ===" -ForegroundColor Cyan
curl.exe -s "$API_URL/api/health"

Write-Host "`n=== 2. System Metrics ===" -ForegroundColor Cyan
curl.exe -s "$API_URL/api/metrics"

Write-Host "`n=== 3. Upload Sample PDF Guideline ===" -ForegroundColor Cyan
# Buat dokumen uji jika belum ada
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

Write-Host "`n=== 8. Image Generation & Cloudflare R2 Upload ===" -ForegroundColor Cyan
curl.exe -s -X POST "$API_URL/api/images" `
  -H "Content-Type: application/json" `
  -H "X-Session-Id: $SESSION_ID" `
  -d '{"prompt":"Earthy ceramic vase on limestone table with soft morning sunlight","mood":"warm minimalist"}'
```

Jika langkah 8 mengembalikan URL dengan domain `https://pub-xxx.r2.dev/...` atau data URI, berarti integrasi penyimpanan Cloudflare R2 telah berhasil sepenuhnya!

---

## 8. Panduan Troubleshooting & Solusi Praktis

### Kendala 1: `SSL connection has been closed unexpectedly` pada Neon
- **Penyebab:** Neon mewajibkan enkripsi TLS/SSL pada seluruh koneksi jaringan.
- **Solusi:** Pastikan parameter `?ssl=require` terpasang di akhir URL database:
  `postgresql+asyncpg://user:pass@host/neondb?ssl=require`

### Kendala 2: `password authentication failed for user "neondb_owner"`
- **Penyebab:** Karakter khusus pada password (seperti `#`, `@`, atau `/`) belum di-encode URL saat ditulis dalam string koneksi.
- **Solusi:** Lakukan URL encode pada karakter khusus password Anda (misal `#` menjadi `%23`), atau salin langsung string koneksi dari tombol copy di Neon dashboard.

### Kendala 3: Gambar R2 Tidak Muncul di Browser (Broken Image Icon)
- **Penyebab:** Public Access pada R2 belum diizinkan atau URL public salah.
- **Solusi:**
  1. Masuk ke Cloudflare Dashboard -> R2 -> bucket `brandmuse-images` -> **Settings**.
  2. Pastikan **R2.dev subdomain** berstatus **Allowed**.
  3. Pastikan nilai `R2_PUBLIC_URL` di Render sama persis dengan alamat subdomain yang tertera (misal: `https://pub-xxxx.r2.dev`).
  4. Periksa CORS policy bucket R2 sesuai Langkah 3.5.

### Kendala 4: CORS Blocked saat Memanggil API dari Frontend
- **Penyebab:** Header `CORS_ORIGIN` di Render belum mencantumkan domain Cloudflare Pages Anda.
- **Solusi:** Buka Render -> Environment -> tambahkan URL origin persis frontend Anda (misalnya `https://brandmuse.pages.dev`, tanpa garis miring penutup `/`).
