# app/routes.py
from flask import Blueprint, jsonify, request

from .ocr_engine import (
    extract_text,          # Easy (wrapper lama)
    extract_text_easy,
    extract_text_paddle,
)

from .nutrition_parser import (
    parse_nutrition,
    _clean_text,
    _parse_serving_size_gram,
    _parse_servings_per_pack,
    _parse_sugar_per_serving,
    _parse_sugar_per_pack,
)
from .roboflow_client import (
    run_layout_workflow,
    crop_union_bbox,
    crop_detection,
    get_detections_from_result,
)

bp = Blueprint("main", __name__)


@bp.get("/health")
def health_check():
    return jsonify({
        "status": "ok",
        "message": "Sajisehat backend is running"
    })


def _best_det(detections, cls_name: str):
    """Ambil detection dengan confidence tertinggi untuk class tertentu."""
    cand = [d for d in detections if d.get("class") == cls_name]
    if not cand:
        return None
    return max(cand, key=lambda d: d.get("confidence", 0))


@bp.post("/scan-nutrition")
def scan_nutrition():
    # 1. Validasi input
    if "image" not in request.files:
        return jsonify({
            "success": False,
            "message": "No image file found in request. Use form-data with key 'image'.",
            "error_code": "NO_IMAGE",
        }), 400

    file = request.files["image"]
    if file.filename == "":
        return jsonify({
            "success": False,
            "message": "Empty filename.",
            "error_code": "EMPTY_FILENAME",
        }), 400

    try:
        # --- baca bytes ---
        image_bytes = file.read()

        # --------------------------------------------------
        # 2. KIRIM ke Roboflow Workflow (deteksi layout / row)
        # --------------------------------------------------
        rf_result = run_layout_workflow(image_bytes)
        detections = get_detections_from_result(rf_result)

        # --------------------------------------------------
        # 3. OCR UNION ROI (untuk raw_text umum & fallback)
        # --------------------------------------------------
        union_roi_bytes = crop_union_bbox(image_bytes, detections)

        # OCR versi Easy
        raw_text_easy = extract_text_easy(union_roi_bytes)

        # OCR versi Paddle
        raw_text_paddle = extract_text_paddle(union_roi_bytes)

        # Untuk parsing utama, misalnya kita tetap prioritaskan Easy dulu,
        # kalau kosong, pakai Paddle.
        raw_text = raw_text_easy or raw_text_paddle

        # --------------------------------------------------
        # 4. OCR PER-CLASS (takaran saji, sajian per kemasan, gula)
        #    → semua crop pakai bbox dari Roboflow
        # --------------------------------------------------
        det_takaran = _best_det(detections, "takaran_saji")
        det_sajian = _best_det(detections, "sajian_per_kemasan")
        det_gula = _best_det(detections, "gula")

        # Tambah padding sedikit lebih besar supaya angka ikut masuk
        text_takaran = extract_text(crop_detection(image_bytes, det_takaran, pad=0.4)) if det_takaran else ""
        text_sajian  = extract_text(crop_detection(image_bytes, det_sajian, pad=0.25)) if det_sajian else ""
        text_gula    = extract_text(crop_detection(image_bytes, det_gula, pad=0.4)) if det_gula else ""

        # --------------------------------------------------
        # 5. PARSING PUSAT: serahkan ke nutrition_parser.parse_nutrition
        #    parse_nutrition sudah tahu cara:
        #      - pakai text_takaran / text_sajian / text_gula dulu
        #      - fallback ke raw_text kalau perlu
        # --------------------------------------------------
        parsed = parse_nutrition(
            raw_text or "",
            text_takaran=text_takaran,
            text_sajian=text_sajian,
            text_gula=text_gula,
        )

        serving_size_gram      = parsed.get("serving_size_gram")
        servings_per_pack      = parsed.get("servings_per_pack")
        sugar_per_serving_gram = parsed.get("sugar_per_serving_gram")
        sugar_per_pack_gram    = parsed.get("sugar_per_pack_gram")

        # --------------------------------------------------
        # 6. LOGIKA FALLBACK NUMERIK (tidak boleh None)
        # --------------------------------------------------
        if serving_size_gram is None:
            serving_size_gram = 0.0

        if servings_per_pack is None or servings_per_pack <= 0:
            servings_per_pack = 1

        # Hitung turunan antara gula per sajian & per kemasan
        if sugar_per_serving_gram is None and sugar_per_pack_gram is not None and servings_per_pack:
            sugar_per_serving_gram = sugar_per_pack_gram / servings_per_pack

        if sugar_per_pack_gram is None and sugar_per_serving_gram is not None and servings_per_pack:
            sugar_per_pack_gram = sugar_per_serving_gram * servings_per_pack

        sugar_per_serving_gram = sugar_per_serving_gram or 0.0
        sugar_per_pack_gram = sugar_per_pack_gram or (sugar_per_serving_gram * servings_per_pack)

        # --------------------------------------------------
        # 7. RESPON JSON
        # --------------------------------------------------
        return jsonify({
            "success": True,
            "message": "Nutrition label scanned via Roboflow + OCR",
            "data": {
                "product_name": parsed.get("product_name"),
                "raw_text": raw_text,  # yang dipakai parser (Easy dulu, kalau kosong ke Paddle)
                "serving_size_gram": round(float(serving_size_gram), 2),
                "servings_per_pack": int(round(float(servings_per_pack))),
                "sugar_per_serving_gram": round(float(sugar_per_serving_gram), 2),
                "sugar_per_pack_gram": round(float(sugar_per_pack_gram), 2),
                "roboflow_detections": detections,
                "debug": {
                    "text_takaran": text_takaran,
                    "text_sajian": text_sajian,
                    "text_gula": text_gula,
                    "raw_text_easy": raw_text_easy,
                    "raw_text_paddle": raw_text_paddle,
                },
            }
        }), 200

    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"Failed to scan nutrition: {str(e)}",
            "error_code": "MODEL_ERROR",
        }), 500
