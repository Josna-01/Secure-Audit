import os
import uuid
import shutil
import cv2
import numpy as np
import hashlib
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, File, UploadFile, Form, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from ultralytics import YOLO

# -------------------------------------------------------------------
# Configuration & Directory Setup
# -------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_DIR = os.path.join(BASE_DIR, "model")
UPLOADS_DIR = os.path.join(BASE_DIR, "uploads")
OUTPUTS_DIR = os.path.join(BASE_DIR, "outputs")
STATIC_DIR = os.path.join(BASE_DIR, "static")
SAMPLE_DIR = os.path.join(BASE_DIR, "sample_data")

for d in [MODEL_DIR, UPLOADS_DIR, OUTPUTS_DIR, STATIC_DIR, SAMPLE_DIR]:
    os.makedirs(d, exist_ok=True)

# Select YOLOv8 model file dynamically
#
# IMPORTANT: model/best.pt in this project was fine-tuned on SYNTHETIC
# placeholder images (OpenCV-drawn rectangles/ellipses from
# create_sample_data.py / prepare_dataset.py) — not real photos. A model
# trained on fake cartoon shapes cannot recognize real knives/guns/etc. and
# will misfire on real images (this is the "detects a fan instead of a
# knife" bug). Until best.pt is retrained on a REAL labeled dataset (see
# train_model.py's docstring / README_RETRAIN.md), we deliberately use the
# pretrained COCO weights instead, which at least reliably detects the
# object classes it actually knows (knife, scissors, person).
#
# Set env var USE_CUSTOM_MODEL=1 once you've retrained best.pt on real data
# and are confident in it, to switch back.
def get_model_path():
    BEST_MODEL_PATH = os.path.join(MODEL_DIR, "best.pt")
    DEFAULT_MODEL_PATH = os.path.join(MODEL_DIR, "yolov8n.pt")
    ROOT_MODEL_PATH = os.path.join(os.path.dirname(BASE_DIR), "yolov8n.pt")
    USE_CUSTOM_MODEL = os.environ.get("USE_CUSTOM_MODEL", "0") == "1"

    if USE_CUSTOM_MODEL and os.path.exists(BEST_MODEL_PATH):
        return BEST_MODEL_PATH
    elif os.path.exists(DEFAULT_MODEL_PATH):
        return DEFAULT_MODEL_PATH
    elif os.path.exists(ROOT_MODEL_PATH):
        return ROOT_MODEL_PATH
    else:
        return "yolov8n.pt"

SELECTED_MODEL_PATH = get_model_path()
print(f"[INFO] Initializing YOLOv8 model from: {SELECTED_MODEL_PATH}")
model = YOLO(SELECTED_MODEL_PATH)

def reload_model():
    global model, SELECTED_MODEL_PATH
    SELECTED_MODEL_PATH = get_model_path()
    print(f"[INFO] Reloading YOLOv8 model from: {SELECTED_MODEL_PATH}")
    model = YOLO(SELECTED_MODEL_PATH)
    load_crime_model()
    return SELECTED_MODEL_PATH

# -------------------------------------------------------------------
# Second model: custom-trained crime model (knife, gun, bullet, blood)
# -------------------------------------------------------------------
# Produced by train_crime_model.py and saved as model/crime_best.pt.
# When present, it handles knife/gun/bullet/blood, and the pretrained COCO
# model above is used ONLY for "person" (COCO is already good at people).
# When absent, the app falls back to COCO for person + knife + scissors.
CRIME_MODEL_PATH = os.path.join(MODEL_DIR, "crime_best.pt")
crime_model = None

def load_crime_model():
    global crime_model
    if os.path.exists(CRIME_MODEL_PATH):
        crime_model = YOLO(CRIME_MODEL_PATH)
        print(f"[INFO] Crime model loaded: {CRIME_MODEL_PATH} classes={crime_model.names}")
    else:
        crime_model = None
        print("[WARN] model/crime_best.pt not found - gun/bullet/blood detection is OFF. "
              "Run train_crime_model.py to create it.")

load_crime_model()

# Color Constants: Pure RED BGR for OpenCV bounding boxes
COLOR_RED_BGR = (0, 0, 255)
COLOR_TEXT_BGR = (255, 255, 255)  # White text over red banner

# Crime & Forensic Suspicious Object Categories
WEAPON_CLASSES = {
    "knife", "scissors", "gun", "handgun", "rifle", "pistol", "revolver", "shotgun",
    "ammunition", "grenade", "bomb", "axe", "machete", "sword", "hammer", "crowbar",
    "baseball_bat", "baseball bat", "iron_rod", "iron rod", "chains", "rope", "syringe",
    "drugs", "gas_cylinder", "gas cylinder", "molotov", "mask", "cash_bundle", "cash bundle",
    "suspicious_bag", "suspicious bag", "dagger", "firearm", "blade"
}
EVIDENCE_CLASSES = {"backpack", "suitcase", "handbag", "cell phone", "laptop", "bottle", "suspicious_bag", "bullet", "blood"}


# -------------------------------------------------------------------
# FastAPI App Initialization
# -------------------------------------------------------------------
app = FastAPI(
    title="Digital Forensic YOLOv8 Suspicious Object Detection System",
    description="High-performance crime evidence and weapon detection service with trained model inference, red bounding box annotations, and SHA-256 integrity verification.",
    version="2.1.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static file routes
app.mount("/outputs", StaticFiles(directory=OUTPUTS_DIR), name="outputs")
app.mount("/sample-data", StaticFiles(directory=SAMPLE_DIR), name="sample_data")
if os.path.exists(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# -------------------------------------------------------------------
# Helper Utilities
# -------------------------------------------------------------------
def calculate_sha256(file_bytes: bytes) -> str:
    """Computes SHA-256 cryptographic hash of evidence file bytes for digital integrity."""
    return hashlib.sha256(file_bytes).hexdigest()

def classify_risk_level(label: str) -> str:
    """Categorizes object risk level based on forensic criteria."""
    lbl_clean = label.lower()
    if any(w in lbl_clean for w in WEAPON_CLASSES):
        return "HIGH (WEAPON)"
    elif any(e in lbl_clean for e in EVIDENCE_CLASSES):
        return "MEDIUM (EVIDENCE)"
    elif "person" in lbl_clean:
        return "MEDIUM (SUBJECT)"
    return "LOW (GENERAL)"

# ---------------------------------------------------------
# Original Code (Alisha) - draw_red_bounding_boxes and run_detection without NMS:
# def draw_red_bounding_boxes(image: np.ndarray, results, conf_threshold: float = 0.25, names=None, allowed=None):
#     annotated_img = image.copy()
#     detections = []
#     suspicious_count = 0
#     for result in results:
#         boxes = result.boxes
#         for box in boxes:
#             conf = float(box.conf[0].cpu().numpy())
#             if conf < conf_threshold:
#                 continue
#             x1, y1, x2, y2 = box.xyxy[0].cpu().numpy().astype(int)
#             cls_id = int(box.cls[0].cpu().numpy())
#             label = (names if names is not None else model.names).get(cls_id, f"Class {cls_id}")
#             risk = classify_risk_level(label)
#             lbl_clean = label.lower().replace("_", " ").strip()
#             allowed_keywords = allowed if allowed is not None else ["knife", "scissors", "person"]
#             if not any(ak in lbl_clean for ak in allowed_keywords):
#                 continue
#             is_weapon = "HIGH" in risk
#             if is_weapon or "MEDIUM" in risk:
#                 suspicious_count += 1
#             box_thickness = 4 if is_weapon else 3
#             cv2.rectangle(annotated_img, (x1, y1), (x2, y2), COLOR_RED_BGR, box_thickness)
#             detections.append({
#                 "id": len(detections) + 1,
#                 "label": label,
#                 "category": risk,
#                 "confidence": round(conf, 4),
#                 "confidence_percentage": f"{conf * 100:.1f}%",
#                 "bbox": {"x1": int(x1), "y1": int(y1), "x2": int(x2), "y2": int(y2)},
#                 "is_suspicious": ("HIGH" in risk or "MEDIUM" in risk)
#             })
#     return annotated_img, detections, suspicious_count
# ---------------------------------------------------------

def calculate_iou(box1: dict, box2: dict) -> float:
    """Calculates Intersection over Union (IoU) between two bounding boxes."""
    x1 = max(box1["x1"], box2["x1"])
    y1 = max(box1["y1"], box2["y1"])
    x2 = min(box1["x2"], box2["x2"])
    y2 = min(box1["y2"], box2["y2"])
    inter = max(0, x2 - x1) * max(0, y2 - y1)
    area1 = max(0, box1["x2"] - box1["x1"]) * max(0, box1["y2"] - box1["y1"])
    area2 = max(0, box2["x2"] - box2["x1"]) * max(0, box2["y2"] - box2["y1"])
    union = area1 + area2 - inter
    return inter / union if union > 0 else 0.0

def clean_forensic_label(label: str) -> str:
    """Standardizes forensic labels to avoid noisy shotgun/knife misclassifications."""
    lbl_lower = label.lower().replace("_", " ").strip()
    if "knife" in lbl_lower or "blade" in lbl_lower or "dagger" in lbl_lower or "machete" in lbl_lower:
        return "Knife"
    elif any(w in lbl_lower for w in ["handgun", "pistol", "revolver", "shotgun", "rifle", "firearm", "gun"]):
        return "Firearm / Handgun"
    elif "person" in lbl_lower:
        return "Person"
    elif any(e in lbl_lower for e in ["backpack", "bag", "handbag", "suitcase"]):
        return "Backpack (Evidence)"
    elif "bullet" in lbl_lower or "casing" in lbl_lower or "ammo" in lbl_lower:
        return "Ammunition"
    return label.capitalize()

def apply_cross_model_nms(candidates: List[Dict[str, Any]], iou_thresh: float = 0.35) -> List[Dict[str, Any]]:
    """Suppresses duplicate and heavily overlapping bounding boxes across multiple models."""
    sorted_candidates = sorted(candidates, key=lambda d: d.get("score", d["confidence"]), reverse=True)
    kept = []
    for cand in sorted_candidates:
        if not any(calculate_iou(cand["bbox"], k["bbox"]) > iou_thresh for k in kept):
            kept.append(cand)
    return kept

def run_detection(frame: np.ndarray, confidence: float = 0.45):
    """
    Runs refined dual-model inference with Cross-Class Non-Maximum Suppression (NMS).
    Prevents duplicate boxes on the same weapon and eliminates low-confidence noise.
    """
    # Use robust confidence threshold (at least 0.40 to avoid phantom detections)
    conf_thresh = max(confidence, 0.40)
    candidates = []

    # 1. Custom Crime Model (Weapons: Knife, Guns, Blood, Bullets)
    if crime_model is not None:
        try:
            crime_res = crime_model(frame, conf=conf_thresh, verbose=False)
            for box in crime_res[0].boxes:
                conf = float(box.conf[0].cpu().numpy())
                cls_id = int(box.cls[0].cpu().numpy())
                raw_name = crime_model.names.get(cls_id, f"Class {cls_id}")
                x1, y1, x2, y2 = box.xyxy[0].cpu().numpy().astype(int)
                
                std_label = clean_forensic_label(raw_name)
                risk = classify_risk_level(std_label)
                # Slight score bonus for distinct knife detections to resolve knife vs shotgun ambiguity
                score = conf + (0.05 if "knife" in raw_name.lower() else 0.0)
                
                candidates.append({
                    "raw_label": raw_name,
                    "label": std_label,
                    "category": risk,
                    "confidence": round(conf, 4),
                    "confidence_percentage": f"{conf * 100:.1f}%",
                    "score": score,
                    "bbox": {"x1": int(x1), "y1": int(y1), "x2": int(x2), "y2": int(y2)},
                    "is_suspicious": True
                })
        except Exception as e:
            print(f"[WARN] Crime model inference failed: {e}")

    # 2. Base Pretrained YOLO COCO Model (Person, Backpacks, Luggage, Secondary Knife)
    try:
        coco_res = model(frame, conf=conf_thresh, verbose=False)
        for box in coco_res[0].boxes:
            conf = float(box.conf[0].cpu().numpy())
            cls_id = int(box.cls[0].cpu().numpy())
            raw_name = model.names.get(cls_id, f"Class {cls_id}")
            lbl_clean = raw_name.lower().replace("_", " ").strip()
            
            # Whitelist relevant forensic classes from COCO
            allowed_coco = ["person", "backpack", "handbag", "suitcase", "knife", "scissors", "bottle"]
            if not any(ac in lbl_clean for ac in allowed_coco):
                continue
                
            x1, y1, x2, y2 = box.xyxy[0].cpu().numpy().astype(int)
            std_label = clean_forensic_label(raw_name)
            risk = classify_risk_level(std_label)
            
            candidates.append({
                "raw_label": raw_name,
                "label": std_label,
                "category": risk,
                "confidence": round(conf, 4),
                "confidence_percentage": f"{conf * 100:.1f}%",
                "score": conf,
                "bbox": {"x1": int(x1), "y1": int(y1), "x2": int(x2), "y2": int(y2)},
                "is_suspicious": ("HIGH" in risk or "MEDIUM" in risk)
            })
    except Exception as e:
        print(f"[WARN] Base model inference failed: {e}")

    # 3. Apply Cross-Model NMS to eliminate duplicate overlapping boxes
    filtered_detections = apply_cross_model_nms(candidates, iou_thresh=0.35)

    # 4. Draw Clean Red Bounding Boxes on Frame
    annotated_img = frame.copy()
    suspicious_count = 0
    for i, det in enumerate(filtered_detections, 1):
        det["id"] = i
        b = det["bbox"]
        is_weapon = "HIGH" in det.get("category", "")
        if is_weapon or "MEDIUM" in det.get("category", ""):
            suspicious_count += 1
        box_thickness = 4 if is_weapon else 3
        cv2.rectangle(annotated_img, (b["x1"], b["y1"]), (b["x2"], b["y2"]), COLOR_RED_BGR, box_thickness)

    return annotated_img, filtered_detections, suspicious_count


# -------------------------------------------------------------------
# Blood-like region heuristic (NOT a trained model — see disclaimer)
# -------------------------------------------------------------------
# There is no "blood" class in COCO, and no real trained weights for it in
# this project. This is a plain color heuristic that flags dark-red regions.
# It WILL false-positive on red paint, sauce, red fabric, etc. Treat any hit
# as "worth a closer look", never as confirmation.
COLOR_BLOOD_HEURISTIC_BGR = (60, 20, 220)  # magenta-red, visually distinct from pure red boxes

def detect_blood_like_regions(image: np.ndarray, grid_size: int = 24, min_cluster_cells: int = 3):
    h, w = image.shape[:2]
    cell_w = max(1, w // grid_size)
    cell_h = max(1, h // grid_size)
    flagged_cells = set()

    for gy in range(grid_size):
        for gx in range(grid_size):
            x0, y0 = gx * cell_w, gy * cell_h
            x1, y1 = min(x0 + cell_w, w), min(y0 + cell_h, h)
            if x1 <= x0 or y1 <= y0:
                continue
            cell = image[y0:y1, x0:x1]
            b, g, r = cell[:, :, 0].mean(), cell[:, :, 1].mean(), cell[:, :, 2].mean()
            # dark, dominant-red, low green/blue relative to red
            is_blood_like = 60 < r < 200 and (r - g) > 35 and (r - b) > 25 and g < 90 and b < 90
            if is_blood_like:
                flagged_cells.add((gx, gy))

    if not flagged_cells:
        return []

    # flood-fill merge adjacent flagged cells into boxes
    visited = set()
    boxes = []
    for cell in flagged_cells:
        if cell in visited:
            continue
        stack = [cell]
        visited.add(cell)
        min_gx, min_gy, max_gx, max_gy, size = cell[0], cell[1], cell[0], cell[1], 0
        while stack:
            cx, cy = stack.pop()
            size += 1
            min_gx, min_gy = min(min_gx, cx), min(min_gy, cy)
            max_gx, max_gy = max(max_gx, cx), max(max_gy, cy)
            for dx, dy in [(1, 0), (-1, 0), (0, 1), (0, -1)]:
                nb = (cx + dx, cy + dy)
                if nb in flagged_cells and nb not in visited:
                    visited.add(nb)
                    stack.append(nb)
        if size >= min_cluster_cells:
            boxes.append({
                "x1": min_gx * cell_w, "y1": min_gy * cell_h,
                "x2": min((max_gx + 1) * cell_w, w), "y2": min((max_gy + 1) * cell_h, h)
            })
    return boxes

def draw_blood_heuristic_boxes(image: np.ndarray, source: np.ndarray = None):
    # Analyze the ORIGINAL frame (`source`), never the annotated one - otherwise
    # the red detection boxes we just drew would be flagged as "blood".
    boxes = detect_blood_like_regions(source if source is not None else image)
    detections = []
    for b in boxes:
        cv2.rectangle(image, (b["x1"], b["y1"]), (b["x2"], b["y2"]), COLOR_BLOOD_HEURISTIC_BGR, 2)
        detections.append({
            "label": "blood_like_region (color heuristic, unverified)",
            "category": "HEURISTIC (NOT A TRAINED DETECTION)",
            "confidence": None,
            "bbox": b,
            "is_suspicious": True
        })
    return image, detections

# -------------------------------------------------------------------
# Root & Health Endpoints
# -------------------------------------------------------------------
@app.get("/")
def index():
    """Serves the Web Interface or API status response."""
    index_html = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_html):
        return FileResponse(index_html)
    return {
        "status": "online",
        "system": "YOLOv8 Trained Crime & Suspicious Object Detection API",
        "model_loaded": SELECTED_MODEL_PATH,
        "bounding_box_color": "RED (BGR: 0, 0, 255)",
        "docs_url": "/docs"
    }

@app.get("/health")
def health():
    return {
        "status": "healthy",
        "model_loaded": SELECTED_MODEL_PATH,
        "classes_count": len(model.names) if model else 0,
        "crime_model_loaded": crime_model is not None,
        "crime_classes": dict(crime_model.names) if crime_model is not None else {}
    }

# -------------------------------------------------------------------
# Model Training Endpoint (/train)
# -------------------------------------------------------------------
@app.post("/train", summary="Train/Fine-tune YOLOv8 on Suspicious Object Dataset")
def train_model_endpoint(epochs: int = 5):
    """
    Triggers automated training/fine-tuning of YOLOv8 on the suspicious object dataset.
    Saves trained weights to model/best.pt and reloads the active model.
    """
    try:
        from train_model import train_suspicious_object_model
        # Original code (Alisha):
        # trained_path = train_suspicious_object_model(epochs=epochs)
        train_res = train_suspicious_object_model(epochs=epochs)
        trained_path = train_res[0] if isinstance(train_res, tuple) else train_res
        active_model = reload_model()
        return JSONResponse({
            "status": "success",
            "message": "Suspicious object detection model trained successfully!",
            "trained_model_path": trained_path,
            "active_model": active_model,
            "classes": model.names
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Model training failed: {str(e)}")

# -------------------------------------------------------------------
# Image Detection Endpoint (/detect/image and /detect-image)
# -------------------------------------------------------------------
@app.post("/detect/image", summary="Predict and detect suspicious objects in user-input image with Red Bounding Boxes")
@app.post("/detect-image", include_in_schema=False)
async def detect_image(
    image: Optional[UploadFile] = File(None),
    sample_filename: Optional[str] = Form(None),
    confidence: float = Form(0.40)
):
    """
    Processes user input image or sample image.
    Calculates SHA-256 hash, runs trained YOLOv8 inference, highlights detected suspicious objects with RED bounding boxes,
    and returns output image URL and detailed detection metrics.
    """
    contents = None
    filename = "input_image.jpg"

    if image and image.filename:
        contents = await image.read()
        filename = image.filename
    elif sample_filename:
        sample_path = os.path.join(SAMPLE_DIR, sample_filename)
        if os.path.exists(sample_path):
            with open(sample_path, "rb") as f:
                contents = f.read()
            filename = sample_filename
        else:
            raise HTTPException(status_code=404, detail=f"Sample file '{sample_filename}' not found.")
    else:
        # Fallback to default sample knife evidence if no input provided
        default_sample = os.path.join(SAMPLE_DIR, "sample_knife_evidence.jpg")
        if os.path.exists(default_sample):
            with open(default_sample, "rb") as f:
                contents = f.read()
            filename = "sample_knife_evidence.jpg"

    if not contents:
        raise HTTPException(status_code=400, detail="No image file provided.")

    # Calculate SHA-256 Evidence Hash
    sha256_hash = calculate_sha256(contents)

    # Decode image to OpenCV BGR
    nparr = np.frombuffer(contents, np.uint8)
    cv_img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    if cv_img is None:
        raise HTTPException(status_code=400, detail="Failed to decode input image.")

    # Run detection (COCO for person + custom crime model when available)
    annotated_img, detections, suspicious_count = run_detection(cv_img, confidence)

    # Save annotated output image
    ext = os.path.splitext(filename)[1] or ".jpg"
    out_filename = f"detected_{uuid.uuid4().hex[:8]}{ext}"
    out_filepath = os.path.join(OUTPUTS_DIR, out_filename)
    cv2.imwrite(out_filepath, annotated_img)

    return JSONResponse({
        "status": "success",
        "filename": filename,
        "sha256_hash": sha256_hash,
        "active_model": SELECTED_MODEL_PATH,
        "output_image_url": f"/outputs/{out_filename}",
        "total_objects": len(detections),
        "suspicious_objects_count": suspicious_count,
        "detections": detections
    })

# -------------------------------------------------------------------
# Video Detection Endpoint (/detect/video and /detect-video)
# -------------------------------------------------------------------
@app.post("/detect/video", summary="Detect suspicious objects in Video frame-by-frame with Red Boxes")
@app.post("/detect-video", include_in_schema=False)
async def detect_video(
    video: Optional[UploadFile] = File(None),
    sample_filename: Optional[str] = Form(None),
    confidence: float = Form(0.40)
):
    """
    Frame-by-frame detection on uploaded video or sample video using trained model.
    Highlights detected objects in RED BOXES on every frame and returns processed output video.
    """
    temp_input_filename = f"temp_{uuid.uuid4().hex[:8]}.mp4"
    temp_input_path = os.path.join(UPLOADS_DIR, temp_input_filename)
    filename = "sample_video.mp4"
    file_bytes = b""

    if video and video.filename:
        filename = video.filename
        with open(temp_input_path, "wb") as buffer:
            shutil.copyfileobj(video.file, buffer)
        with open(temp_input_path, "rb") as f:
            file_bytes = f.read()
    elif sample_filename:
        sample_path = os.path.join(SAMPLE_DIR, sample_filename)
        if os.path.exists(sample_path):
            shutil.copy(sample_path, temp_input_path)
            filename = sample_filename
            with open(sample_path, "rb") as f:
                file_bytes = f.read()
        else:
            raise HTTPException(status_code=404, detail=f"Sample video '{sample_filename}' not found.")
    else:
        default_vid = os.path.join(SAMPLE_DIR, "sample_surveillance_stream.mp4")
        if os.path.exists(default_vid):
            shutil.copy(default_vid, temp_input_path)
            filename = "sample_surveillance_stream.mp4"
            with open(default_vid, "rb") as f:
                file_bytes = f.read()

    if not os.path.exists(temp_input_path):
        raise HTTPException(status_code=400, detail="No video file provided.")

    sha256_hash = calculate_sha256(file_bytes) if file_bytes else "N/A"

    try:
        cap = cv2.VideoCapture(temp_input_path)
        if not cap.isOpened():
            raise HTTPException(status_code=400, detail="Could not open video stream.")

        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        if fps <= 0 or np.isnan(fps):
            fps = 25.0

        out_filename = f"detected_video_{uuid.uuid4().hex[:8]}.mp4"
        out_filepath = os.path.join(OUTPUTS_DIR, out_filename)

        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out_writer = cv2.VideoWriter(out_filepath, fourcc, fps, (width, height))

        total_frame_detections = 0
        total_suspicious_hits = 0
        object_counts = {}

        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break

            annotated_frame, frame_detections, suspicious_count = run_detection(frame, confidence)

            total_frame_detections += len(frame_detections)
            total_suspicious_hits += suspicious_count

            for det in frame_detections:
                lbl = det["label"]
                object_counts[lbl] = object_counts.get(lbl, 0) + 1

            out_writer.write(annotated_frame)

        cap.release()
        out_writer.release()

        return JSONResponse({
            "status": "success",
            "filename": filename,
            "sha256_hash": sha256_hash,
            "output_video_url": f"/outputs/{out_filename}",
            "fps": round(fps, 2),
            "resolution": f"{width}x{height}",
            "total_frame_detections": total_frame_detections,
            "total_suspicious_hits": total_suspicious_hits,
            "detected_object_frequencies": object_counts
        })

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Video processing failed: {str(e)}")

    finally:
        if os.path.exists(temp_input_path):
            try:
                os.remove(temp_input_path)
            except Exception:
                pass

if __name__ == "__main__":
    import uvicorn
    # Original code (Alisha):
    # uvicorn.run("main:app", host="127.0.0.1", port=8001, reload=True)
    # Updated: Port 8003 to prevent collision with BNS service on 8001
    uvicorn.run("main:app", host="127.0.0.1", port=8003, reload=True)
