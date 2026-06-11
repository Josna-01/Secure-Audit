import os
import shutil
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from roboflow import Roboflow

load_dotenv()

ROBOFLOW_API_KEY = os.environ.get("ROBOFLOW_API_KEY")

app = FastAPI(title="Secure Audit — Object Detection Service")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load Roboflow model (Legacy cloud fallback)
try:
    if ROBOFLOW_API_KEY:
        rf = Roboflow(api_key=ROBOFLOW_API_KEY)
        project = rf.workspace().project("weapon-detection-using-yolov8")
        model = project.version(1).model
        print("[INFO] Loaded Roboflow cloud model successfully.")
    else:
        print("[WARNING] ROBOFLOW_API_KEY is not defined in environment.")
        model = None
except Exception as e:
    print(f"[ERROR] Failed to load Roboflow model: {e}")
    model = None


@app.get("/")
def home():
    return {
        "status": "online",
        "service": "object-detection",
        "engine": "Roboflow (Cloud API)" if model else "None (Requires local YOLOv8 setup)"
    }


@app.post("/detect")
async def detect(image: UploadFile = File(...)):
    """
    Runs weapon/object detection on the uploaded image.
    This template currently calls the Roboflow Cloud model.
    The team member should replace this logic with local YOLOv8 inference (using 'ultralytics' library).
    """
    if not model:
        raise HTTPException(
            status_code=500,
            detail="Object detection model is not loaded. Set ROBOFLOW_API_KEY or configure local YOLOv8."
        )

    temp_file_path = f"temp_{image.filename}"
    try:
        # Save uploaded file temporarily
        with open(temp_file_path, "wb") as buffer:
            shutil.copyfileobj(image.file, buffer)

        # Run prediction via Roboflow Client
        prediction = model.predict(temp_file_path).json()
        return JSONResponse(content=prediction)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Detection failed: {str(e)}")
    finally:
        # Clean up temp file
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8003))
    uvicorn.run("app:app", host="0.0.0.0", port=port, reload=True)
