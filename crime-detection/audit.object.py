import os
import sys
import shutil
import cv2
import numpy as np

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATASET_DIR = os.path.join(BASE_DIR, "dataset")

# Complete taxonomy of 26 crime-related suspicious object classes
CLASSES = [
    "knife",
    "scissors",
    "handgun",
    "rifle",
    "pistol",
    "revolver",
    "shotgun",
    "ammunition",
    "grenade",
    "bomb",
    "axe",
    "machete",
    "sword",
    "hammer",
    "crowbar",
    "baseball_bat",
    "iron_rod",
    "chains",
    "rope",
    "syringe",
    "drugs",
    "gas_cylinder",
    "molotov",
    "mask",
    "cash_bundle",
    "suspicious_bag"
]

def create_dataset_structure():
    """
    Creates standard YOLO dataset folder hierarchy and writes data.yaml.
    """
    print("[INFO] Initializing dataset directory structure...")
    train_img_dir = os.path.join(DATASET_DIR, "train", "images")
    train_lbl_dir = os.path.join(DATASET_DIR, "train", "labels")
    val_img_dir = os.path.join(DATASET_DIR, "val", "images")
    val_lbl_dir = os.path.join(DATASET_DIR, "val", "labels")

    for d in [train_img_dir, train_lbl_dir, val_img_dir, val_lbl_dir]:
        os.makedirs(d, exist_ok=True)

    dataset_abs_path = os.path.abspath(DATASET_DIR).replace('\\', '/')
    yaml_path = os.path.join(DATASET_DIR, "data.yaml")

    names_str = "\n".join([f"  {idx}: {cls_name}" for idx, cls_name in enumerate(CLASSES)])
    data_yaml_content = f"""path: {dataset_abs_path}
train: train/images
val: val/images

names:
{names_str}
"""

    with open(yaml_path, "w") as f:
        f.write(data_yaml_content)

    print(f"[INFO] Created data.yaml at: {yaml_path}")
    return yaml_path, train_img_dir, train_lbl_dir, val_img_dir, val_lbl_dir


def generate_synthetic_samples(train_img_dir, train_lbl_dir, val_img_dir, val_lbl_dir):
    """
    Generates representative annotated sample images for all 26 classes to ensure
    end-to-end dataset validity and offline fine-tuning readiness.
    """
    print("[INFO] Generating synthetic dataset samples for 26 crime-related classes...")

    # Define visual signatures for synthetic generation per class
    for cls_id, cls_name in enumerate(CLASSES):
        for split in ["train", "val"]:
            count = 3 if split == "train" else 1
            for sample_idx in range(count):
                fname = f"sample_{cls_name}_{split}_{sample_idx+1}.jpg"
                img_dir = train_img_dir if split == "train" else val_img_dir
                lbl_dir = train_lbl_dir if split == "train" else val_lbl_dir

                img_path = os.path.join(img_dir, fname)
                lbl_path = os.path.join(lbl_dir, os.path.splitext(fname)[0] + ".txt")

                # Canvas with varying background lighting
                bg_val = np.random.randint(180, 240)
                canvas = np.full((640, 640, 3), bg_val, dtype=np.uint8)

                # Bounding box coords (center x, center y, width, height)
                xc = np.random.uniform(0.35, 0.65)
                yc = np.random.uniform(0.35, 0.65)
                w = np.random.uniform(0.25, 0.45)
                h = np.random.uniform(0.25, 0.45)

                px1 = int((xc - w / 2) * 640)
                py1 = int((yc - h / 2) * 640)
                px2 = int((xc + w / 2) * 640)
                py2 = int((yc + h / 2) * 640)

                # Class-specific graphic features
                if "knife" in cls_name or "machete" in cls_name or "sword" in cls_name:
                    cv2.line(canvas, (px1, py1), (px2, py2), (80, 80, 80), 14)
                    cv2.line(canvas, (px1, py1), (px1 + 50, py1 + 50), (20, 20, 200), 18)
                elif "gun" in cls_name or "pistol" in cls_name or "revolver" in cls_name or "rifle" in cls_name or "shotgun" in cls_name:
                    cv2.rectangle(canvas, (px1, py1), (px2, py1 + (py2 - py1) // 2), (40, 40, 40), -1)
                    cv2.rectangle(canvas, (px1, py1), (px1 + (px2 - px1) // 3, py2), (40, 40, 40), -1)
                elif "scissors" in cls_name:
                    cv2.circle(canvas, (px1 + 30, py1 + 30), 25, (0, 0, 160), 6)
                    cv2.circle(canvas, (px1 + 30, py2 - 30), 25, (0, 0, 160), 6)
                    cv2.line(canvas, (px1 + 30, py1 + 30), (px2, py2 - 30), (120, 120, 120), 8)
                elif "grenade" in cls_name or "bomb" in cls_name or "molotov" in cls_name:
                    cv2.ellipse(canvas, (int((px1+px2)/2), int((py1+py2)/2)), (int(w*320), int(h*320)), 0, 0, 360, (30, 90, 30), -1)
                elif "axe" in cls_name or "hammer" in cls_name or "crowbar" in cls_name or "bat" in cls_name or "rod" in cls_name:
                    cv2.line(canvas, (px1, py1), (px2, py2), (40, 80, 140), 20)
                elif "drug" in cls_name or "syringe" in cls_name:
                    cv2.rectangle(canvas, (px1, py1), (px2, py2), (220, 220, 240), -1)
                    cv2.rectangle(canvas, (px1, py1), (px2, py2), (0, 0, 250), 3)
                elif "cash" in cls_name:
                    cv2.rectangle(canvas, (px1, py1), (px2, py2), (60, 160, 60), -1)
                    cv2.circle(canvas, (int((px1+px2)/2), int((py1+py2)/2)), 20, (255, 255, 255), -1)
                else: # bag, rope, gas cylinder, mask, etc.
                    cv2.rectangle(canvas, (px1, py1), (px2, py2), (100, 100, 100), -1)

                # Add texture & noise
                noise = np.random.randint(-15, 15, (640, 640, 3), dtype=np.int16)
                canvas = np.clip(canvas.astype(np.int16) + noise, 0, 255).astype(np.uint8)

                cv2.imwrite(img_path, canvas)

                # Write YOLO label format
                with open(lbl_path, "w") as f:
                    f.write(f"{cls_id} {xc:.6f} {yc:.6f} {w:.6f} {h:.6f}\n")

    print("[SUCCESS] Synthetic dataset samples generated successfully!")


def download_roboflow_dataset(api_key: str, workspace: str, project: str, version: int):
    """
    Downloads dataset from Roboflow Universe using roboflow Python SDK if API key is provided.
    """
    try:
        from roboflow import Roboflow
        rf = Roboflow(api_key=api_key)
        proj = rf.workspace(workspace).project(project)
        dataset = proj.version(version).download("yolov8", location=DATASET_DIR)
        print(f"[SUCCESS] Downloaded Roboflow dataset to: {dataset.location}")
        return True
    except Exception as e:
        print(f"[WARNING] Could not download Roboflow dataset: {e}")
        return False


if __name__ == "__main__":
    yaml_path, tr_img, tr_lbl, val_img, val_lbl = create_dataset_structure()
    generate_synthetic_samples(tr_img, tr_lbl, val_img, val_lbl)
