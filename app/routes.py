from flask import Blueprint, jsonify, request

bp = Blueprint("main", __name__)

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

    dummy_response = {
        "success": True,
        "message": "Dummy nutrition scan result (AI belum diaktifkan)",
        "data": {
            "raw_text": "Takaran saji 30 g\nJumlah sajian per kemasan 3\nGula total 12 g per sajian",
            "product_name": "Contoh Minuman Teh Manis",
            "serving_size_gram": 30.0,
            "servings_per_pack": 3,
            "sugar_per_serving_gram": 12.0,
            "sugar_per_pack_gram": 36.0
        }
    }

    return jsonify(dummy_response), 200
