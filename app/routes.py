# app/routes.py
from flask import Blueprint, jsonify, request

from .ocr_engine import extract_text
from .nutrition_parser import parse_nutrition
from .ml_model import predict_nutrition_from_pil

from PIL import Image
from io import BytesIO

# === WAJIB: definisi blueprint ===
bp = Blueprint("main", __name__)


@bp.get("/health")
def health_check():
    return jsonify({
        "status": "ok",
        "message": "Sajisehat backend is running"
    })


@bp.post("/scan-nutrition")
def scan_nutrition():
    # 1. Cek ada file image atau tidak
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
        # --- baca bytes & buat PIL image ---
        image_bytes = file.read()
        pil_img = Image.open(BytesIO(image_bytes))

        # 2. Prediksi pakai model ML (vision)
        ml_pred = predict_nutrition_from_pil(pil_img)
        ml_serving  = ml_pred["serving_size_gram"]
        ml_pack     = ml_pred["servings_per_pack"]
        ml_sugar_sv = ml_pred["sugar_per_serving_gram"]

        # 3. OCR + parser (backup + untuk raw_text)
        raw_text = None
        rule_pred = {
            "serving_size_gram": None,
            "servings_per_pack": None,
            "sugar_per_serving_gram": None,
        }

        try:
            raw_text = extract_text(image_bytes)
            if raw_text:
                parsed = parse_nutrition(raw_text)
                if parsed:
                    rule_pred = parsed
        except Exception:
            # Kalau OCR error, jangan matiin seluruh request
            pass

        # 4. Gabungkan hasil ML dan OCR
        serving = ml_serving
        if serving <= 0 and rule_pred.get("serving_size_gram"):
            serving = rule_pred["serving_size_gram"]

        servings_per_pack = ml_pack
        if (ml_pack < 1 or ml_pack > 40) and rule_pred.get("servings_per_pack"):
            servings_per_pack = rule_pred["servings_per_pack"]

        sugar_per_serving = ml_sugar_sv
        if sugar_per_serving < 0 and rule_pred.get("sugar_per_serving_gram"):
            sugar_per_serving = rule_pred["sugar_per_serving_gram"]

        sugar_per_pack = sugar_per_serving * servings_per_pack

        return jsonify({
            "success": True,
            "message": "Nutrition label scanned by ML + OCR",
            "data": {
                "product_name": None,
                "raw_text": raw_text,
                "serving_size_gram": round(float(serving), 2),
                "servings_per_pack": int(round(float(servings_per_pack))),
                "sugar_per_serving_gram": round(float(sugar_per_serving), 2),
                "sugar_per_pack_gram": round(float(sugar_per_pack), 2),
            }
        }), 200

    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"Failed to scan nutrition: {str(e)}",
            "error_code": "MODEL_ERROR",
        }), 500
