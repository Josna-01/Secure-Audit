import os
import uuid
import shutil
import logging
import threading
import datetime
import requests
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from supabase import create_client, Client
import uvicorn
from sqlalchemy.orm import Session
from db import SessionLocal, get_db
from models import PhotogrammetryModel

# Import local service classes
from services.frame_extractor import FrameExtractor
from services.frame_selector import FrameSelector
from services.colmap_runner import ColmapRunner
from services.open3d_processor import Open3DProcessor

# Load environment variables
load_dotenv()

# Set mode to PRODUCTION to ensure strict frame selection and robust COLMAP processing
os.environ["PHOTOGRAMMETRY_MODE"] = "PRODUCTION"

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
    raise RuntimeError("Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY environment variables.")

# Initialize logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("photogrammetry-backend")

# Initialize Supabase client using Service Role Key to enable database updates
supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

# Initialize FastAPI App
app = FastAPI(title="Secure Audit — Photogrammetry microservice", version="1.0")

# Setup CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic schema for trigger body
class TriggerRequest(BaseModel):
    evidence_id: str
    file_url: str

def run_pipeline_background(job_id: str, case_id: str, file_url: str):
    """
    Executes the full photogrammetry pipeline asynchronously:
    1. Downloads video from remote storage
    2. Extracts raw frames
    3. Selects the highest quality frames
    4. Runs COLMAP 3D reconstruction
    5. Refines mesh and measures dimensions in Open3D
    6. Uploads outputs to Supabase Storage
    7. Updates job status in Supabase Database
    """
    logger.info(f"[JOB {job_id}] Starting background processing pipeline.")

    # Workspace directory mapping
    job_dir = os.path.join("/tmp/secure_audits", case_id)
    frames_dir = os.path.join(job_dir, "frames")
    selected_dir = os.path.join(job_dir, "selected")
    colmap_dir = os.path.join(job_dir, "colmap")
    output_dir = os.path.join(job_dir, "output")
    video_path = os.path.join(job_dir, "input_video.mp4")

    try:
        # Create temporary working directories
        os.makedirs(job_dir, exist_ok=True)
        os.makedirs(frames_dir, exist_ok=True)
        os.makedirs(selected_dir, exist_ok=True)
        os.makedirs(colmap_dir, exist_ok=True)
        os.makedirs(output_dir, exist_ok=True)

        # 1. Download video file from remote URL
        logger.info(f"[JOB {job_id}] Step 1/5: Downloading video from {file_url}...")
        response = requests.get(file_url, stream=True, timeout=60)
        response.raise_for_status()
        with open(video_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        logger.info(f"[JOB {job_id}] Video downloaded successfully to {video_path}")

        # 2. Extract frames from video
        logger.info(f"[JOB {job_id}] Step 2/5: Extracting frames...")
        extractor = FrameExtractor()
        extracted_paths = extractor.extract(video_path, frames_dir, fps=15)
        logger.info(f"[JOB {job_id}] Extracted {len(extracted_paths)} frames.")

        # 3. Select best frames
        logger.info(f"[JOB {job_id}] Step 3/5: Selecting best frame candidates...")
        selector = FrameSelector()
        selected_paths = selector.select(extracted_paths, max_frames=25)
        logger.info(f"[JOB {job_id}] Selected {len(selected_paths)} high-quality frames.")

        if not selected_paths:
            raise ValueError("No frames passed quality and similarity criteria. Cannot run reconstruction.")

        # Copy selected frames to selection workspace folder
        for idx, path in enumerate(selected_paths):
            dest_name = f"frame_{idx:03d}.jpg"
            dest_path = os.path.join(selected_dir, dest_name)
            shutil.copy(path, dest_path)

        # 4. Execute COLMAP Reconstruction
        logger.info(f"[JOB {job_id}] Step 4/5: Running COLMAP reconstruction (SfM + MVS)...")
        runner = ColmapRunner()
        colmap_res = runner.reconstruct(selected_dir, colmap_dir)
        dense_ply = colmap_res["dense_ply_path"]
        logger.info(f"[JOB {job_id}] COLMAP completed. Dense point cloud created: {dense_ply}")

        # 5. Open3D Post-Processing
        logger.info(f"[JOB {job_id}] Step 5/5: Running Open3D cleaning and mesh reconstruction...")
        processor = Open3DProcessor()
        o3d_res = processor.process(dense_ply, output_dir)
        logger.info(f"[JOB {job_id}] Open3D processing completed. Assets generated.")

        # 6. Upload processed artifacts to Supabase Storage
        model_ply_local = o3d_res["ply_url"]
        model_glb_local = o3d_res["glb_url"]

        # Upload model.ply
        ply_storage_path = f"models/{case_id}/{job_id}_model.ply"
        logger.info(f"[JOB {job_id}] Uploading point cloud to Supabase Storage: {ply_storage_path}")
        with open(model_ply_local, "rb") as f:
            ply_bytes = f.read()
        supabase.storage.from_("evidence").upload(
            path=ply_storage_path,
            file=ply_bytes,
            file_options={"content-type": "application/octet-stream"}
        )
        ply_url = supabase.storage.from_("evidence").get_public_url(ply_storage_path)
        if ply_url.endswith("?"):
            ply_url = ply_url[:-1]

        # Upload model.glb
        glb_storage_path = f"models/{case_id}/{job_id}_model.glb"
        logger.info(f"[JOB {job_id}] Uploading 3D mesh GLB to Supabase Storage: {glb_storage_path}")
        with open(model_glb_local, "rb") as f:
            glb_bytes = f.read()
        supabase.storage.from_("evidence").upload(
            path=glb_storage_path,
            file=glb_bytes,
            file_options={"content-type": "model/gltf-binary"}
        )
        glb_url = supabase.storage.from_("evidence").get_public_url(glb_storage_path)
        if glb_url.endswith("?"):
            glb_url = glb_url[:-1]

        # 7. Update Job Status to Completed in Database
        completed_at = datetime.datetime.now(datetime.timezone.utc)
        db = SessionLocal()
        try:
            job = db.query(PhotogrammetryModel).filter(PhotogrammetryModel.id == uuid.UUID(job_id)).first()
            if job:
                job.status = "Completed"
                job.model_url = glb_url
                job.point_cloud_url = ply_url
                job.frame_count = len(selected_paths)
                job.completed_at = completed_at
                db.commit()
            logger.info(f"[JOB {job_id}] Pipeline execution completed successfully. Database record updated.")
        except Exception as db_err:
            db.rollback()
            logger.error(f"[JOB {job_id}] Failed to update job database record status: {db_err}")
        finally:
            db.close()

    except Exception as e:
        logger.exception(f"[JOB {job_id}] Pipeline execution failed.")
        db = SessionLocal()
        try:
            job = db.query(PhotogrammetryModel).filter(PhotogrammetryModel.id == uuid.UUID(job_id)).first()
            if job:
                job.status = "Failed"
                db.commit()
            logger.info(f"[JOB {job_id}] Job database record marked as Failed.")
        except Exception as db_err:
            db.rollback()
            logger.error(f"[JOB {job_id}] Failed to update job database record status: {db_err}")
        finally:
            db.close()

    finally:
        # Cleanup temporary workspace
        try:
            if os.path.exists(job_dir):
                shutil.rmtree(job_dir)
                logger.info(f"[JOB {job_id}] Cleaned up temporary directory: {job_dir}")
        except Exception as cleanup_err:
            logger.error(f"[JOB {job_id}] Failed to clean up temp dir {job_dir}: {cleanup_err}")


@app.get("/")
def read_root():
    return {
        "service": "photogrammetry-backend",
        "status": "running",
        "port": 8004
    }


@app.post("/trigger/{case_id}")
def trigger_reconstruction(case_id: str, payload: TriggerRequest, db: Session = Depends(get_db)):
    """
    Triggers the photogrammetry pipeline for a video evidence item.
    Creates a database job log and spawns a background processing thread.
    """
    try:
        # Insert job into DB with default status 'Processing'
        db_job = PhotogrammetryModel(
            id=uuid.uuid4(),
            case_id=uuid.UUID(case_id),
            evidence_id=uuid.UUID(payload.evidence_id),
            status="Processing"
        )
        db.add(db_job)
        db.commit()
        db.refresh(db_job)

        # Spawn pipeline processing thread
        thread = threading.Thread(
            target=run_pipeline_background,
            args=(str(db_job.id), case_id, payload.file_url)
        )
        thread.start()

        return {
            "job_id": str(db_job.id),
            "status": "Processing"
        }

    except Exception as e:
        logger.exception("Failed to trigger reconstruction request.")
        raise HTTPException(status_code=500, detail=f"Trigger failed: {str(e)}")


@app.get("/status/{case_id}")
def get_reconstruction_status(case_id: str, db: Session = Depends(get_db)):
    """
    Queries and returns the latest photogrammetry job status for the given case_id.
    """
    try:
        row = db.query(PhotogrammetryModel) \
            .filter(PhotogrammetryModel.case_id == uuid.UUID(case_id)) \
            .order_by(PhotogrammetryModel.created_at.desc()) \
            .first()

        if not row:
            raise HTTPException(
                status_code=404,
                detail="No photogrammetry reconstruction jobs found for this case."
            )

        return {
            "status": row.status,
            "model_url": row.model_url,
            "point_cloud_url": row.point_cloud_url,
            "frame_count": row.frame_count,
            "created_at": row.created_at.isoformat().replace("+00:00", "Z") if row.created_at else None,
            "completed_at": row.completed_at.isoformat().replace("+00:00", "Z") if row.completed_at else None
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to query job status for case: {case_id}")
        raise HTTPException(status_code=500, detail=f"Database query failed: {str(e)}")


if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=8004, reload=True)
