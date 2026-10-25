import os
import uuid
import hashlib
import cv2
import numpy as np
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from ultralytics import YOLO

# -------------------------------------------------------------------
# Configuration & Directory Setup
# -------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUTS_DIR = os.path.join(BASE_DIR, "outputs")
UPLOADS_DIR = os.path.join(BASE_DIR, "uploads")
SAMPLE_DIR = os.path.join(BASE_DIR, "sample_data")

for d in [OUTPUTS_DIR, UPLOADS_DIR, SAMPLE_DIR]:
    os.makedirs(d, exist_ok=True)

app = FastAPI(
    title="Secure Audit - Object Detection Microservice (best)",
    description="Fine-tuned YOLOv8 Crime & Weapon Object Detection Service",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/outputs", StaticFiles(directory=OUTPUTS_DIR), name="outputs")

# -------------------------------------------------------------------
# Model Initialization
# -------------------------------------------------------------------
MODEL_PATH = os.getenv("BEST_MODEL_PATH", os.path.join(BASE_DIR, "best.pt"))
if not os.path.exists(MODEL_PATH):
    # Fallback to yolov8n if best.pt is missing
    print(f"[WARN] {MODEL_PATH} not found, falling back to yolov8n.pt")
    MODEL_PATH = "yolov8n.pt"

print(f"[INFO] Loading YOLO model from: {MODEL_PATH}")
try:
    model = YOLO(MODEL_PATH)
    print(f"[INFO] YOLO model loaded successfully with classes: {model.names}")
except Exception as e:
    print(f"[ERROR] Failed to load model from {MODEL_PATH}: {e}")
    print("[INFO] Loading fallback yolov8n.pt model...")
    model = YOLO("yolov8n.pt")

def calculate_sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

# -------------------------------------------------------------------
# Endpoints
# -------------------------------------------------------------------
@app.get("/")
def root():
    return {
        "service": "Secure Audit Object Detection (best)",
        "status": "online",
        "docs": "/docs",
        "health": "/health"
    }

@app.get("/health")
def health():
    return {
        "status": "healthy",
        "service": "Secure Audit Object Detection (best)",
        "model": os.path.basename(MODEL_PATH),
        "classes_count": len(model.names) if hasattr(model, "names") else 0,
        "classes": model.names if hasattr(model, "names") else {}
    }

@app.post("/detect/image")
@app.post("/detect-image")
async def detect_image(
    image: Optional[UploadFile] = File(None),
    sample_filename: Optional[str] = Form(None),
    confidence: float = Form(0.25)
):
    """
    Run YOLOv8 object detection on input image.
    Returns SHA-256 hash, annotated image URL, and list of detections.
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
        raise HTTPException(status_code=400, detail="No image file provided.")

    if not contents:
        raise HTTPException(status_code=400, detail="Empty image file provided.")

    sha256_hash = calculate_sha256(contents)

    # Decode image to numpy array
    nparr = np.frombuffer(contents, np.uint8)
    cv_img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if cv_img is None:
        raise HTTPException(status_code=400, detail="Failed to decode input image.")

    h, w, _ = cv_img.shape

    # Run YOLO inference
    results = model.predict(source=cv_img, conf=confidence, verbose=False)
    detections: List[Dict[str, Any]] = []

    annotated_img = cv_img.copy()

    for r in results:
        boxes = r.boxes
        if boxes is not None:
            for box in boxes:
                coords = box.xyxy[0].tolist()
                x1, y1, x2, y2 = float(coords[0]), float(coords[1]), float(coords[2]), float(coords[3])
                conf = float(box.conf[0].item())
                cls_idx = int(box.cls[0].item())
                label = model.names.get(cls_idx, f"class_{cls_idx}")

                detections.append({
                    "label": label,
                    "confidence": round(conf, 4),
                    "bbox": {
                        "x1": round(x1, 2),
                        "y1": round(y1, 2),
                        "x2": round(x2, 2),
                        "y2": round(y2, 2)
                    }
                })

                # Draw bounding box on image
                cv2.rectangle(annotated_img, (int(x1), int(y1)), (int(x2), int(y2)), (0, 0, 255), 2)
                caption = f"{label} {conf:.2f}"
                cv2.putText(
                    annotated_img,
                    caption,
                    (int(x1), max(20, int(y1) - 6)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    (0, 0, 255),
                    2
                )

    out_filename = f"detected_{uuid.uuid4().hex[:8]}.jpg"
    out_filepath = os.path.join(OUTPUTS_DIR, out_filename)
    cv2.imwrite(out_filepath, annotated_img)

    return JSONResponse({
        "status": "success",
        "filename": filename,
        "sha256_hash": sha256_hash,
        "output_image_url": f"/outputs/{out_filename}",
        "total_objects": len(detections),
        "detections": detections
    })

@app.post("/detect/video")
@app.post("/detect-video")
async def detect_video(
    video: Optional[UploadFile] = File(None),
    confidence: float = Form(0.25)
):
    """
    Frame-by-frame detection on uploaded video.
    """
    if not video or not video.filename:
        raise HTTPException(status_code=400, detail="No video file provided.")

    temp_input = os.path.join(UPLOADS_DIR, f"temp_{uuid.uuid4().hex[:8]}.mp4")
    with open(temp_input, "wb") as f:
        f.write(await video.read())

    try:
        cap = cv2.VideoCapture(temp_input)
        if not cap.isOpened():
            raise HTTPException(status_code=400, detail="Could not open video file.")

        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = cap.get(cv2.CAP_PROP_FPS) or 25.0

        out_filename = f"detected_video_{uuid.uuid4().hex[:8]}.mp4"
        out_filepath = os.path.join(OUTPUTS_DIR, out_filename)
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out_writer = cv2.VideoWriter(out_filepath, fourcc, fps, (width, height))

        total_detections = 0
        freqs: Dict[str, int] = {}

        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break
            results = model.predict(source=frame, conf=confidence, verbose=False)
            for r in results:
                if r.boxes is not None:
                    for box in r.boxes:
                        cls_idx = int(box.cls[0].item())
                        lbl = model.names.get(cls_idx, str(cls_idx))
                        freqs[lbl] = freqs.get(lbl, 0) + 1
                        total_detections += 1
                        coords = box.xyxy[0].tolist()
                        cv2.rectangle(frame, (int(coords[0]), int(coords[1])), (int(coords[2]), int(coords[3])), (0, 0, 255), 2)
            out_writer.write(frame)

        cap.release()
        out_writer.release()

        return JSONResponse({
            "status": "success",
            "filename": video.filename,
            "output_video_url": f"/outputs/{out_filename}",
            "total_frame_detections": total_detections,
            "detected_object_frequencies": freqs
        })
    finally:
        if os.path.exists(temp_input):
            try:
                os.remove(temp_input)
            except Exception:
                pass
