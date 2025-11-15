![Backend SAJISEHAT](https://github.com/snopflake/sajisehat-backend/raw/main/screenshot/backend_sajisehat_banner.png)

# SAJISEHAT – Backend API 🍽️  
**Layanan OCR & Analisis Gula untuk Aplikasi SAJISEHAT**

Repository ini berisi **backend** untuk aplikasi SAJISEHAT.  
Backend menyediakan endpoint HTTP untuk:

- Menerima **gambar label gizi** (nutrition facts) dari aplikasi mobile.
- Memanggil **Roboflow Workflow** untuk deteksi layout (takaran saji, sajian per kemasan, gula, dll.).
- Melakukan **OCR & parsing teks** label gizi.
- Menghasilkan informasi terstruktur tentang **kandungan gula** yang siap dikonsumsi oleh frontend.

Backend dikembangkan dengan **Flask** dan telah dideploy di platform Render dengan konfigurasi `gunicorn`.

---

## 🔌 Arsitektur Singkat

Alur utama backend:

1. **Frontend** mengirimkan request `POST /scan-nutrition` dengan `image` (form-data).
2. Endpoint memanggil `process_image_with_roboflow()`:
   - Mengirim gambar ke **Roboflow Workflow** (`WORKSPACE_NAME = "nutritionrowstakarangula"`, `WORKFLOW_ID = "custom-workflow-5"`).
   - Mengambil semua bounding box deteksi (gula, takaran saji, dsb.).
   - Menghitung dimensi gambar (lebar, tinggi).
3. Hasil workflow (detections + metadata) diproses dan teks label gizi diparsing oleh `parse_nutrition()`.
4. Backend mengembalikan JSON berisi:
   - `serving_size_gram`
   - `servings_per_pack`
   - `sugar_per_serving_gram`
   - `sugar_per_pack_gram`
   - `raw_text` hasil OCR
   - metadata deteksi (list bounding box + ukuran gambar)

Semua dikemas dalam format respons yang mudah digunakan oleh aplikasi Android SAJISEHAT.

---

## 🧰 Daftar Framework, Library, & Tools yang Digunakan (BACKEND)

### 1. Bahasa & Environment

- **Python 3.11** (lihat `runtime.txt`)
- **Virtual environment** (opsional tapi direkomendasikan)
- **WSGI server**: `gunicorn` (lihat `Procfile`)

### 2. Web Framework & Server

- **Flask**  
  Digunakan sebagai web framework utama untuk mendefinisikan:
  - Aplikasi (`create_app()` di `app/__init__.py`)
  - Blueprint & routing (`app/routes.py`)

- **gunicorn**  
  Digunakan sebagai production server:  
  `web: gunicorn run:app --workers 1 --threads 1 --timeout 300 -b 0.0.0.0:$PORT`

### 3. Computer Vision, OCR, & Model Serving

- **inference-sdk** (Roboflow)  
  - Menghubungkan backend ke Roboflow Serverless API (`InferenceHTTPClient`).
  - Menjalankan **Roboflow Workflow** untuk mendeteksi layout label gizi.

- **OpenCV (opencv-python-headless)**  
  - Memproses gambar (decode dari bytes, crop ROI berdasarkan bounding boxes).
  - Menggabungkan bounding box (`crop_union_bbox`) jika diperlukan.

- **NumPy**  
  - Representasi array/gambar sebagai `ndarray`.
  - Operasi numerik sederhana untuk bounding box & dimensi gambar.

- **Pillow (PIL)**  
  - Membaca gambar dari bytes.
  - Mengambil ukuran gambar jika metadata dari Roboflow kosong.

### 4. HTTP & Utilitas

- **requests**  
  - Utilitas HTTP umum (jika dibutuhkan untuk integrasi tambahan).

- **python-dotenv**  
  - Memuat environment variables dari `.env` saat development (misalnya `ROBOFLOW_API_KEY`).

### 5. Tools Pendukung & Infrastruktur

- **Procfile**  
  - Konfigurasi proses web untuk deployment PaaS (Render / Heroku / dsb.).

- **Git & GitHub**  
  - Version control & kolaborasi.

---

## 📁 Struktur Folder

```text
sajisehat-backend-main/
├─ app/
│  ├─ __init__.py          # Factory pattern Flask: create_app()
│  ├─ routes.py            # Endpoint utama /scan-nutrition
│  ├─ ocr_engine.py        # Orkestrasi proses OCR via Roboflow
│  ├─ roboflow_client.py   # Client Roboflow (InferenceHTTPClient + workflow)
│  ├─ nutrition_parser.py  # Parsing teks label gizi → nilai gula & takaran saji
├─ run.py                  # Entry point Flask app (untuk dev & gunicorn)
├─ requirements.txt        # Dependency backend (UTF-16 encoded)
├─ Procfile                # Konfigurasi gunicorn untuk deployment
├─ runtime.txt             # Versi Python (3.11.9)
└─ .gitignore
