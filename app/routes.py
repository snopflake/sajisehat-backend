from flask import Blueprint, jsonify, request

from .ocr_engine import extract_text
from .nutrition_parser import parse_nutrition

bp = Blueprint("main", __name__)


@bp.get("/health")
def health_check():
    return jsonify({
        "status": "ok",
        "message": "Sajisehat backend is running"
    })


@bp.post("/scan-nutrition")
def scan_nutrition():
    if "image" not in request.files:
        return jsonify({
            "success": False,
            "message": "No image file found in request. Use form-data with key 'image'.",
            "error_code": "NO_IMAGE"
        }), 400

    file = request.files["image"]

    if file.filename == "":
        return jsonify({
            "success": False,
            "message": "Empty filename.",
            "error_code": "EMPTY_FILENAME"
        }), 400

    # baca bytes gambar
    image_bytes = file.read()

    # 1. OCR -> raw_text
    raw_text = extract_text(image_bytes)

    # kalau kosong, balikin error friendly
    if not raw_text.strip():
        return jsonify({
            "success": False,
            "message": "Could not extract any text from image.",
            "error_code": "OCR_EMPTY"
        }), 422

    # 2. Parsing nutrisi -> dict
    nutrition = parse_nutrition(raw_text)

    response = {
        "success": True,
        "message": "Nutrition label scanned successfully",
        "data": nutrition
    }

    return jsonify(response), 200
