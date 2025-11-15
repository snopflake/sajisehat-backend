[![Banner SAJISEHAT Backend](https://github.com/snopflake/sajisehat-backend/raw/main/screenshot/backend_sajisehat_banner.png)](https://github.com/snopflake/sajisehat-backend/raw/main/screenshot/backend_sajisehat_banner.png)

# SAJISEHAT – Backend API 🍽️  
**Layanan Deteksi Layout Label Gizi (Object Detection) untuk Aplikasi SAJISEHAT**

Backend ini merupakan **layanan REST API** yang digunakan oleh aplikasi Android **SAJISEHAT** untuk:

- Menerima **gambar label gizi** dari aplikasi mobile  
- Memanggil **Roboflow Workflow** untuk mendeteksi struktur layout label gizi  
- Mengembalikan **koordinat objek penting** (takaran saji, sajian per kemasan, dan total gula)  
- Menyediakan data bounding box yang akan digunakan frontend untuk menjalankan **OCR** menggunakan ML Kit Text Recognizer pada area yang tepat  

> 💡 Catatan penting:  
> **Backend TIDAK melakukan OCR dan TIDAK melakukan parsing nilai gizi.**  
> OCR dan parsing angka (takaran saji, sajian per kemasan, total gula) dilakukan **sepenuhnya di Android** menggunakan ML Kit, berdasarkan bounding box yang dikirim dari backend.

Backend dikembangkan menggunakan **Flask**, dan dideploy di **Render** menggunakan `gunicorn`.

---

## 🧩 Tujuan & Peran Backend

### Masalah yang Ingin Dipecahkan

- Label gizi biasanya berisi banyak teks (bahan, klaim marketing, informasi pabrik, dll.) sehingga OCR mentah sering:
  - salah baca posisi,
  - tertangkap teks yang tidak relevan,
  - menghasilkan noise yang menyulitkan parsing.
- Diperlukan mekanisme untuk **mengidentifikasi area penting** pada label gizi, khususnya:
  - **Takaran saji**
  - **Jumlah sajian per kemasan**
  - **Total gula**

### Peran Backend SAJISEHAT

1. **Mendeteksi layout label gizi melalui Roboflow**  
   Backend menemukan dan menentukan **lokasi tiga objek utama** (takaran saji, sajian per kemasan, total gula) di dalam gambar.

2. **Mengirim bounding box ke frontend Android**  
   Frontend kemudian menjalankan OCR **hanya pada area yang relevan**, sehingga:
   - Akurasi OCR meningkat  
   - Noise teks lain berkurang drastis  

3. **Menjadi perantara antara aplikasi dan Roboflow Workflow**  
   - Frontend hanya perlu mengirim gambar ke backend.  
   - Backend yang mengurus pemanggilan Roboflow dan merapikan hasil deteksi menjadi format JSON yang mudah dikonsumsi.

---

## 🔌 Alur Kerja Utama Backend

### Endpoint Utama: `POST /scan-nutrition`

1. **Frontend → Backend**
   - Aplikasi Android memotret label gizi (mis. via **ML Kit Document Scanner**).
   - Gambar dikirim ke backend melalui endpoint:
     ```text
     POST /scan-nutrition
     ```
   - Backend menerima file `image` dalam format `multipart/form-data`.

2. **Backend → Roboflow**
   - Fungsi `process_image_with_roboflow()`:
     - Menerima gambar dari request,
     - Mengirim gambar ke **Roboflow Workflow**,
     - Workflow mendeteksi *tiga objek utama*:
       - Takaran saji  
       - Sajian per kemasan  
       - Total gula  
     - Menghasilkan koordinat bounding box + label kelas + confidence.

3. **Pemrosesan Hasil Workflow**
   - Backend menormalkan hasil deteksi menjadi struktur data yang konsisten:
     - `class` (misal: `gula`, `takaran_saji`, `sajian_per_kemasan`)  
     - Koordinat bounding box (`x`, `y`, `width`, `height`)  
     - `confidence`  
   - Backend juga memastikan informasi dimensi gambar (`image_width`, `image_height`) tersedia (mengambil dari workflow atau menghitung ulang via **PIL** bila perlu).

4. **Backend → Frontend**
   - Backend mengembalikan respons JSON berisi:
     - `detections` (list bounding box + label objek)  
     - `image_width`, `image_height`  
     - metadata lain jika diperlukan
   - Data ini digunakan frontend untuk menjalankan OCR pada ROI yang tepat dan melakukan parsing nilai gizi di sisi Android.

---

## 🔄 Alur Fitur Scan (POV Backend SAJISEHAT)

![Alur Fitur Scan](https://github.com/snopflake/sajisehat-backend/raw/main/screenshot/alur_fitur_scan.png)

1. **Menerima Gambar dari Frontend**  
   - Backend menerima request `POST /scan-nutrition` dengan file `image` (multipart/form-data).  
   - Gambar dibaca sebagai bytes lalu dikonversi menjadi representasi yang siap dikirim ke Roboflow (mis. `bytes` / `ndarray` via **OpenCV / PIL** sesuai kebutuhan client Roboflow).

2. **Mengirim Gambar ke Roboflow Workflow**  
   - Backend memanggil **Roboflow Serverless Workflow** menggunakan `InferenceHTTPClient` dari **inference-sdk**.  
   - Workflow melakukan **layout detection** untuk menemukan tiga objek utama pada label gizi:
     - Takaran saji (*serving size*)  
     - Jumlah sajian per kemasan (*servings per container*)  
     - Jumlah gula (*sugar content*)  
   - Workflow mengembalikan:
     - bounding box setiap objek,
     - confidence score,
     - (jika tersedia) metadata dimensi gambar.

3. **Pemrosesan Bounding Box & Metadata**  
   - Backend membangun struktur data final untuk setiap deteksi:
     - `class` (misal: `gula`, `takaran_saji`, `sajian_per_kemasan`)  
     - Koordinat bounding box (`x`, `y`, `width`, `height`)  
     - `confidence`  
   - Jika ukuran gambar tidak tersedia dari workflow, backend menghitungnya menggunakan **PIL**.

4. **Menyusun Respons JSON ke Frontend**  
   - Backend menyusun respons JSON yang berisi:
     ```json
     {
       "success": true,
       "message": "Deteksi layout label gizi berhasil",
       "data": {
         "detections": [
           {
             "class": "gula",
             "x": 123.4,
             "y": 56.7,
             "width": 80.0,
             "height": 20.0,
             "confidence": 0.94
           },
           {
             "class": "takaran_saji",
             "x": 50.0,
             "y": 100.0,
             "width": 120.0,
             "height": 25.0,
             "confidence": 0.91
           }
         ],
         "image_width": 1080,
         "image_height": 1920
       }
     }
     ```
   - Di sisi frontend, data ini digunakan untuk:
     - Menentukan ROI OCR di Android (ML Kit Text Recognizer),  
     - Melakukan parsing nilai takaran saji, sajian per kemasan, dan total gula di perangkat,  
     - Menampilkan hasil ke pengguna dan menyimpan riwayat ke **Cloud Firestore**.

---

## 🧰 Framework, Library, & Tools yang Digunakan

> Bagian ini disusun untuk memenuhi ketentuan lomba:  
> *“Peserta wajib mencantumkan daftar framework, library, atau tools yang digunakan dalam dokumentasi teknis (README atau proposal teknis).”*

### 1. Bahasa & Environment

- **Python 3.11** (lihat `runtime.txt`)
- **Virtual environment** (opsional, direkomendasikan untuk isolasi lingkungan)
- **WSGI server**: `gunicorn` (konfigurasi di `Procfile`)

### 2. Web Framework

- **Flask**
  - Factory pattern (`create_app()` di `app/__init__.py`)
  - Routing endpoint (`app/routes.py`) untuk:
    - `POST /scan-nutrition`

### 3. Computer Vision & Object Detection

- **inference-sdk (Roboflow)**  
  - `InferenceHTTPClient` untuk memanggil Roboflow Workflow dari backend.
  - Melakukan layout detection terhadap label gizi.

- **OpenCV (opencv-python-headless)**  
  - Utilitas pemrosesan gambar (decode gambar, manipulasi dasar jika diperlukan).

- **NumPy**  
  - Representasi data gambar dan koordinat sebagai `ndarray`.
  - Operasi numerik untuk perhitungan bounding box / dimensi.

- **Pillow (PIL)**  
  - Membaca gambar dan mendapatkan ukuran gambar (`width`, `height`).

### 4. Utilitas

- **requests**  
  - HTTP client umum (digunakan bila ada integrasi tambahan).

- **python-dotenv**  
  - Membaca konfigurasi dari `.env` pada saat development (misalnya `ROBOFLOW_API_KEY`).

### 5. Infrastruktur & DevOps

- **Render**  
  - Platform deployment **PaaS** untuk menjalankan backend Flask + gunicorn.

- **Procfile**  
  - Mendefinisikan proses yang dijalankan Render:
    ```Procfile
    web: gunicorn run:app --workers 1 --threads 1 --timeout 300 -b 0.0.0.0:$PORT
    ```

- **runtime.txt**  
  - Menentukan versi Python (misalnya: `python-3.11.9`).

- **Git & GitHub**  
  - Version control dan hosting source code.

---

## 🏛️ Arsitektur Kode Backend

- `app/__init__.py`  
  Inisialisasi aplikasi Flask menggunakan factory pattern (`create_app()`).

- `app/routes.py`  
  Mendefinisikan endpoint utama `POST /scan-nutrition` yang:
  - menerima gambar dari frontend,
  - memanggil engine Roboflow,
  - mengembalikan JSON bounding box ke frontend.

- `app/roboflow_engine.py`  
  Mengatur pipeline pemrosesan gambar dan pemanggilan workflow Roboflow:
  - menyiapkan payload gambar,
  - memanggil **InferenceHTTPClient**,
  - menormalkan hasil deteksi menjadi format internal backend.

- `app/roboflow_client.py`  
  Menginisialisasi client Roboflow:
  - konfigurasi `WORKSPACE_NAME` dan `WORKFLOW_ID`,
  - fungsi helper untuk memanggil workflow.

- `run.py`  
  Entry point untuk menjalankan aplikasi (lokal maupun melalui gunicorn).

---

## 📁 Struktur Folder

```text
sajisehat-backend/
├─ app/
│  ├─ __init__.py           # Factory pattern Flask: create_app()
│  ├─ routes.py             # Endpoint utama: POST /scan-nutrition
│  ├─ roboflow_engine.py    # Orkestrasi pipeline ke Roboflow Workflow
│  ├─ roboflow_client.py    # Client Roboflow (InferenceHTTPClient + konfigurasi)
├─ run.py                   # Entry point aplikasi
├─ requirements.txt         # Dependency backend (encoded UTF-16)
├─ Procfile                 # Konfigurasi proses gunicorn untuk deployment
├─ runtime.txt              # Versi Python (misalnya python-3.11.9)
├─ screenshot/
│  ├─ backend_sajisehat_banner.png
│  └─ alur_fitur_scan.png
└─ .gitignore
