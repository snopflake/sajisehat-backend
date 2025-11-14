# app/roboflow_client.py
import os
import tempfile
from typing import Dict, Any, List

import cv2
import numpy as np
from inference_sdk import InferenceHTTPClient

api_key = os.environ.get("ROBOFLOW_API_KEY")
if not api_key:
    raise RuntimeError("ROBOFLOW_API_KEY is not set. Please set it in your environment variables.")

client = InferenceHTTPClient(
    api_url="https://serverless.roboflow.com",
    api_key=api_key,
)

WORKSPACE_NAME = "nutritionrowstakarangula"
WORKFLOW_ID = "custom-workflow-5"


def run_layout_workflow(image_bytes: bytes) -> Dict[str, Any]:
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
        tmp.write(image_bytes)
        tmp_path = tmp.name

    result = client.run_workflow(
        workspace_name=WORKSPACE_NAME,
        workflow_id=WORKFLOW_ID,
        images={"image": tmp_path},
        use_cache=True,
    )
    return result


def _find_all_predictions(obj: Any) -> List[Dict[str, Any]]:
    """
    Rekursif cari semua list 'predictions' di mana pun berada di JSON.
    """
    found: List[Dict[str, Any]] = []

    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == "predictions" and isinstance(v, list):
                for item in v:
                    if isinstance(item, dict):
                        found.append(item)
            else:
                found.extend(_find_all_predictions(v))
    elif isinstance(obj, list):
        for item in obj:
            found.extend(_find_all_predictions(item))

    return found


def get_detections_from_result(rf_result: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Ambil semua deteksi yang punya x,y,width,height dari hasil workflow.
    """
    all_preds = _find_all_predictions(rf_result)
    detections = [
        p for p in all_preds
        if isinstance(p, dict)
        and {"x", "y", "width", "height"}.issubset(p.keys())
    ]
    return detections


def crop_union_bbox(image_bytes: bytes, detections: List[Dict[str, Any]]) -> bytes:
    if not detections:
        return image_bytes

    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if img is None:
        return image_bytes

    h, w = img.shape[:2]
    x1s, y1s, x2s, y2s = [], [], [], []

    for det in detections:
        cx = det.get("x")
        cy = det.get("y")
        bw = det.get("width")
        bh = det.get("height")
        if cx is None or cy is None or bw is None or bh is None:
            continue

        x1 = max(int(cx - bw / 2), 0)
        y1 = max(int(cy - bh / 2), 0)
        x2 = min(int(cx + bw / 2), w - 1)
        y2 = min(int(cy + bh / 2), h - 1)

        x1s.append(x1)
        y1s.append(y1)
        x2s.append(x2)
        y2s.append(y2)

    if not x1s:
        return image_bytes

    x1_u, y1_u, x2_u, y2_u = min(x1s), min(y1s), max(x2s), max(y2s)
    roi = img[y1_u:y2_u, x1_u:x2_u].copy()

    ok, buf = cv2.imencode(".jpg", roi)
    if not ok:
        return image_bytes
    return buf.tobytes()

def crop_detection(image_bytes: bytes, det: Dict[str, Any], pad: float = 0.15) -> bytes:
    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if img is None:
        return image_bytes

    h, w = img.shape[:2]

    cx, cy = det["x"], det["y"]
    bw, bh = det["width"], det["height"]

    # tambah padding
    bw *= 1 + pad
    bh *= 1 + pad

    x1 = max(int(cx - bw / 2), 0)
    y1 = max(int(cy - bh / 2), 0)
    x2 = min(int(cx + bw / 2), w - 1)
    y2 = min(int(cy + bh / 2), h - 1)

    roi = img[y1:y2, x1:x2]
    ok, buf = cv2.imencode(".jpg", roi)
    if not ok:
        return image_bytes
    return buf.tobytes()
