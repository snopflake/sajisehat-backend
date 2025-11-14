from flask import Blueprint, jsonify, request

from .ocr_engine import process_image_with_roboflow
from .nutrition_parser import parse_nutrition

bp = Blueprint("main", __name__)

@bp.post("/scan-nutrition")
def scan_nutrition():
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
        image_bytes = file.read()

        rf_result = process_image_with_roboflow(image_bytes)

        return jsonify({
            "success": True,
            "message": "Layout detected via Roboflow",
            "data": {
                "detections": rf_result["detections"],
                "image_width": rf_result.get("image_width"),
                "image_height": rf_result.get("image_height"),
            }
        }), 200

    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"Failed to process image with Roboflow: {str(e)}",
            "error_code": "MODEL_ERROR",
        }), 500
