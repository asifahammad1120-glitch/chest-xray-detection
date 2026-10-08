"""
AI pipeline: loads the trained YOLO and CNN models once (singleton pattern)
and exposes functions to run the full detect -> crop -> classify pipeline
on an uploaded chest X-ray image.
"""

import os
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from django.conf import settings

# These imports are slow (loading TensorFlow, ultralytics) — they happen
# once when this module is first imported, not on every request.
from ultralytics import YOLO
import tensorflow as tf


# ── Model paths ──────────────────────────────────────────────────
# Adjust these if your models folder lives somewhere else relative
# to the Django project.
YOLO_MODEL_PATH = settings.BASE_DIR.parent.parent / "models" / "best.pt"
CNN_MODEL_PATH = settings.BASE_DIR.parent.parent / "models" / "cnn_best.keras"

# Must match the exact order Keras used when training (alphabetical,
# as printed during CNN training: "Classes found: [...]")
CNN_CLASS_NAMES = [
    "Aortic enlargement", "Atelectasis", "Calcification", "Cardiomegaly",
    "Consolidation", "ILD", "Infiltration", "Lung Opacity", "Nodule-Mass",
    "Normal", "Other lesion", "Pleural effusion", "Pleural thickening",
    "Pneumothorax", "Pulmonary fibrosis",
]

CNN_INPUT_SIZE = (224, 224)

# Minimum YOLO confidence to keep a detection — filters out YOLO's
# weakest, least-confident boxes before they ever reach the CNN.
YOLO_CONF_THRESHOLD = 0.25


# ── Singleton model loading ──────────────────────────────────────
_yolo_model = None
_cnn_model = None


def get_yolo_model():
    global _yolo_model
    if _yolo_model is None:
        _yolo_model = YOLO(str(YOLO_MODEL_PATH))
    return _yolo_model


def get_cnn_model():
    global _cnn_model
    if _cnn_model is None:
        _cnn_model = tf.keras.models.load_model(str(CNN_MODEL_PATH))
    return _cnn_model


# ── Pipeline functions ───────────────────────────────────────────

def _box_iou(box_a, box_b):
    """Intersection-over-Union between two (x1,y1,x2,y2) boxes."""
    ax1, ay1, ax2, ay2 = box_a
    bx1, by1, bx2, by2 = box_b

    inter_x1 = max(ax1, bx1)
    inter_y1 = max(ay1, by1)
    inter_x2 = min(ax2, bx2)
    inter_y2 = min(ay2, by2)

    inter_area = max(0, inter_x2 - inter_x1) * max(0, inter_y2 - inter_y1)
    area_a = (ax2 - ax1) * (ay2 - ay1)
    area_b = (bx2 - bx1) * (by2 - by1)
    union_area = area_a + area_b - inter_area

    return inter_area / union_area if union_area > 0 else 0.0


def _deduplicate_detections(detections, iou_threshold=0.5):
    """
    Removes near-duplicate detections of the SAME class that heavily overlap
    (e.g. YOLO firing twice on one real finding). Keeps the higher-confidence
    box of each overlapping pair. Different classes overlapping is left alone,
    since a real X-ray can genuinely show two different findings in the same area.
    """
    # Highest confidence first, so we always keep the best box in a cluster
    sorted_dets = sorted(detections, key=lambda d: d["confidence"], reverse=True)
    kept = []

    for det in sorted_dets:
        is_duplicate = False
        for kept_det in kept:
            if det["class_name"] == kept_det["class_name"]:
                if _box_iou(det["box"], kept_det["box"]) > iou_threshold:
                    is_duplicate = True
                    break
        if not is_duplicate:
            kept.append(det)

    return kept


def run_detection(image_path):
    """
    Runs YOLO on the given image path.
    Returns a list of dicts: [{"class_name", "confidence", "box": (x1,y1,x2,y2)}, ...]
    Near-duplicate same-class detections are filtered out.
    """
    model = get_yolo_model()
    results = model(str(image_path), conf=YOLO_CONF_THRESHOLD, verbose=False)

    detections = []
    for result in results:
        for box in result.boxes:
            cls_id = int(box.cls[0])
            class_name = model.names[cls_id]
            confidence = float(box.conf[0])
            x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
            detections.append({
                "class_name": class_name,
                "confidence": confidence,
                "box": (x1, y1, x2, y2),
            })

    return _deduplicate_detections(detections)


CROP_PADDING = 0.10  # same padding used when the CNN training crops were generated


def classify_crop(image: Image.Image, box):
    """
    Crops the given box (with the same padding used in training) and runs the CNN.
    Returns (predicted_class_name, confidence).
    """
    x1, y1, x2, y2 = box
    pad_x = (x2 - x1) * CROP_PADDING / 2
    pad_y = (y2 - y1) * CROP_PADDING / 2
    img_w, img_h = image.size

    left = max(0, int(x1 - pad_x))
    top = max(0, int(y1 - pad_y))
    right = min(img_w, int(x2 + pad_x))
    bottom = min(img_h, int(y2 + pad_y))

    crop = image.crop((left, top, right, bottom)).convert("RGB")
    crop_resized = crop.resize(CNN_INPUT_SIZE)

    arr = np.array(crop_resized, dtype=np.float32)
    arr = np.expand_dims(arr, axis=0)

    model = get_cnn_model()
    predictions = model.predict(arr, verbose=0)[0]

    predicted_idx = int(np.argmax(predictions))
    return CNN_CLASS_NAMES[predicted_idx], float(predictions[predicted_idx])


def draw_annotated_image(image: Image.Image, detections_with_classification):
    """
    Draws bounding boxes + labels on a copy of the image.
    detections_with_classification: list of dicts with "box", "class_name"
    (the YOLO detection class — shown on the box for visual reference).
    Returns a new PIL Image.
    """
    annotated = image.copy().convert("RGB")
    draw = ImageDraw.Draw(annotated)

    for det in detections_with_classification:
        x1, y1, x2, y2 = det["box"]
        label = f'{det["class_name"]} {det["confidence"]:.0%}'

        draw.rectangle([x1, y1, x2, y2], outline="red", width=3)
        draw.rectangle([x1, y1, x1 + len(label) * 7 + 6, y1 + 16], fill="red")
        draw.text((x1 + 3, y1 + 1), label, fill="white")

    return annotated


def run_full_pipeline(image_path):
    """
    Runs the complete YOLO -> crop -> CNN pipeline on one image.
    Returns a dict with:
      - "detections": list of {"class_name", "confidence", "box",
                                "classification_class", "classification_confidence"}
      - "annotated_image": PIL Image with boxes drawn
    """
    image = Image.open(image_path)
    detections = run_detection(image_path)

    for det in detections:
        predicted_class, cnn_confidence = classify_crop(image, det["box"])
        det["classification_class"] = predicted_class
        det["classification_confidence"] = cnn_confidence

    annotated_image = draw_annotated_image(image, detections)

    return {
        "detections": detections,
        "annotated_image": annotated_image,
    }