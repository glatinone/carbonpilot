# CarbonPilot — Brief untuk Pitch Deck & Video Presentasi (Claude Opus 5.5)

Status: draft awal untuk sesi pembuatan deck & video bersama Claude Opus 5.5.
Konteks: Google Cloud AI Builder Cup 2026 — JAPAC hackathon oleh Hack2skill.
Deadline submission: 18 Okt 2026. Evaluasi: 19 Okt — 6 Nov. Finalis: 7 Nov, Grand Finale Singapore 4 Des.

---

## 1. Produk dalam satu kalimat (wajib ada di cover & closing)

"AI carbon decision engine untuk JAPAC: dari data operasional yang berantakan menjadi
tindakan dekarbonisasi yang terukur, finansial-aware, dan setiap angkanya bisa dilacak
ke mesin kalkulasi — bukan ke model bahasa."

Tagline existing: "From carbon accounting to carbon action."
Alur inti: Measure → Diagnose → Simulate → Act (enam layar, satu loop).

## 2. Mengapa pitch ini beda (jangan oversell)

- Bukan "platform AI karbon pertama" — pasar sudah ramai (Watershed, Persefoni, Sweep, SINAI).
- Klaim yang dapat dipertahankan:
  1. Model bahasa TIDAK PERNAH menghasilkan angka karbon. Mesin deterministik menghitung,
     LLM memilih analisis dan menjelaskan. Ini kontrak pada output, bukan sekadar cara.
  2. Lokasi grid = variabel keputusan. 20 grid JAPAC, satu basis dokumentasi, CC BY 4.0.
  3. Satu proses. Tidak ada CORS layer, tidak ada procurement project.
  4. Trade-off ada di halaman: matriks + MAC curve + kalimat perbandingan dihitung mesin.
  5. Verifiable: 138+ tes, preflight yang gagal saat key diam-diam mati.

## 3. Anchor numbers (sudah diverifikasi di instance deployed)

- Footprint: 11,208 tCO2e/thn · 168 record · 12 bulan
- Scope: 1/2/3 = 11,6% / 27,3% / 61,1% · Scope 3 terbesar
- Cloud: 271 t (2,4% karbon) tapi 33% dari spend — cerita keputusan, bukan ukuran bar
- Load: 4.304.333 kWh → Indonesia 3.036 tCO2e (rank 19/20, coal 69%) vs NZ 399 tCO2e
- Demo hero: "turun 15% tanpa naik biaya" → hasil 33,8% turun + hemat $775K/thn,
  342 skenario feasible dari 2.098 dievaluasi
- Kredibilitas: 138+ tes pytest · 13 tools · preflight 13 OK

## 4. Story arc (11 slide, dari deck submission yang sudah ada)

1. Cover — masalah dulu, bukan produk: "Companies can already measure. They still cannot decide."
2. Problem — persona: sustainability/ops manager; reporting = pandangan ke belakang;
   carbon dan money diputuskan terpisah.
3. Finding — lokasi = variabel keputusan (3,036 vs 399 t).
4. Solution — loop 4 langkah.
5. Rule — model tidak pernah menghasilkan angka karbon.
6. Demo — constraint search: 15% → 33,8% & −$775K, 342 dari 2.098.
7. Tech — 13 tools, first turn forced, cited retrieval, satu proses.
8. Verified — 138 tes, preflight.
9. Market — akui kategori dulu, lalu klaim sempit.
10. Impact & roadmap — 20 grid CC BY 4.0, EN/ID, pattern engine-over-model.
11. Closing — loop + URL + "submitted to AI Builder Cup 2026".

## 5. Angka-angka baru yang HARUS masuk deck & video (fitur baru, baru selesai)

- MAC curve: grafik standar industri; tindakan di bawah 0 $/t = menghemat uang.
  Data: tiap rekomendasi sudah punya carbon_impact_t, cost_impact_usd, effort, confidence.
- Carbon pricing scenario: masukkan harga $/t → engine hitung ulang seluruh footprint
  dan re-rank tindakan berdasarkan net cost = cost_impact_usd + (carbon_impact_t × price).
  Verdict deterministik 1 kalimat.
- Repo kini PUBLIK: https://github.com/glatinone/carbonpilot
- Subdomain live: https://rakazo-civo.tail1b51ed.ts.net:8443

Skenario demo baru yang disarankan untuk video:
- Buka MAC curve → tunjuk titik "menghemat uang sekaligus memotong karbon"
- Masukkan harga karbon $50–100/ton → re-order tindakan → verdict mesin
- Tutup dengan constraint search 15% (story yang sudah ada)

## 6. Video presentasi: brief teknis

- Panjang: di bawah 3 menit (persyaratan resmi). Rekomendasi ~2:30.
- Bahasa: Indonesia atau Inggris? Rekomendasi Inggris dengan subtitle/versi ID,
  karena juri JAPAC. (Await konfirmasi singkat Kiell.)
- Format: rekaman walkthrough instance live (wajib real, bukan mockup).
- Struktur video (detik):
  0:00-0:20 Problem → 0:20-0:45 Product + finding lokasi → 0:45-1:15 Loop Measure→Act
  → 1:15-1:45 MAC curve + carbon pricing (baru) → 1:45-2:15 Constraint search hero result
  → 2:15-2:30 Close (URL + repo publik).
- Video sebaiknya direkam ulang / di-reshoot karena fitur baru (MAC curve, pricing)
  belum ada di rekaman lama; atau buat video kedua pendek untuk fitur baru dan jelaskan
  di deskripsi Devpost.
- Rekomendasi: 1 video utama (walkthrough lengkap, ~2:30) + 1 video fitur baru (60-90s).

## 7. Yang SUDAH dikerjakan di repo (status terkini — ringkas)

- Deploy persistent: systemd enabled + Restart=always + auto-start; live kembali.
- Repo publik: github.com/glatinone/carbonpilot.
- Bilingual constraint message: teks constraint search kini per-locale (EN/ID),
  struktur aditif message_key + counts, tanpa perubahan kontrak API.
- Per-page tab title: 6 rute unik (valid static export).
- scripts/deploy.sh: idempotent, health check ganda.
- MAC curve + carbon pricing: (status: dalam pengerjaan paralel, subagent).
  Verifikasi ikut di sini setelah selesai: pytest, tsc, build, preflight vs deployed.

## 8. Perintah verifikasi yang dipakai (bisa langsung dipakai di sesi Claude)

- cd backend && ./.venv/Scripts/python.exe -m pytest -q
- cd frontend && npx tsc --noEmit
- cd frontend && npm run build
- cd backend && ./.venv/Scripts/python.exe -m scripts.preflight --base-url https://rakazo-civo.tail1b51ed.ts.net:8443  (linux: scripts/preflight.py)

## 9. Constraints gaya (penting untuk Claude Opus)

- Anti "AI slop": tanpa gradient dekoratif, tanpa glow, tanpa kartu blur membulat.
- Desain "Ledger": garis ramping, warna hanya untuk state.
- Font: Source Serif 4 (menyatakan), Inter (menjelaskan), IBM Plex Mono (mengukur).
- Simpulan jujur: jangan klaim "first AI carbon platform"; batasi klaim pada engine-over-model.
