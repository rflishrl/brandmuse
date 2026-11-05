# Panduan Deployment Produksi: Cloudflare Pages + Supabase + Render

Panduan langkah demi langkah untuk melakukan deploy penuh aplikasi **BrandMuse** ke lingkungan produksi cloud:
- **Frontend SPA:** Cloudflare Pages
- **Database & Storage:** Supabase (PostgreSQL 15 + pgvector + Object Storage)
- **Backend API:** Render (Docker Web Service, Starter 512 MB RAM, Region Singapore)

---

## Arsitektur & Alur Komunikasi

```
[Pengguna di Browser]
        │
        ▼ (HTTPS)
[Cloudflare Pages] (apps/web - React 18, Bun, Tailwind CSS)
        │
        ▼ (REST / SSE Streaming dengan header X-Session-Id)
[Render API Service] (apps/api - FastAPI, Python 3.12, Uvicorn)
        │
        ├─────────────────────────────┬─────────────────────────────┐
        ▼ (Pooler Port 6543 IPv4)      ▼ (HTTPS REST / S3 API)       ▼ (HTTPS)
   [Supabase DB]                [Supabase Storage]              [OpenAI / Stability]
(pgvector + tsvector)          (bucket: brandmuse-images)     (gpt-4o-mini / SDXL 1.0)
```

---

## Langkah 1: Persiapan Database & Storage di Supabase

### 1.1 Buat Project Supabase Baru
1. Masuk ke [Supabase Dashboard](https://supabase.com/dashboard).
2. Klik **"New Project"**.
3. Pilih Region: **Singapore (`ap-southeast-1`)** agar latensi ke Render (Singapore) berada di bawah 10 ms.
4. Simpan database password Anda dengan aman.

### 1.2 Aktifkan Extension `vector`
1. Di sidebar dashboard Supabase, buka menu **Database** -> **Extensions**.
2. Cari `vector` (pgvector).
3. Pastikan statusnya **Enabled** (migrasi Alembic juga menyertakan perintah `CREATE EXTENSION IF NOT EXISTS vector;`).

### 1.3 Dapatkan Dua Jenis Connection String
Supabase menyediakan dua jenis alamat koneksi. Sangat penting membedakan keduanya:

1. **Transaction Pooler URL (Port 6543 - IPv4):**
   - Digunakan oleh **Backend API di Render**, karena Render menggunakan jaringan IPv4 sedangkan koneksi langsung Supabase menggunakan IPv6.
   - Buka **Project Settings** -> **Database** -> bagian **Connection Pooling**.
   - Pilih mode: **Transaction** (Port `6543`).
   - Format connection string (gunakan prefix `postgresql+asyncpg://`):
     ```
     postgresql+asyncpg://postgres.[PROJECT_REF]:[PASSWORD]@aws-0-ap-southeast-1.pooler.supabase.com:6543/postgres
     ```

2. **Direct / Session URL (Port 5432):**
   - Digunakan dari komputer lokal Anda untuk menjalankan migrasi skema tabel Alembic.
   - Format:
     ```
     postgresql+asyncpg://postgres:[PASSWORD]@db.[PROJECT_REF].supabase.co:5432/postgres
     ```

### 1.4 Jalankan Migrasi Skema Database dari Komputer Lokal
Jalankan migrasi dari terminal lokal Anda menggunakan connection string Port 5432:

```powershell
cd C:\Projects\brandmuse\apps\api

# Set environment variable migrasi dan jalankan upgrade Alembic
$env:MIGRATION_DATABASE_URL = "postgresql+asyncpg://postgres:[PASSWORD]@db.[PROJECT_REF].supabase.co:5432/postgres"
uv run alembic upgrade head
```

Setelah berhasil, 4 tabel berikut akan otomatis dibuat di Supabase beserta indeks HNSW dan RLS:
- `documents` (metadata panduan brand)
- `chunks` (potongan teks, vektor embedding 1536-dim, dan GIN `tsvector`)
- `generations` (riwayat konsep dan URL gambar permanen)
- `usage_counters` (kuota harian global persisten)

### 1.5 Buat Storage Bucket untuk Aset Gambar
1. Di dashboard Supabase, buka menu **Storage**.
2. Klik **"New Bucket"**.
3. Beri nama: **`brandmuse-images`**.
4. Aktifkan opsi **"Public bucket"** (agar URL gambar dapat diakses dan diunduh langsung oleh browser pengguna).
5. Klik **Save**.
6. Ambil kredensial API:
   - Buka **Project Settings** -> **API**.
   - Salin **Project URL** (contoh: `https://xyzcompany.supabase.co`).
   - Salin **`service_role` secret key** (Kunci rahasia ini hanya boleh diletakkan di environment backend Render, jangan pernah dibagikan ke frontend!).

---

## Langkah 2: Deploy Backend API ke Render

Cloudflare Pages dikhususkan untuk static frontend (SPA), sehingga backend FastAPI dideploy ke layanan container seperti Render.

### 2.1 Buat Web Service di Render
1. Masuk ke [Render Dashboard](https://dashboard.render.com).
2. Klik **"New +"** -> pilih **"Web Service"**.
3. Hubungkan ke repositori GitHub project `brandmuse`.
4. Beri nama service: misalnya `brandmuse-api`.
5. Pilih Region: **Singapore**.
6. Pilih Environment: **Docker**.
7. Konfigurasi direktori build:
   - **Dockerfile Path:** `apps/api/Dockerfile`
   - **Docker Context Directory:** `.` (root repositori)
8. Pilih Instance Type: **Starter** (512 MB RAM).
9. Masukkan Health Check Path: **`/api/health`**.

### 2.2 Atur Environment Variables di Render
Di bagian **Environment Variables**, tambahkan variabel berikut:

| Nama Variabel | Nilai / Contoh | Keterangan |
| :--- | :--- | :--- |
| `PORT` | `8000` | Port aplikasi FastAPI |
| `ENVIRONMENT` | `production` | Mode runtime |
| `DATABASE_URL` | `postgresql+asyncpg://postgres.[REF]:[PASS]@aws-0-ap-southeast-1.pooler.supabase.com:6543/postgres` | Pooler IPv4 Supabase port 6543 |
| `DB_POOLER_MODE` | `true` | Wajib `true` untuk menonaktifkan prepared statements pada pooler port 6543 |
| `FTS_CONFIG` | `english` | Konfigurasi full-text search dictionary |
| `LLM_PROVIDER` | `openai` | Menggunakan OpenAI gpt-4o-mini |
| `EMBEDDING_PROVIDER` | `openai` | Menggunakan text-embedding-3-small |
| `EMBEDDING_DIM` | `1536` | Dimensi vektor OpenAI |
| `IMAGE_PROVIDER` | `stability` *(atau `mock` jika belum punya key)* | Provider pembuatan gambar |
| `OPENAI_API_KEY` | `sk-...` | Kunci API OpenAI |
| `STABILITY_API_KEY` | `sk-...` | Kunci API Stability AI |
| `SUPABASE_URL` | `https://[PROJECT_REF].supabase.co` | URL project Supabase |
| `SUPABASE_SERVICE_ROLE_KEY` | `eyJhbGciOi...` | Service role key untuk upload ke Storage |
| `SUPABASE_STORAGE_BUCKET` | `brandmuse-images` | Nama bucket gambar publik |
| `DAILY_LLM_LIMIT` | `200` | Batas harian proteksi budget |
| `DAILY_IMAGE_LIMIT` | `25` | Batas harian generasi gambar |
| `SESSION_IMAGE_HOURLY_LIMIT` | `5` | Batas kecepatan per sesi pengguna |
| `CORS_ORIGIN` | `http://localhost:5173` *(akan diperbarui setelah Pages jadi)* | Domain frontend yang diizinkan |

10. Klik **"Create Web Service"**.
11. Tunggu hingga build selesai dan status menjadi **Live**. Catat URL backend Render Anda (contoh: `https://brandmuse-api.onrender.com`).

---

## Langkah 3: Deploy Frontend ke Cloudflare Pages

### 3.1 Hubungkan Repositori ke Cloudflare Pages
1. Masuk ke [Cloudflare Dashboard](https://dash.cloudflare.com).
2. Di menu navigasi kiri, pilih **Workers & Pages**.
3. Klik **"Create application"** -> pilih tab **"Pages"** -> klik **"Connect to Git"**.
4. Pilih repositori GitHub `brandmuse`.

### 3.2 Konfigurasi Build Settings
Atur parameter build sebagai berikut:
- **Project name:** `brandmuse` (atau nama pilihan Anda)
- **Production branch:** `main`
- **Framework preset:** `None`
- **Root directory:** `apps/web`
- **Build command:** `bun run build`
- **Build output directory:** `dist`

### 3.3 Konfigurasi Environment Variables di Cloudflare Pages
Buka bagian **Environment variables (advanced)** dan tambahkan:

| Variable | Value | Keterangan |
| :--- | :--- | :--- |
| `BUN_VERSION` | `1.4.4` | Menginstruksikan build image Cloudflare untuk memasang Bun v1.4.4 |
| `VITE_API_URL` | `https://brandmuse-api.onrender.com` | URL Web Service Render dari Langkah 2 |

### 3.4 SPA Deep Route Handling (Otomatis)
Aplikasi menggunakan file `apps/web/public/_redirects` dengan isi:
```
/* /index.html 200
```
File ini akan otomatis disalin ke folder `dist/_redirects` saat build, sehingga ketika pengguna melakukan hard refresh pada rute `/ask`, `/campaign`, atau `/gallery`, Cloudflare Pages tidak akan menampilkan error 404.

### 3.5 Klik "Save and Deploy"
Cloudflare Pages akan mengunduh repositori, mengompilasi kode TypeScript dengan Bun, dan merilis aset web ke CDN global Cloudflare. Catat domain Pages Anda (contoh: `https://brandmuse.pages.dev`).

---

## Langkah 4: Finalisasi CORS & Verifikasi Smoke Test

### 4.1 Perbarui Kredensial CORS di Render
1. Buka kembali dashboard service Render Anda.
2. Pada bagian **Environment Variables**, perbarui nilai `CORS_ORIGIN`:
   ```env
   CORS_ORIGIN=https://brandmuse.pages.dev
   ```
   *(Penting: Masukkan URL lengkap tanpa tanda slash di akhir dan jangan gunakan wildcard `*` demi keamanan).*
3. Klik **"Save Changes"**. Render akan otomatis merestart service.

### 4.2 Uji End-to-End dengan Skrip Smoke Test
Jalankan pengujian end-to-end langsung terhadap URL produksi Render Anda:

```powershell
# Jalankan dari terminal PowerShell lokal:
.\scripts\smoke-test.ps1 -BaseUrl "https://brandmuse-api.onrender.com"

# Atau jika menggunakan Git Bash / Linux:
./scripts/smoke-test.sh https://brandmuse-api.onrender.com
```

Skrip akan memverifikasi 8 tahapan otomatis:
1. `GET /api/health` status 200 dengan security headers aktif.
2. Isolasi sesi via header `X-Session-Id`.
3. Ingesti guideline sampel ke database Supabase.
4. Pengecekan daftar dokumen.
5. Grounded Q&A chat dengan Server-Sent Events (SSE) token streaming.
6. Pembuatan 3 konsep kampanye terstruktur.
7. Pembuatan gambar Stable Diffusion dan upload ke Supabase Storage bucket.
8. Verifikasi gambar tersimpan di galeri sesi.

---

## Tips Operasional & Troubleshooting

1. **Kenapa harus Port 6543 (`DB_POOLER_MODE=true`) untuk Render?**
   Render berkomunikasi melalui jaringan IPv4. Alamat langsung Supabase (port 5432) menggunakan IPv6 murni yang tidak dapat dihubungi langsung dari beberapa cloud host. Transaction Pooler di port 6543 menyediakan gerbang IPv4. Pada port 6543, prepared statements harus dinonaktifkan (`DB_POOLER_MODE=true`) agar asyncpg tidak mengalami error statement cache.
2. **Cold Start Backend (Render Starter Tier):**
   Jika instance Render tidak menerima traffic selama 15 menit, instance akan sleep. Frontend BrandMuse telah dilengkapi detektor bawaan: jika request pertama memakan waktu lebih dari 5 detik, banner informasi otomatis muncul memberi tahu pengguna bahwa server sedang bangun (waking up).
3. **Keamanan Kunci Supabase:**
   Kunci `SUPABASE_SERVICE_ROLE_KEY` memiliki hak akses admin penuh yang dapat bypass RLS. Kunci ini hanya ada di backend Render dan tidak pernah disuntikkan ke frontend Cloudflare Pages.
