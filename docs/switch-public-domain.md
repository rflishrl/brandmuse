# Panduan Pengalihan Domain Publik Media (`R2_PUBLIC_URL`)

BrandMuse menerapkan prinsip **satu titik pengalihan** untuk host media publik:
- Database (`generations.image_url`) menyimpan **key objek** pada baris baru (mis. `brandmuse/generations/<owner>/<uuid>.webp`) dan tetap mendukung dual-read URL absolut legacy (`https://pub-...r2.dev/...`).
- Seluruh URL publik (`url`, `image_url`, dan `thumbnail_url`) dibangun di backend lewat `public_media_url(key)` dan `media_variant_url(key, width)` yang hanya membaca `R2_PUBLIC_URL`.
- Frontend (`apps/web`) tidak meng-hardcode host media di kode TSX, konfigurasi Orval, maupun header keamanan (`apps/web/public/_headers` memakai `img-src 'self' data: blob: https:`).

> Catatan: Subdomain `r2.dev` hanya boleh dipakai untuk pengujian sementara / dev dan tidak mendukung Cache Rules atau WAF Custom Rules Cloudflare. Produksi wajib memakai Custom Domain pada bucket `brandmuse`.

---

## Langkah Mengganti Hostname / Domain Publik (Tanpa Ubah Kode)

1. **Hubungkan domain baru di Cloudflare R2:**
   - Buka Cloudflare Dashboard -> **R2** -> bucket `brandmuse` -> **Settings** -> **Custom Domains** -> **Add**.
   - Masukkan subdomain baru (mis. `media.<NEW_DOMAIN>`) pada zona Cloudflare yang sudah aktif, lalu tunggu status **Active / Enabled**.
2. **Salin aturan zona ke domain baru:**
   - **Cache Rule:** `http.host eq "media.<NEW_DOMAIN>"` -> **Eligible for cache**, Edge TTL **Override origin 1 year**, Browser TTL **Respect origin**.
   - **WAF Hotlink Rule (jika diperlukan):** perbarui daftar `http.host` dan `http.referer` agar tetap mengizinkan `Referer` kosong, `brandmuse.pages.dev`, `localhost`, dan `<NEW_DOMAIN>`.
   - **CORS bucket `brandmuse`:** pastikan origin frontend yang mengakses `media.<NEW_DOMAIN>` tercantum di `AllowedOrigins`.
3. **Ubah `R2_PUBLIC_URL` di Render:**
   - Buka Render Dashboard -> service `brandmuse-api` -> **Environment**.
   - Ubah `R2_PUBLIC_URL` menjadi `https://media.<NEW_DOMAIN>` (tanpa trailing slash).
   - Simpan perubahan dan tunggu Render selesai restart/redeploy. Tidak perlu rebuild frontend di Cloudflare Pages.
4. **Verifikasi cutover:**
   - Panggil `POST /api/images` atau `GET /api/images` dan pastikan `url` / `image_url` / `thumbnail_url` sudah mengarah ke `https://media.<NEW_DOMAIN>/brandmuse/generations/...`.
   - Uji cache Cloudflare dengan dua permintaan berturut-turut:
     ```bash
     curl -I "https://media.<NEW_DOMAIN>/brandmuse/generations/<owner>/<uuid>.webp"
     curl -I "https://media.<NEW_DOMAIN>/brandmuse/generations/<owner>/<uuid>.webp"
     ```
     Permintaan kedua harus menampilkan `cf-cache-status: HIT` dan `cache-control: public, max-age=31536000, immutable`.
5. **Putuskan domain lama setelah aman:**
   - Setelah trafik stabil pada domain baru, hapus custom domain lama dari **Settings -> Custom Domains** di bucket `brandmuse`.
