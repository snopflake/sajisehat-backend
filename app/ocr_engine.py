# app/ocr_engine.py
import numpy as np
import cv2
import easyocr

# Inisialisasi OCR sekali saja (bahasa Inggris + Indonesia)
_reader = easyocr.Reader(['en', 'id'], gpu=False)


def _bytes_to_cv2(image_bytes: bytes):
    """Helper: bytes -> OpenCV BGR image."""
    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    return img


def extract_text(image_bytes: bytes) -> str:
    """
    Menerima bytes gambar, mengembalikkan teks hasil OCR
    dalam bentuk string multiline (PAKAI EasyOCR).
    """
    img = _bytes_to_cv2(image_bytes)
    if img is None:
        return ""

    # EasyOCR: detail=0 => hanya teksnya saja
    results = _reader.readtext(img, detail=0, paragraph=True)

    if not results:
        return ""

    return "\n".join(results)


# --- COMPAT: biar routes.py yang sempat impor ini tidak error --- #

# Sama persis dengan extract_text
extract_text_easy = extract_text

# Placeholder: tidak lagi pakai PaddleOCR, selalu kosong
def extract_text_paddle(image_bytes: bytes) -> str:
    return ""
