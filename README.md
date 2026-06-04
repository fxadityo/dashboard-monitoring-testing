# Dashboard Monitoring UAT

Repo ini berisi dashboard monitoring UAT yang saya buat sebagai **eksperimen pakai OpenAI Codex** — jadi ini bukan dashboard "production-ready", melainkan lebih ke proof of concept: bisa nggak Codex bantu QA Engineer bikin tooling monitoring dari nol?

Hasilnya cukup menarik. Struktur kode bisa di-generate dengan cepat, meski tetap butuh banyak review dan penyesuaian manual sebelum bisa dipakai tim.

![Dashboard Preview](main/dashboard-preview.png)

---

## Cara Kerjanya

Inti dari repo ini ada di `generate_dashboard.py`. File ini yang bertugas baca semua Excel di folder `data/`, proses datanya, dan siapin output-nya — baik ke Streamlit maupun ke FastAPI. Jadi kedua "tampilan" itu sebenarnya ngambil data dari tempat yang sama.

```
data/*.xlsx
     │
     ▼
generate_dashboard.py   ← otak utama: baca Excel, proses, siapin data
     │
     ├──► streamlit_app.py   → dashboard interaktif (yang ini yang dipakai tim)
     │
     └──► app.py (FastAPI)   → serve HTML + endpoint /api/dashboard-data
```

Kenapa ada FastAPI kalau Streamlit sudah ada? Ini bagian dari konsep yang saya coba — FastAPI berperan sebagai **data connector layer** yang terpisah dari tampilan. Mirip konsep MCP (Model Context Protocol), di mana ada satu "pintu" khusus untuk data, dan tampilan tinggal consume dari sana. Untuk keperluan sehari-hari tim, Streamlit-nya yang langsung dipakai.

---

## Struktur Folder

```
dashboard-monitoring-testing/
│
├── data/                  ← taruh semua file Excel di sini
├── output/                ← hasil generate HTML (auto, jangan diedit manual)
├── app.py                 ← FastAPI (data connector layer)
├── generate_dashboard.py  ← core logic, dipakai app.py dan streamlit_app.py
├── streamlit_app.py       ← dashboard utama yang diakses tim
└── requirements.txt
```

---

## Source Data: Excel

Data UAT disimpan dalam file `.xlsx` di folder `data/`. Setiap file = satu project. Kalau ada project baru, tinggal tambah file Excel baru di folder yang sama.

### Penamaan File

Nama file langsung jadi nama project di dashboard, jadi pastikan formatnya konsisten:

```
[KODE] - [Nama Project].xlsx
```

Contoh: `UAT Scenarios - PRJ20260012 - Leadsync dan CRM.xlsx`

### Sheet yang Dibaca

Dashboard hanya baca sheet bernama **`Dashboard Progress`**. Sheet lain di workbook yang sama akan diabaikan.

### Kolom yang Dibutuhkan

| Kolom | Keterangan |
|---|---|
| `No` | Nomor urut |
| `Scenario ID` | ID skenario — wajib ada, baris tanpa ini dibuang otomatis |
| `Total Task` | Total task dalam skenario |
| `Task Done` | Task yang sudah selesai |
| `Status` | Status skenario (`Done`, `In Progress`, dll) |
| `PIC` | Nama tester |
| `Notes` | Catatan, referensi bug, dll |

### Update Data

Karena source datanya di-manage manual lewat Git, kalau ada update di Excel — entah itu nambahin skenario baru, update status, atau update notes — perlu di-commit dan push ke repo:

```bash
git add data/
git commit -m "update UAT data - [nama project] [tanggal/sprint]"
git push
```

Setelah push, dashboard otomatis baca data terbaru karena tidak ada cache — setiap kali dashboard dibuka, Excel langsung dibaca ulang dari disk.

> Ini memang keterbatasan dari pendekatan sekarang. Ke depannya idealnya data bisa pull langsung dari test management tool tanpa perlu manual push. Tapi untuk fase eksperimen ini, cukup.

---

## Menjalankan Dashboard

Install dulu dependency-nya:

```bash
pip install -r requirements.txt
```

Lalu jalankan Streamlit:

```bash
streamlit run streamlit_app.py --server.address 0.0.0.0
```

Flag `--server.address 0.0.0.0` penting supaya dashboard bisa diakses dari device lain, bukan cuma dari mesin yang menjalankannya. Setelah Streamlit jalan, cek di terminal — akan ada info URL-nya termasuk network URL yang bisa dibagikan ke anggota tim di jaringan yang sama.

---

## Apa yang Tampil di Dashboard

**Filter (sidebar kiri)**
Bisa filter by Project, PIC, Status, dan ada kolom search bebas untuk cari berdasarkan Scenario ID atau Notes.

**KPI di atas**
- Progress Task — persentase task selesai dari total
- Scenario Done — berapa skenario yang sudah berstatus Done
- Total Scenario — total skenario di filter aktif
- Data Terakhir — timestamp terakhir file Excel dimodifikasi

**Charts**
Empat pie chart: distribusi progress task, distribusi status, task per PIC, dan scenario per project.

**Tabel detail**
List lengkap semua skenario sesuai filter yang aktif, lengkap dengan kolom source file dan waktu modifikasinya.

---

## Catatan Pakai Codex

Codex lumayan bantu di bagian-bagian boilerplate yang biasanya makan waktu: struktur FastAPI, logika baca multi-file Excel dengan pandas, sampai setup komponen Streamlit. Tapi ada beberapa hal yang tetap perlu dikerjakan manual:

- Validasi edge case di data (baris kosong, kolom tidak sesuai format)
- Fine-tuning filter dan logika agregasi supaya sesuai kebutuhan spesifik
- Penyesuaian tampilan Streamlit

Kesimpulan pribadi: Codex efektif buat bikin kerangka cepat, tapi tetap butuh QA Engineer yang paham konteks UAT-nya untuk review dan juga validasi output-nya.

---

## Author

**Adityo Nugroho** — Quality Assurance Tester
