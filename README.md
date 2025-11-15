[![Banner SAJISEHAT Backend](https://github.com/snopflake/sajisehat-backend/raw/main/screenshot/backend_sajisehat_banner.png)](https://github.com/snopflake/sajisehat-backend/raw/main/screenshot/backend_sajisehat_banner.png)

# SAJISEHAT – Backend API 🍽️  
**Layanan Deteksi Layout Label Gizi (Object Detection) untuk Aplikasi SAJISEHAT**

Backend ini merupakan **layanan REST API** yang digunakan oleh aplikasi Android **SAJISEHAT** untuk:

- Menerima **gambar label gizi** dari aplikasi mobile  
- Memanggil **Roboflow Workflow** untuk mendeteksi struktur layout label gizi  
- Mengembalikan **koordinat objek penting** (takaran saji, sajian per kemasan, dan total gula)  
- Digunakan frontend untuk menjalankan **OCR** menggunakan ML Kit Text Recognizer pada area yang tepat  

> Catatan penting:  
> **Backend TIDAK melakukan OCR**.  
> OCR dilakukan **sepenuhnya di Android** dengan ML Kit, berdasarkan bounding box yang dikirim dari backend.

Backend dikembangkan menggunakan **Flask**, dan dideploy di **Render** menggunakan `gunicorn`.

---

## 🧩 Tujuan & Peran Backend

### Masalah yang Ingin Dipecahkan
- Label gizi biasanya berisi banyak teks sehingga OCR mentah sering salah membaca.
- Dibutuhkan mekanisme untuk **mengidentifikasi area penting** dari label gizi, yaitu:
  - Takaran saji
  - Jumlah sajian per kemasan
  - Total gula

### Peran Backend SAJISEHAT
1. **Mendeteksi layout label gizi melalui Roboflow**  
   Backend menemukan dan menentukan **lokasi tiga objek utama** di gambar.

2. **Mengirim bounding box ke frontend**  
   Frontend kemudian menjalankan OCR **hanya pada area yang relevan**, sehingga:
   - Akurasi OCR meningkat
   - Noise teks lain berkurang drastis

3. **Menjadi perantara antara aplikasi dan Roboflow Workflow**

---

## 🔌 Alur Kerja Utama Backend

### Endpoint Utama: `POST /scan-nutrition`

1. **Frontend → Backend**
   - Aplikasi Android memotret label gizi menggunakan **ML Kit Document Scanner**.
   - Gambar dikirim ke backend melalui endpoint `POST /scan-nutrition`.

2. **Backend → Roboflow**
   - Backend memanggil `process_image_with_roboflow()`, yang:
     - Mengirim gambar ke **Roboflow Workflow**
     - Workflow mendeteksi *tiga objek utama*:
       - Takaran saji  
       - Sajian per kemasan  
       - Total gula  
     - Menghasilkan koordinat bounding box tiap objek

3. **Backend → Frontend**
   - Backend mengembalikan respons JSON berisi:
     - `detections` (bounding box + label objek)
     - `image_width`, `image_height`
     - Metadata lain yang relevan

4. **Frontend (OCR)**
   - Frontend melakukan OCR menggunakan **ML Kit Text Recognizer** terhadap:
     - Setiap ROI (Region of Interest) berdasarkan bounding box hasil backend  
   - Hasil OCR lalu diparsing menjadi nilai angka gula, takaran saji, dll.

---

## ✨ Fitur Utama Backend

1. **Deteksi Layout Label Gizi (Roboflow Workflow)**
2. **Object Detection untuk 3 komponen utama:**
   - Takaran saji
   - Sajian per kemasan
   - Total gula
3. **Menjalankan inference Roboflow melalui inference-sdk**
4. **Mengembalikan bounding box siap pakai ke frontend Android**
5. **Arsitektur sederhana dan optimal untuk pemrosesan serverless (Render)**

---
## 🔄 Alur Fitur Scan (POV Backend SAJISEHAT)

![Alur Fitur Scan](https://github.com/snopflake/sajisehat-backend/raw/main/screenshot/alur_fitur_scan.png)

1. **Menerima Gambar dari Frontend**  
   - Backend menerima request `POST /scan-nutrition` berisi file `image` (multipart/form-data).  
   - File gambar dibaca sebagai bytes dan dikonversi menjadi array gambar menggunakan **OpenCV / PIL**.

2. **Mengirim Gambar ke Roboflow Workflow**  
   - Backend memanggil **Roboflow Serverless Workflow** menggunakan `InferenceHTTPClient` dari **inference-sdk**.  
   - Workflow melakukan **layout detection** untuk menemukan tiga objek utama pada label gizi:
     - Takaran saji (*serving size*)  
     - Jumlah sajian per kemasan (*servings per container*)  
     - Jumlah gula (*sugar content*)  
   - Workflow mengembalikan:
     - bounding box setiap objek,  
     - confidence score,  
     - ukuran gambar (`image_width`, `image_height`),  
     - hasil OCR bawaan (jika tersedia).

3. **Pemrosesan Bounding Box & Metadata**  
   - Backend membangun struktur data final untuk setiap deteksi:
     - `class` (misal: `gula`, `takaran_saji`, `sajian_per_kemasan`)  
     - koordinat bounding box (`x`, `y`, `width`, `height`)  
     - `confidence`  
   - Jika ukuran gambar tidak tersedia dari workflow, backend menghitungnya menggunakan **PIL**.

4. **Orkestrasi OCR & Parsing Nilai Gizi**  
   - Backend menggabungkan hasil workflow dan teks OCR menjadi teks mentah (`raw_text`).  
   - Fungsi `parse_nutrition()` mengekstrak nilai numerik dari teks, seperti:
     - `serving_size_gram` (takaran saji dalam gram/ml)  
     - `servings_per_pack` (jumlah sajian per kemasan)  
     - `sugar_per_serving_gram`  
     - `sugar_per_pack_gram`  
   - Proses ini melibatkan:
     - normalisasi teks,  
     - penggunaan regex,  
     - fallback jika format teks tidak standar.

5. **Menghasilkan Respons Terstruktur untuk Frontend**  
   - Backend mengembalikan respons JSON terstruktur, misalnya:
     ```json
     {
       "success": true,
       "message": "Nutrition label parsed successfully",
       "data": {
         "raw_text": "TAKARAN SAJI 200 ml ... Gula 18 g ...",
         "serving_size_gram": 200.0,
         "servings_per_pack": 1.0,
         "sugar_per_serving_gram": 18.0,
         "sugar_per_pack_gram": 18.0
       },
       "meta": {
         "detections": [
           {
             "class": "gula",
             "x": 123.4,
             "y": 56.7,
             "width": 80.0,
             "height": 20.0,
             "confidence": 0.94
           }
         ],
         "image_width": 1080,
         "image_height": 1920
       }
     }
     ```
   - Data ini kemudian digunakan oleh frontend untuk:
     - menampilkan hasil ekstraksi gula ke pengguna,  
     - menghitung estimasi persentase konsumsi gula harian,  
     - menyimpan riwayat konsumsi di **Cloud Firestore**.

---

## 🧰 Framework, Library, & Tools yang Digunakan

### 1. Bahasa & Environment
- Python 3.11
- gunicorn (WSGI server)
- Virtual environment (opsional)

### 2. Web Framework
- **Flask**
  - `create_app()` (Factory Pattern)
  - Routing (`app/routes.py`)

### 3. Computer Vision & Detection
- **inference-sdk (Roboflow)**  
- OpenCV (headless)  
- NumPy  
- Pillow (PIL)  

### 4. Utilitas
- requests  
- python-dotenv  

### 5. Infrastruktur
- Render PaaS  
- Procfile  
- runtime.txt  
- Git & GitHub  

---

## 🏛️ Arsitektur Kode Backend

- `app/__init__.py` → inisialisasi Flask  
- `app/routes.py` → endpoint `/scan-nutrition`  
- `app/roboflow_client.py` → mengirim gambar ke workflow Roboflow  
- `app/roboflow_engine.py` →  orkestrasi pipeline ke Roboflow  
- `run.py` → entry point aplikasi  

---

## 📁 Struktur Folder

```text
sajisehat-backend/
├─ app/
│  ├─ __init__.py
│  ├─ routes.py
│  ├─ roboflow_engine.py
│  ├─ roboflow_client.py
├─ run.py
├─ requirements.txt
├─ Procfile
├─ runtime.txt
├─ screenshot/
│  └─ backend_sajisehat_banner.png
└─ .gitignore
