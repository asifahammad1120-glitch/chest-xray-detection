# AI-Based Chest X-Ray Abnormality Detection & Medical Report Management System

An AI-assisted platform that detects and classifies abnormalities in chest X-rays using YOLOv8 and a CNN classifier, with a Django web application supporting three roles — **Patient**, **Doctor/Radiologist**, and **Admin** — through a full upload → AI analysis → doctor review → verified report workflow.

> **Disclaimer:** This system is an AI-assisted analysis tool. AI predictions are not a substitute for professional medical diagnosis. Final clinical interpretation is always provided by a qualified doctor/radiologist.

---

## How it works

```
Patient uploads chest X-ray
        ↓
YOLOv8 detects abnormal regions (bounding boxes + confidence)
        ↓
Each detected region is cropped
        ↓
CNN classifies the cropped region (14 abnormality classes + Normal)
        ↓
AI analysis report generated (detections + classifications + annotated image)
        ↓
Doctor reviews AI output, adds clinical observation & final interpretation
        ↓
Verified medical report available to patient
```

## Results

| Model | Metric | Score |
|---|---|---|
| YOLOv8n (detection) | mAP50 | 0.347 |
| YOLOv8n (detection) | mAP50-95 | 0.185 |
| EfficientNetB0 (classification) | Weighted F1 | 0.751 |
| EfficientNetB0 (classification) | Accuracy | 74.6% |

**14 detected abnormality classes:** Aortic enlargement, Atelectasis, Calcification, Cardiomegaly, Consolidation, ILD, Infiltration, Lung Opacity, Nodule-Mass, Other lesion, Pleural effusion, Pleural thickening, Pneumothorax, Pulmonary fibrosis (+ Normal, for classification only).

## Tech stack

- **AI/ML:** YOLOv8 (Ultralytics), EfficientNetB0 (TensorFlow/Keras), OpenCV, PIL
- **Backend:** Django, SQLite
- **Frontend:** HTML, Bootstrap 5
- **Training:** Google Colab / Kaggle Notebooks (T4 GPU)

## Project structure

```
chest-xray-detection/
├── datasets/              # YOLO + CNN datasets (not included — see Dataset section)
├── yolo_training/         # YOLOv8 training notebooks
├── cnn_training/          # CNN dataset prep + training notebooks
├── django_app/
│   └── xray_platform/     # Django project (models, views, templates, AI pipeline)
├── models/                 # Trained model weights (included)
│   ├── best.pt             # YOLOv8 detector
│   └── cnn_best.keras      # EfficientNetB0 classifier
└── docs/                   # Project report, screenshots
```

## Dataset

Trained on a 14-class chest X-ray abnormality dataset derived from [VinBigData's Chest X-ray Abnormalities dataset](https://www.kaggle.com/c/vinbigdata-chest-xray-abnormalities-detection), sourced via Roboflow ([chest-xray-v7k22](https://universe.roboflow.com/sit-ytzws/chest-xray-v7k22)). Not included in this repo due to size — see the link above to obtain it, or contact for the prepared version.

## Setup & installation

```bash
# Clone the repo
git clone https://github.com/<your-username>/chest-xray-detection.git
cd chest-xray-detection/django_app/xray_platform

# Create environment (Python 3.11)
conda create -n chestxray python=3.11 -y
conda activate chestxray
pip install django pillow tensorflow==2.21.0 ultralytics

# Run migrations
python manage.py migrate
python manage.py seed_categories
python manage.py createsuperuser

# Start the server
python manage.py runserver
```

Visit `http://127.0.0.1:8000/`.

## Key design notes

- **Class imbalance:** the dataset has a long-tail distribution (e.g. 16,092 Aortic enlargement vs. 620 Atelectasis instances). Addressed via class-weighted CNN training and augmentation; an oversampling experiment on YOLO was tested but discarded after it measurably hurt performance due to multi-label image co-occurrence — documented as an analyzed limitation, not hidden.
- **False-positive filtering:** rather than relying solely on a CNN "Normal" class (data-limited, only ~85 source images), the pipeline also filters low-confidence YOLO detections via a confidence threshold before classification.
- **Duplicate detection suppression:** an IoU-based filter removes near-duplicate same-class YOLO boxes before they reach the CNN or the report.


## License

This project was developed as part of an internship assignment at Singularis Software Technologies.
