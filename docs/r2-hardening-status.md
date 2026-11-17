# Status Penguatan Integrasi Cloudflare R2 - BrandMuse

Dokumen ini mencatat keputusan arsitektur final, progres per fase, hasil verifikasi dokumentasi resmi, daftar environment variables, urutan cutover produksi, rencana rollback, dan prosedur rotasi rahasia.

---

## 1. Keputusan Arsitektur & Ruang Lingkup Final

1. **Model Bucket Tunggal (`brandmuse`):** Menggunakan satu bucket bernama `brandmuse` (tanpa bucket `-dev` terpisah). Isolasi environment dijaga lewat `R2_KEY_PREFIX` (`brandmuse` untuk produksi, `brandmuse-dev` untuk uji non-produksi, atau `STORAGE_PROVIDER=local` untuk dev offline).
2. **Domain Publik:** Custom domain `https://media-bm.raflisahrul.my.id` (disetel hanya via env `R2_PUBLIC_URL`, tidak di-hardcode di kode/CSP/CORS) terhubung langsung ke bucket `brandmuse` dengan `r2.dev` dalam keadaan **Disabled**.
3. **Format, Varian, & Key Media (Dual WebP Statis via Pillow):**
   - Full: maks sisi `1920 px`, quality `80`, key `<R2_KEY_PREFIX>/generations/<owner>/<uuid>.webp`
   - Thumb: maks sisi `480 px`, quality `78`, key `<R2_KEY_PREFIX>/generations/<owner>/<uuid>-thumb.webp`
   - Metadata objek: `ContentType: image/webp`, `CacheControl: public, max-age=31536000, immutable`.
   - `<owner>`: 16 karakter hex pertama dari HMAC-SHA256 `X-Session-Id` dengan `MEDIA_OWNER_SECRET`.
   - Tanpa `/cdn-cgi/image/` sehingga konsumsi kuota Cloudflare Image Transformations adalah 0 / 5.000 per akun.
4. **PDF Tidak Disimpan di R2:** Upload PDF tetap langsung divalidasi dan di-chunk ke pgvector (`chunks`).
5. **Dual-Read & URL Builder:** Database menyimpan key objek full pada baris baru (tetap mendukung URL absolut legacy `r2.dev` dan `data:` URI pada baris lama). URL dibangun lewat `public_media_url(key)` dan `media_variant_url(key, width)` dengan whitelist lebar `(480, 1920)`.
6. **Penjaga Environment Startup (Fail-Fast):** Saat R2 aktif, `ENVIRONMENT != "production"` mewajibkan `R2_KEY_PREFIX` berakhiran `-dev`; `ENVIRONMENT == "production"` melarang akhiran `-dev` dan mewajibkan `MEDIA_OWNER_SECRET`.
7. **Keputusan Fase 0 yang Disetujui:**
   - **Lifecycle bucket `brandmuse`:** Tidak ada penghapusan otomatis pada prefix `brandmuse/`. Aturan global abort incomplete multipart upload setelah 1 hari, serta aturan hapus 7 hari khusus prefix `brandmuse-dev/`.
   - **Aset statis:** Seluruh logo/ikon sudah SVG inline dan `samples/` dibaca lokal oleh backend untuk pgvector.
   - **Deduplikasi mock:** Ditolak (menghindari overhead `HeadObject` Class B dan berbagi key antarbaris `generations`).
   - **Status bucket lama (`brandmuse-images`):** Sudah dihapus sebelumnya oleh pemilik proyek (tidak ada masa pengamatan 14 hari atau migrasi objek dari bucket lama).
   - **Kuota Tier 2:** Ditunda (Tier 1 sudah mencukupi untuk volume `DAILY_IMAGE_LIMIT`).
   - **Cold start Render:** Timeout klien 90 detik dengan pesan ramah `"Server demo sedang bangun..."`, tanpa retry otomatis pada mutasi `POST /api/images`.

---

## 2. Status Fase

| Fase | Status | Ringkasan |
| :--- | :--- | :--- |
| **Fase 0: Audit** | Selesai | Audit backend, frontend, dokumen, kuota, SSRF, dan verifikasi resmi selesai; keputusan disetujui. |
| **Fase 1: Cloudflare** | Selesai | Bucket `brandmuse` (`APAC`), `r2.dev` disabled, CORS, custom domain `Active`, Cache Rule `cache-media-r2-static`, Image Transformations Sources, WAF Hotlink, Lifecycle, dan Token S3 selesai. |
| **Fase 2: Backend** | Selesai | Konfigurasi, guard prefix, `boto3` `when_required` checksum, Dual WebP Pillow, SSRF guard, kuota Tier 1, `/api/admin/usage`, migrasi Alembic `0004_add_generation_size_bytes` (teruji di Neon), OpenAPI/Orval, dan 80 pytest / ruff / mypy lulus. |
| **Fase 3: Frontend** | Selesai | `GalleryPage` (thumbnail, `<button>`, `<dialog>` light-dismiss + fallback Safari, paginasi), `CampaignPage`, `mutator.ts` (90s timeout), `queryKeys.ts`, dan `apps/web/public/_headers` (CSP tanpa host hardcode); lint/format/typecheck/build lulus. |
| **Fase 4: Migrasi Data** | Selesai (Teruji) | Script `apps/api/scripts/migrate_images_to_shared_bucket.py` + unit test (84 pytest lulus); uji `--dry-run` & `--apply` terhadap Neon selesai dengan `total_candidates: 0`. |
| **Fase 5: Cutover & Dokumen** | Selesai (Siap Cutover Produksi) | `docs/switch-public-domain.md`, pembaruan `README.md`, `DEPLOYMENT_NEON_R2.md`, `DEPLOYMENT_RENDER.md`, `docker-compose.yml`, `.env.example`, rencana rollback, dan prosedur rotasi rahasia selesai. Menunggu deploy Render/Pages & verifikasi live akhir. |

---

## 3. Hasil `[VERIFIKASI]` Resmi

| Topik | Hasil Verifikasi | Dampak Implementasi |
| :--- | :--- | :--- |
| **`boto3` / `botocore` checksum** | `uv.lock` mengunci `boto3==1.43.124` & `botocore==1.43.124` dengan default `when_supported`. | Disetel eksplisit `request_checksum_calculation="when_required"` dan `response_checksum_validation="when_required"` di `Config`. |
| **Mock engine** | `MockImageProvider` mengabaikan prompt dan menghasilkan 3 output tetap per `aspect_ratio`. | Dedup mock tidak diimplementasikan. |
| **Urutan `usage_counters`** | Sebelumnya di-increment sebelum generasi/upload. | Diperbaiki: cek kuota sebelum generate, increment hanya setelah R2 & DB berhasil. |
| **Host penyedia gambar** | Stability memakai JSON base64; Replicate mengembalikan URL `replicate.delivery` / `*.replicate.delivery`. | Validasi HTTPS, allowlist host, anti-IP privat, tolak redirect lintas host, batas unduhan 15 MB. |
| **Domain `.my.id` & nameserver** | `.my.id` didukung sebagai zona Cloudflare (vanity NS hanya Business/Enterprise). | Memakai nameserver standar `*.ns.cloudflare.com`. |
| **Cache Custom Domain & Class B** | `r2.dev` tidak mendukung Cache Rules/WAF. Custom domain + Cache Rule menghasilkan `cf-cache-status: HIT` dan tidak dihitung Class B. | Cache Rule `cache-media-r2-static` aktif untuk `media-bm.raflisahrul.my.id`. |
| **Hotlink Protection** | WAF Custom Rules paket Free mendukung filter `http.referer` (tetap bisa dipalsukan klien non-browser). | WAF Custom Rule memblokir `Referer` luar yang tidak kosong. |
| **Location Hint & Notifikasi R2** | Hint `apac` permanen saat pembuatan bucket. Notifikasi usage-based billing hanya untuk akun Pay-as-you-go. | Bucket `brandmuse` dibuat di APAC; pemantauan lewat R2 Metrics dan `GET /api/admin/usage`. |
| **Cold start Render** | Free Web Service spin down setelah 15 menit tidak aktif (~30-90 dtk). | Polling `/api/health` + banner warming up + timeout klien 90 detik di `mutator.ts`. |

---

## 4. Daftar Environment Variables

### Backend (`apps/api` / Render)

| Variabel | Status | Nilai Produksi (Render) | Nilai Non-Produksi / Uji |
| :--- | :--- | :--- | :--- |
| `ENVIRONMENT` | Ada | `production` | `development` |
| `STORAGE_PROVIDER` | Ada | `r2` | `local` atau `r2` |
| `R2_ACCOUNT_ID` | Ada | `<32-char-hex>` | `<32-char-hex>` |
| `R2_ACCESS_KEY_ID` | Ada | Token `brandmuse-token` | Token `brandmuse-token` |
| `R2_SECRET_ACCESS_KEY` | Ada | Rahasia token `brandmuse-token` | Rahasia token `brandmuse-token` |
| `R2_BUCKET_NAME` | Diperbarui | `brandmuse` | `brandmuse` |
| `R2_KEY_PREFIX` | **Baru** | `brandmuse` | `brandmuse-dev` |
| `R2_PUBLIC_URL` | Diperbarui | `https://media-bm.raflisahrul.my.id` | `https://media-bm.raflisahrul.my.id` (atau kosong saat `local`) |
| `R2_APP_QUOTA_MB` | **Baru** | `2048` | `2048` |
| `ADMIN_TOKEN` | **Baru** | `<64-char-hex-acak>` | `<64-char-hex-acak>` |
| `MEDIA_OWNER_SECRET` | **Baru** | `<64-char-hex-acak>` | `<64-char-hex-acak>` |
| `DAILY_IMAGE_LIMIT` | Ada | `25` | `25` |
| `SESSION_IMAGE_HOURLY_LIMIT` | Ada | `5` | `5` |

### Frontend (`apps/web` / Cloudflare Pages)

| Variabel | Status | Nilai |
| :--- | :--- | :--- |
| `VITE_API_URL` | Ada | `https://brandmuse-13ck.onrender.com` |

---

## 5. Urutan Cutover Produksi & Verifikasi Akhir (Fase 5)

1. **Pastikan Cloudflare siap** (bucket `brandmuse`, `r2.dev` disabled, custom domain `Active`, Cache Rule, WAF Hotlink, CORS, Lifecycle, Token S3).
2. **Atur Environment Variables di Render** (tabel bagian 4 di atas, jangan menimpa variabel lain yang sudah berjalan) lalu deploy backend terbaru.
3. **Verifikasi skema DB produksi** (pastikan `alembic current` di `MIGRATION_DATABASE_URL` produksi berada di `0004_add_generation_size_bytes`; jalankan `uv run alembic upgrade head` bila belum).
4. **Jalankan migrasi data produksi (jika masih ada baris lama):**
   - `uv run python scripts/migrate_images_to_shared_bucket.py --source-host <OLD_R2_HOST>` (dry-run)
   - Jika ada kandidat: ulangi dengan `--apply`.
5. **Deploy frontend (`apps/web`) ke Cloudflare Pages** agar perubahan galeri, timeout 90 detik, dan `_headers` aktif.
6. **Verifikasi pasca-deploy:**
   - Gambar baru dari `POST /api/images` berformat `.webp` dan muncul dari `R2_PUBLIC_URL` (`https://media-bm.raflisahrul.my.id/brandmuse/generations/<owner>/<uuid>.webp`).
   - Dua `curl -I` berturut-turut ke URL gambar menunjukkan `cf-cache-status: HIT` dan `cache-control: public, max-age=31536000, immutable` pada permintaan kedua.
   - `GET /api/admin/usage` dengan `Authorization: Bearer <ADMIN_TOKEN>` mengembalikan JSON kuota dengan `200 OK`, dan tanpa token mengembalikan `401`.
   - Simulasikan ambang kuota di lingkungan uji (`R2_APP_QUOTA_MB` kecil sementara atau unit test) dan pastikan pesan ramah muncul tanpa angka internal.
   - Uji pengalihan `R2_PUBLIC_URL` di lingkungan uji mengubah URL respons API tanpa perubahan kode.
7. **Selesai cutover:** Bucket lama `brandmuse-images` sudah dihapus oleh pemilik proyek sebelumnya, sehingga tidak perlu menunggu masa pengamatan 14 hari.

---

## 6. Rencana Rollback

Karena bucket lama `brandmuse-images` sudah dihapus oleh pemilik proyek sebelumnya:
1. Jika perlu rollback aplikasi di **Render**, lakukan rollback/redeploy ke commit atau Docker image sebelumnya sambil tetap mempertahankan `R2_BUCKET_NAME=brandmuse`.
2. Baris lama yang mungkin tersimpan sebagai URL absolut atau `data:` URI tetap terbaca berkat mekanisme **dual-read** pada `public_media_url()` dan `media_variant_url()`.
3. Kolom `size_bytes` pada tabel `generations` bersifat `nullable=True`, sehingga aplikasi versi lama maupun baru tetap berjalan tanpa error skema (bila benar-benar perlu menurunkan skema, jalankan `uv run alembic downgrade 0003_db_performance_indexes` pada target terkait).

---

## 7. Prosedur Rotasi Rahasia

1. **Token R2 (`R2_ACCESS_KEY_ID` / `R2_SECRET_ACCESS_KEY`):**
   - Buat token baru (`brandmuse-token-v2`, **Object Read & Write**, scope khusus bucket `brandmuse`) di Cloudflare Dashboard -> R2 -> Manage R2 API Tokens.
   - Perbarui `R2_ACCESS_KEY_ID` dan `R2_SECRET_ACCESS_KEY` di Render Environment Variables dan tunggu restart.
   - Verifikasi `POST /api/images` berhasil mengunggah objek baru.
   - Revoke / hapus token lama di Cloudflare Dashboard.
2. **`ADMIN_TOKEN`:**
   - Generate token acak baru minimal 32 byte (PowerShell / `openssl rand -hex 32`).
   - Perbarui `ADMIN_TOKEN` di Render Environment Variables.
   - Verifikasi token lama ditolak (`401`) dan token baru diterima (`200`) oleh `GET /api/admin/usage`.
3. **`MEDIA_OWNER_SECRET`:**
   - Generate secret acak baru minimal 32 byte dan perbarui di Render Environment Variables.
   - **Catatan dampak:** Merotasi `MEDIA_OWNER_SECRET` mengubah segmen `<owner>` pada objek baru yang dibuat setelah rotasi; seluruh objek lama di database tetap valid dan tetap dapat diakses karena key lengkapnya tersimpan di kolom `generations.image_url`.
