# Production Deployment Guide: Render (Backend) + Neon + Cloudflare R2 + Cloudflare Pages

Panduan lengkap deployment backend **BrandMuse** ke **Render (Free Web Service)** bersama serverless database Neon dan object storage Cloudflare R2.

- **Backend API:** Render Web Service (FastAPI Python 3.12, Uvicorn, Free Tier, Tanpa Kartu Kredit)
- **Database Serverless:** Neon.tech (PostgreSQL 16 + pgvector, Pooled Connection)
- **Object Storage:** Cloudflare R2 (S3-compatible, 10 GB free tier, zero egress fees)
- **Frontend SPA:** Cloudflare Pages (React 18 + Vite + Tailwind, Bun runtime)

---

## 1. Arsitektur Komunikasi

```mermaid
flowchart TD
    User["Browser Pengguna"] -->|HTTPS CDN Edge| Pages["Cloudflare Pages (apps/web: React 18 / Bun)"]
    Pages -->|REST / SSE Streaming + X-Session-Id| Render["Render Web Service (FastAPI / Uvicorn Port Dinamis)"]
    Render -->|Pooled Connection / Port 5432 ssl=require| Neon["Neon.tech (PostgreSQL 16 + pgvector)"]
    Render -->|S3 API / boto3 put_object| R2["Cloudflare R2 Bucket (brandmuse-images)"]
    Render -->|Persistent HTTP Connection Pool| AI["Google Gemini 1.5 Flash / OpenAI"]
    User -->|Download Public Assets| R2Public["Cloudflare R2 Public CDN"]
```

---

## 2. Parameter Web Service di Render

### 2.1 Konfigurasi Utama
1. Buka [dashboard.render.com](https://dashboard.render.com) dan login dengan akun GitHub Anda.
2. Klik tombol **New +** -> pilih **Web Service**.
3. Hubungkan repositori **`brandmuse`**.
4. Isi parameter service:
   - **Name:** `brandmuse-api` (atau nama unik pilihan Anda, menghasilkan domain `https://brandmuse-13ck.onrender.com`).
   - **Region:** Singapore (`ap-southeast-1`) atau Oregon / Ohio.
   - **Branch:** `main`
   - **Root Directory:** `apps/api`
   - **Runtime:** **Python 3**
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
   - **Instance Type:** Pilih **Free** ($0/month, Tanpa Kartu Kredit).

---

## 3. Konfigurasi Environment Variables di Render

Masuk ke menu service Anda di Render -> tab **Environment**, masukkan variabel berikut:

### 3.1 Kredensial Sensitif (Secrets)

| Key | Contoh Nilai | Keterangan |
| :--- | :--- | :--- |
| `DATABASE_URL` | `postgresql+asyncpg://neondb_owner:***@ep-dry-lake-123456-pooler.us-east-1.aws.neon.tech/neondb?ssl=require` | URL Neon pooled connection |
| `GEMINI_API_KEY` | `AIzaSy...` | API Key Google Gemini (LLM & Embeddings) |
| `OPENAI_API_KEY` | `sk-...` | API Key OpenAI (opsional jika menggunakan Gemini) |
| `STABILITY_API_KEY` | `sk-...` | API Key Stability AI (opsional jika menggunakan mock) |
| `R2_ACCOUNT_ID` | `c3a...` | Cloudflare Account ID untuk storage R2 |
| `R2_ACCESS_KEY_ID` | `41f...` | Cloudflare R2 Access Key ID |
| `R2_SECRET_ACCESS_KEY` | `89a...` | Cloudflare R2 Secret Access Key |
| `R2_BUCKET_NAME` | `brandmuse-images` | Nama bucket Cloudflare R2 |
| `R2_PUBLIC_URL` | `https://pub-xxx.r2.dev` | Public URL Cloudflare R2 |

### 3.2 Variabel Runtime

| Key | Nilai | Keterangan |
| :--- | :--- | :--- |
| `ENVIRONMENT` | `production` | Mode produksi |
| `DB_POOLER_MODE` | `true` | Wajib aktif untuk connection pooler Neon |
| `LLM_PROVIDER` | `gemini` | Provider bahasa utama |
| `EMBEDDING_PROVIDER` | `gemini` | Provider embedding vektor |
| `EMBEDDING_DIM` | `1536` | Dimensi vektor embedding |
| `IMAGE_PROVIDER` | `mock` *(atau `stability`)* | Provider visual image generation |
| `STORAGE_PROVIDER` | `r2` *(atau `local`)* | Backend penyimpanan gambar |
| `CORS_ORIGIN` | `https://brandmuse.pages.dev,http://localhost:5173` | Allowed frontend origins (tanpa trailing slash) |

---

## 4. Hubungkan Frontend di Cloudflare Pages

1. Buka [Cloudflare Dashboard](https://dash.cloudflare.com) -> **Workers & Pages** -> pilih project `brandmuse`.
2. Masuk ke **Settings** -> **Environment variables**.
3. Perbarui variabel `VITE_API_URL`:
   ```text
   VITE_API_URL=https://brandmuse-13ck.onrender.com
   ```
4. Simpan, lalu pada tab **Deployments** klik **Retry deployment** (atau push commit baru).

---

## 5. Perilaku Cold-Start pada Free Tier Render

* **Auto-Sleep:** Jika tidak ada request selama 15 menit, Render akan menidurkan kontainer (*spin down*) untuk menghemat resource.
* **Auto-Wakeup:** Saat request pertama masuk, server akan bangun otomatis dalam waktu **~20–30 detik**.
* **UI Feedback:** Frontend BrandMuse sudah dilengkapi indikator status otomatis (`isServerWarmingUp`) yang menampilkan banner elegan saat server sedang bangun, sehingga pengguna mengetahui proses cold start tanpa menganggap aplikasi mengalami error.

---

## 6. Verifikasi & Smoke Test

Uji endpoint langsung dari terminal atau browser:

```bash
# 1. Health check & status database
curl https://brandmuse-13ck.onrender.com/api/health

# Respon sukses:
# {"status":"ok","database":"connected","providers":{"llm":"gemini","embeddings":"gemini","image":"mock"}}

# 2. Interactive OpenAPI Documentation
# Buka di browser: https://brandmuse-13ck.onrender.com/docs
```
