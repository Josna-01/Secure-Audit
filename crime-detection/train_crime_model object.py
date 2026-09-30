import os
import shutil
import cv2
import numpy as np
from ultralytics import YOLO
from prepare_dataset import create_dataset_structure, generate_synthetic_samples

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_DIR = os.path.join(BASE_DIR, "model")
BACKEND_MODEL_DIR = os.path.join(os.path.dirname(BASE_DIR), "backend", "model")
OBJECT_BACKEND_MODEL_DIR = os.path.join(os.path.dirname(BASE_DIR), "object-backend", "model")

for md in [MODEL_DIR, BACKEND_MODEL_DIR, OBJECT_BACKEND_MODEL_DIR]:
    os.makedirs(md, exist_ok=True)

def train_suspicious_object_model(epochs: int = 3, imgsz: int = 640):
    """
    Retrains YOLOv8 model on crime-related suspicious objects dataset with augmentations
    and exports trained weights to model directories.
    """
    print("[INFO] Setting up dataset for training...")
    yaml_path, train_img_dir, train_lbl_dir, val_img_dir, val_lbl_dir = create_dataset_structure()

    # Generate synthetic samples if dataset has fewer than 10 images
    existing_imgs = [f for f in os.listdir(train_img_dir) if f.endswith(('.jpg', '.png', '.jpeg'))]
    if len(existing_imgs) < 10:
        generate_synthetic_samples(train_img_dir, train_lbl_dir, val_img_dir, val_lbl_dir)

    base_weights = os.path.join(MODEL_DIR, "yolov8n.pt")
    root_weights = os.path.join(os.path.dirname(BASE_DIR), "yolov8n.pt")
    if not os.path.exists(base_weights):
        if os.path.exists(root_weights):
            shutil.copy(root_weights, base_weights)
            print(f"[INFO] Copied base weights from root to: {base_weights}")
        else:
            base_weights = "yolov8n.pt"

    print(f"[INFO] Initializing YOLOv8 model from: {base_weights}")
    model = YOLO(base_weights)

    print(f"[INFO] Starting model training for {epochs} epochs with data augmentations...")
    results = model.train(
        data=yaml_path,
        epochs=epochs,
        imgsz=imgsz,
        batch=4,
        project=os.path.join(BASE_DIR, "runs"),
        name="crime_object_detector",
        exist_ok=True,
        verbose=True,
        # Data Augmentations
        degrees=15.0,     # Rotation angle range (-15 to +15 deg)
        fliplr=0.5,       # Horizontal flip probability
        flipud=0.2,       # Vertical flip probability
        hsv_h=0.015,      # HSV-Hue augmentation
        hsv_s=0.7,        # HSV-Saturation augmentation
        hsv_v=0.4,        # HSV-Value (brightness) augmentation
        scale=0.5,        # Image scale factor (+/- 50%)
        translate=0.1,    # Image translation factor (+/- 10%)
        mosaic=1.0,       # Mosaic augmentation probability
        mixup=0.1         # Mixup augmentation probability
    )

    trained_best = os.path.join(BASE_DIR, "runs", "crime_object_detector", "weights", "best.pt")
    target_bests = [
        os.path.join(MODEL_DIR, "best.pt"),
        os.path.join(BACKEND_MODEL_DIR, "best.pt"),
        os.path.join(OBJECT_BACKEND_MODEL_DIR, "best.pt")
    ]

    saved_path = None
    if os.path.exists(trained_best):
        for target in target_bests:
            shutil.copy(trained_best, target)
        saved_path = target_bests[0]
        print(f"[SUCCESS] Trained model weights saved to all target directories, best: {saved_path}")
    else:
        last_pt = os.path.join(BASE_DIR, "runs", "crime_object_detector", "weights", "last.pt")
        if os.path.exists(last_pt):
            for target in target_bests:
                shutil.copy(last_pt, target)
            saved_path = target_bests[0]
            print(f"[SUCCESS] Model weights saved from last epoch: {saved_path}")
        else:
            fallback = base_weights if os.path.exists(base_weights) else "yolov8n.pt"
            for target in target_bests:
                shutil.copy(fallback, target)
            saved_path = target_bests[0]
            print(f"[WARNING] Using base weights as fallback: {saved_path}")

    return saved_path

if __name__ == "__main__":
    train_suspicious_object_model(epochs=3)
