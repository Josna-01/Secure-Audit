import os
import shutil
from ultralytics import YOLO

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_DIR = os.path.join(BASE_DIR, "model")
DATASET_YAML = os.path.join(BASE_DIR, "dataset", "data.yaml")

os.makedirs(MODEL_DIR, exist_ok=True)

def train_suspicious_object_model(epochs: int = 100, imgsz: int = 640, patience: int = 20):
    """
    Retrains YOLOv8 model on real Roboflow dataset (dataset/data.yaml).
    Do NOT use synthetic image generators create_sample_data.py or prepare_dataset.py.
    """
    if not os.path.exists(DATASET_YAML):
        raise FileNotFoundError(f"Real dataset configuration file not found at: {DATASET_YAML}")

    base_weights = os.path.join(MODEL_DIR, "yolov8n.pt")
    if not os.path.exists(base_weights):
        root_weights = os.path.join(os.path.dirname(BASE_DIR), "yolov8n.pt")
        if os.path.exists(root_weights):
            shutil.copy(root_weights, base_weights)
            base_weights = base_weights
        else:
            base_weights = "yolov8n.pt"

    print(f"[INFO] Initializing YOLOv8 model from pretrained weights: {base_weights}")
    model = YOLO(base_weights)

    print(f"[INFO] Retraining model on real dataset ({DATASET_YAML}) for {epochs} epochs (patience={patience})...")
    results = model.train(
        data=DATASET_YAML,
        epochs=epochs,
        imgsz=imgsz,
        patience=patience,
        project=os.path.join(BASE_DIR, "runs"),
        name="train",
        exist_ok=True,
        verbose=True
    )

    trained_best = os.path.join(BASE_DIR, "runs", "train", "weights", "best.pt")
    target_best = os.path.join(MODEL_DIR, "best.pt")

    print("\n--- Running Validation (model.val()) ---")
    val_metrics = model.val(data=DATASET_YAML)
    print(f"[MAP] Overall mAP50-95: {val_metrics.box.map:.4f}")
    print(f"[MAP] Overall mAP50: {val_metrics.box.map50:.4f}")
    print(f"[MAP] Per-class mAP50-95: {val_metrics.box.maps}")

    if os.path.exists(trained_best):
        shutil.copy(trained_best, target_best)
        print(f"[SUCCESS] Retrained weights copied to: {target_best}")

    return target_best, val_metrics

if __name__ == "__main__":
    train_suspicious_object_model(epochs=100, patience=20)
