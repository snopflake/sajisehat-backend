# app/ocr_engine.py
from typing import Dict, Any, List

from .roboflow_client import (
    run_layout_workflow,
    get_detections_from_result,
    # crop_union_bbox  # ga kita pakai lagi di versi JSON-only
)

def process_image_with_roboflow(image_bytes: bytes) -> Dict[str, Any]:
    """
    - Panggil Roboflow workflow
    - Ambil semua detection (takaran_saji, sajian_per_kemasan, gula)
    - Kembalikan dalam format JSON-friendly (list of dict)
    """
    rf_result = run_layout_workflow(image_bytes)

    # 1) Ambil detections dari helper yang sudah kamu punya
    detections_raw = get_detections_from_result(rf_result)

    detections: List[Dict[str, Any]] = []
    for det in detections_raw:
        # pastikan semua field JSON-serializable
        detections.append({
            "class": det.get("class"),
            "x": float(det.get("x", 0)),
            "y": float(det.get("y", 0)),
            "width": float(det.get("width", 0)),
            "height": float(det.get("height", 0)),
            "confidence": float(det.get("confidence", 0)),
        })

    # 2) Kalau kamu memang mau kirim ukuran image dari Roboflow
    #    normalisasi dulu: kalau rf_result list, ambil elemen pertama
    if isinstance(rf_result, list) and rf_result:
        meta_src = rf_result[0]
    else:
        meta_src = rf_result

    image_meta = (meta_src or {}).get("image") or {}

    return {
        "detections": detections,
        "image_width": image_meta.get("width"),
        "image_height": image_meta.get("height"),
    }
