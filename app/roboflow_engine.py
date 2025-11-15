# app/roboflow_engine.py
from typing import Dict, Any, List
import io

from PIL import Image

from .roboflow_client import (
    run_layout_workflow,
    get_detections_from_result,
)


def process_image_with_roboflow(image_bytes: bytes) -> Dict[str, Any]:
    """
    - Panggil Roboflow workflow
    - Ambil semua detection (takaran_saji, sajian_per_kemasan, gula)
    - Kembalikan dict dengan:
        - detections: list[dict]
        - image_width: int
        - image_height: int
    """
    # 1. Jalankan workflow Roboflow (hasil mentah)
    rf_result = run_layout_workflow(image_bytes)

    # 2. Ambil detections dari helper yang sudah kamu punya
    detections_raw = get_detections_from_result(rf_result)

    detections: List[Dict[str, Any]] = []
    for det in detections_raw:
        # pastikan JSON-serializable dan ada default jika key hilang
        detections.append({
            "class": det.get("class"),
            "x": float(det.get("x", 0)),
            "y": float(det.get("y", 0)),
            "width": float(det.get("width", 0)),
            "height": float(det.get("height", 0)),
            "confidence": float(det.get("confidence", 0)),
        })

    # 3. Coba ambil metadata width/height dari hasil Roboflow (kalau ada)
    image_meta: Dict[str, Any] = {}

    if isinstance(rf_result, list) and rf_result:
        # kalau rf_result adalah list (misal [ {...}, {...} ])
        image_meta = (rf_result[0].get("image") or {}) if isinstance(rf_result[0], dict) else {}
    elif isinstance(rf_result, dict):
        # kalau rf_result adalah dict tunggal
        image_meta = rf_result.get("image") or {}

    width = image_meta.get("width")
    height = image_meta.get("height")

    # 4. Fallback: kalau meta dari Roboflow kosong/None, hitung pakai PIL dari image_bytes
    if width is None or height is None:
        img = Image.open(io.BytesIO(image_bytes))
        width, height = img.size  # (width, height) dalam pixel

    return {
        "detections": detections,
        "image_width": int(width),
        "image_height": int(height),
    }
