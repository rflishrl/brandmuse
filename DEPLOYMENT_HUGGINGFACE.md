# Production Deployment Guide: Hugging Face Spaces (Backend) + Neon + Cloudflare Pages

Panduan lengkap migrasi dan deployment backend **BrandMuse** ke **Hugging Face Spaces** sebagai pengganti Render.

- **Backend Container:** Hugging Face Spaces (**16 GB RAM**, **2 vCPU**, Gradio SDK, Bebas Kartu Kredit)
- **Database Serverless:** Neon.tech (PostgreSQL 16 + pgvector, US East `aws-us-east-1` matching HF Spaces)
- **Object Storage:** Cloudflare R2 (S3-compatible, zero egress fees)
- **Frontend SPA:** Cloudflare Pages (React 18 + Vite + Tailwind, Bun runtime)

---

## 1. Mengapa Hugging Face Spaces Lebih Unggul dari Render?

| Aspek | Render (Free Tier) | Hugging Face Spaces (CPU Basic) |
|---|---|---|
| **Alokasi RAM** | **512 MB** *(rawan OOM saat PDF parsing)* | **16 GB (16.384 MB)** *(32x lebih besar)* |
| **Alokasi CPU** | 0.1 – 0.5 shared vCPU | **2 Dedicated vCPU** |
| **Kartu Kredit** | Tidak wajib | **100% Gratis Tanpa Kartu Kredit** |
| **Port Bawaan** | Dinamis (`$PORT`) | **`7860`** (Gradio / FastAPI) |
| **SDK Pilihan** | - | **Gradio SDK** (100% Free, Secrets Aktif, Tanpa Kartu Kredit) |
| **User Non-Root** | Root / User bebas | **UID 1000** (`user`) |
| **Cold Start** | 30 – 50 detik | 10 – 20 detik (auto-warmed oleh frontend) |
| **Batas Disk** | Ephemeral terbatas | **50 GB Disk** |

---

## 2. Arsitektur Komunikasi

```mermaid
flowchart TD
    User["Browser Pengguna"] -->|HTTPS CDN Edge| Pages["Cloudflare Pages (apps/web: React 18 / Bun)"]
    Pages -->|REST / SSE Streaming + X-Session-Id| HF["Hugging Face Spaces (FastAPI on Gradio SDK Port 7860, 16GB RAM)"]
    HF -->|Pooled Connection / Port 5432 ssl=require| Neon["Neon.tech (PostgreSQL 16 + pgvector)"]
    HF -->|S3 API / boto3 put_object| R2["Cloudflare R2 Bucket (brandmuse-images)"]
    HF -->|Persistent HTTP Connection Pool| AI["Google Gemini 1.5 Flash / OpenAI"]
    User -->|Download Public Assets| R2Public["Cloudflare R2 Public CDN"]
```

---

## 3. Langkah 1: Buat Space Baru di Hugging Face

1. Buka [huggingface.co](https://huggingface.co) dan login / register akun Anda.
2. Di pojok kanan atas, klik avatar profil -> pilih **New Space** (atau buka [huggingface.co/new-space](https://huggingface.co/new-space)).
3. Isi parameter Space:
   - **Space name:** `brandmuse-api` (atau nama pilihan Anda).
   - **License:** `mit` (atau pilihan Anda).
   - **Select the Space SDK:** Pilih **Gradio** *(bukan Docker yang meminta kartu kredit, dan bukan Static yang menonaktifkan Secrets)*.
   - **Space Hardware:** Pilih **CPU basic • 2 vCPU • 16 GB • Free** (gratis tanpa kartu kredit!).
   - **Visibility:** Pilih **Public** (agar API dapat diakses oleh frontend Cloudflare Pages).
4. Klik **Create Space**.

> **Mengapa Memilih SDK Gradio?**
> - **100% Gratis Tanpa Kartu Kredit:** Berbeda dengan Docker SDK yang mewajibkan verifikasi pembayaran/kartu kredit, Gradio SDK sepenuhnya gratis.
> - **Secrets Aktif:** Berbeda dengan Static Spaces yang menonaktifkan Secrets (`Secrets are not available for static Spaces`), Gradio SDK mendukung Secrets dan Environment Variables secara penuh.
> - **FastAPI Natively Supported:** Gradio berjalan di atas Starlette & FastAPI. File [`app.py`](file:///c:/Projects/brandmuse/app.py) di root me-mount backend FastAPI BrandMuse, sehingga semua rute (`/api/health`, `/api/ask`, `/docs`) berjalan normal di port bawaan `7860`.

---

## 4. Langkah 2: Konfigurasi Space Variables & Secrets

Masuk ke menu **Settings** pada Space Anda, scroll ke bagian **Variables and secrets**:

### 4.1 Tambahkan Secrets (Kredensial Sensitif)
Klik **New secret** untuk setiap entri berikut:

| Secret Name | Contoh Nilai | Keterangan |
| :--- | :--- | :--- |
| `DATABASE_URL` | `postgresql+asyncpg://neondb_owner:***@ep-dry-lake-123456-pooler.us-east-1.aws.neon.tech/neondb?ssl=require` | URL Neon pooled connection (Region US East) |
| `GEMINI_API_KEY` | `AIzaSy...` | API Key Google Gemini (LLM & Embeddings) |
| `OPENAI_API_KEY` | `sk-...` | API Key OpenAI (opsional jika pakai Gemini) |
| `STABILITY_API_KEY` | `sk-...` | API Key Stability AI (opsional jika pakai Mock) |
| `R2_ACCOUNT_ID` | `c3a...` | Cloudflare Account ID untuk R2 storage |
| `R2_ACCESS_KEY_ID` | `41f...` | Cloudflare R2 Access Key ID |
| `R2_SECRET_ACCESS_KEY` | `89a...` | Cloudflare R2 Secret Access Key |
| `R2_BUCKET_NAME` | `brandmuse-images` | Nama bucket R2 |
| `R2_PUBLIC_URL` | `https://pub-xxx.r2.dev` | Public URL Cloudflare R2 |

### 4.2 Tambahkan Variables (Konfigurasi Runtime)
Klik **New variable** untuk setiap entri berikut:

| Variable Name | Nilai | Keterangan |
| :--- | :--- | :--- |
| `PORT` | `7860` | Port listening Hugging Face Spaces |
| `ENVIRONMENT` | `production` | Mode produksi |
| `DB_POOLER_MODE` | `true` | Wajib aktif untuk connection pooler Neon / PgBouncer |
| `LLM_PROVIDER` | `gemini` *(atau `openai`)* | Provider orkestrasi bahasa utama |
| `EMBEDDING_PROVIDER` | `gemini` *(atau `openai`)* | Provider embedding vektor |
| `EMBEDDING_DIM` | `1536` | Dimensi vektor pgvector |
| `IMAGE_PROVIDER` | `mock` *(atau `stability`)* | Provider visual image generation |
| `STORAGE_PROVIDER` | `r2` *(atau `local`)* | Backend penyimpanan gambar |
| `CORS_ORIGIN` | `https://brandmuse.pages.dev,http://localhost:5173` | Allowed frontend origins (tanpa trailing slash) |

---

## 5. Langkah 3: Optimasi Database Neon & Migrasi Schema

Agar backend di Hugging Face Spaces memiliki performa query maksimal dan tidak terbebani latensi:

### 5.1 Keselarasan Region (Region Alignment)
- Server Hugging Face Spaces gratis (CPU Basic) berlokasi di **US East** (`us-east-1`, North Virginia).
- Buat database Neon Anda di region **US East (N. Virginia) - `aws-us-east-1`**.
- Menyelaraskan region memangkas latensi koneksi dari **~250 ms (lintas benua)** menjadi **< 10 ms**.

### 5.2 Pengaturan Auto-Suspend Neon
- Masuk ke [neon.tech](https://neon.tech) -> Dashboard -> pilih project `brandmuse-db` -> **Settings** -> **Compute**.
- Set **Auto-suspend delay** ke **30 menit** atau **60 menit** (bukan 5 menit bawaan). Ini mencegah database sering *cold start* saat aplikasi sedang aktif diuji atau dipresentasikan.

### 5.3 Menjalankan Migrasi Schema & Indeks Baru
Jalankan migrasi database dari komputer lokal menggunakan direct connection Neon (tanpa `-pooler`):

```powershell
# Set environment variable DIRECT_URL menggunakan direct connection Neon (port 5432)
$env:DIRECT_URL="postgresql+asyncpg://neondb_owner:PASSWORD@ep-dry-lake-123456.us-east-1.aws.neon.tech/neondb?ssl=require"

# Jalankan migrasi Alembic ke head terbaru (mencakup composite index chunks)
& "apps/api/.venv/Scripts/alembic.exe" upgrade head
```

Migrasi ini otomatis menerapkan:
1. `0001_initial_schema`: Tabel documents, chunks, generations, usage_counters.
2. `0002_add_brand_ontology`: Tabel brand_ontologies untuk certified rules.
3. `0003_db_performance_indexes`: Composite indexes (`idx_chunks_doc_chunk_idx` dan `idx_chunks_doc_page`) untuk kecepatan retrieval chunk dokumen.

---

## 6. Langkah 4: Deploy Kode ke Hugging Face Space

Ada dua opsi untuk menghubungkan kode BrandMuse ke Hugging Face:

### Opsi A: Push Langsung Menggunakan Git Remote (Paling Cepat)

1. Di halaman Hugging Face Space Anda, klik tombol titik tiga di kanan atas -> pilih **Clone repository**.
2. Salin URL git Space Anda (contoh: `https://huggingface.co/spaces/<username>/brandmuse-api`).
3. Di terminal lokal proyek BrandMuse:

```powershell
# Tambahkan Hugging Face sebagai remote git baru
git remote add huggingface https://huggingface.co/spaces/<username>/brandmuse-api

# Push branch main ke Hugging Face
git push huggingface main:main
```
*(Catatan: Saat meminta password, gunakan **Hugging Face User Access Token (Write)** yang dibuat dari [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens)).*

### Opsi B: Sinkronisasi Otomatis dari GitHub via GitHub Actions

Tambahkan GitHub Actions workflow di `.github/workflows/sync-huggingface.yml`:
```yaml
name: Sync to Hugging Face Space
on:
  push:
    branches: [main]

jobs:
  sync:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
          lfs: true
      - name: Push to Hugging Face
        env:
          HF_TOKEN: ${{ secrets.HF_TOKEN }}
        run: git push --force https://<username>:$HF_TOKEN@huggingface.co/spaces/<username>/brandmuse-api main:main
```

---

## 7. Langkah 5: Hubungkan Frontend (Cloudflare Pages)

Setelah build di Hugging Face selesai dan status menunjukkan **Running**:

1. Dapatkan URL publik Space Anda:
   Format bawaan Hugging Face Spaces:
   ```text
   https://<username>-<spacename>.hf.space
   ```
   *(Contoh: `https://rflishrl-brandmuse-api.hf.space`)*.

2. Buka dashboard [Cloudflare Pages](https://dash.cloudflare.com) -> pilih proyek `brandmuse` -> **Settings** -> **Environment variables**.
3. Perbarui variabel `VITE_API_URL`:
   ```env
   VITE_API_URL=https://<username>-brandmuse-api.hf.space
   ```
4. Trigger redeploy frontend: Masuk ke tab **Deployments** -> klik **Retry deployment** (atau push commit baru).

---

## 8. Verifikasi & Smoke Test

Uji kesehatan endpoint Hugging Face secara langsung dari terminal:

```powershell
# 1. Health check & security headers
curl -i https://<username>-brandmuse-api.hf.space/api/health

# 2. Jalankan automated smoke test
.\scripts\smoke-test.ps1 -BaseUrl "https://<username>-brandmuse-api.hf.space"
```

Jika respon status `200 OK` dengan status `"status": "healthy"`, backend BrandMuse Anda telah aktif di Hugging Face Spaces dengan kapasitas RAM 16 GB!
