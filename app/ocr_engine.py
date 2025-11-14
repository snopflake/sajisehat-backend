# app/ocr_engine.py
import numpy as np
import cv2
import easyocr

# Inisialisasi OCR sekali saja (bahasa Inggris + Indonesia)
_reader = easyocr.Reader(['en', 'id'], gpu=False)


def extract_text(image_bytes: bytes) -> str:
    """
    Menerima bytes gambar, mengembalikkan teks hasil OCR
    dalam bentuk string multiline.
    """
    # bytes -> numpy array
    nparr = np.frombuffer(image_bytes, np.uint8)
    # decode ke image OpenCV (BGR)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if img is None:
        return ""

    # EasyOCR: detail=0 => hanya teksnya saja
    results = _reader.readtext(img, detail=0, paragraph=True)

    # gabungkan jadi beberapa baris
    if not results:
        return ""

    # results sudah berupa list string; kita gabung dengan newline
    return "\n".join(results)
