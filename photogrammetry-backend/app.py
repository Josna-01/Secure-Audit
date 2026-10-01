import os
import uuid
import shutil
import logging
import threading
import datetime
import time
import requests
from urllib.parse import urlparse
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

from fastapi.staticfiles import StaticFiles
from services.evaluator import PhotogrammetryEvaluator

# Load environment variables from this service's .env file
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))

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
    local_path: str | None = None

class EvaluationRequest(BaseModel):
    gt_length: float | None = None
    gt_width: float | None = None
    gt_height: float | None = None
    scale: float | None = None
    unit: str = "cm"

def _set_step(job_id: str, step: int):
    """Write the current pipeline step to the DB for live UI progress tracking."""
    try:
        db = SessionLocal()
        try:
            job = db.query(PhotogrammetryModel).filter(PhotogrammetryModel.id == uuid.UUID(job_id)).first()
            if job:
                job.current_step = step
                db.commit()
        finally:
            db.close()
    except Exception as exc:
        logger.warning(f"[JOB {job_id}] Could not write step {step} to DB: {exc}")


def run_pipeline_background(job_id: str, case_id: str, file_url: str, local_path: str | None = None):
    """
    Executes the full photogrammetry pipeline asynchronously:
    1. Downloads video from remote storage
    2. Extracts raw frames
    3. Selects the highest quality frames
    4. Runs COLMAP 3D reconstruction (Feature Matching + Sparse Reconstruction)
    5. Runs COLMAP Dense Reconstruction
    6. Runs Open3D Mesh Generation
    7. Uploads outputs to Supabase Storage
    8. Completed
    """
    logger.info(f"[JOB {job_id}] Starting background processing pipeline.")
    pipeline_started_at = time.monotonic()

    # Workspace directory mapping
    # Keep job workspaces isolated and retain them for traceability/debugging.
    job_dir = os.path.join(os.getenv("PHOTOGRAMMETRY_WORK_DIR", os.path.join(BASE_DIR, "jobs")), job_id)
    frames_dir = os.path.join(job_dir, "frames")
    selected_dir = os.path.join(job_dir, "selected")
    roi_dir = os.path.join(job_dir, "roi_frames")
    colmap_dir = os.path.join(job_dir, "colmap")
    output_dir = os.path.join(job_dir, "output")
    source_name = local_path or urlparse(file_url).path
    source_extension = os.path.splitext(source_name)[1].lower()
    if source_extension not in {".mp4", ".mov", ".avi", ".mkv"}:
        source_extension = ".mp4"
    video_path = os.path.join(job_dir, f"input_video{source_extension}")

    try:
        db = SessionLocal()
        try:
            job = db.query(PhotogrammetryModel).filter(PhotogrammetryModel.id == uuid.UUID(job_id)).first()
            if not job:
                raise RuntimeError("Photogrammetry job disappeared before processing could begin.")
            job.status = "Processing"
            job.current_step = 1
            db.commit()
        finally:
            db.close()
        # Create temporary working directories
        os.makedirs(job_dir, exist_ok=True)
        os.makedirs(frames_dir, exist_ok=True)
        os.makedirs(selected_dir, exist_ok=True)
        os.makedirs(colmap_dir, exist_ok=True)
        os.makedirs(output_dir, exist_ok=True)

        # 1. Resolve the evidence.  Locally stored evidence is deliberately
        # passed by the authenticated main backend, while Supabase evidence is
        # downloaded through its public URL.
        if local_path:
            if not os.path.isfile(local_path):
                raise FileNotFoundError(f"Resolved local evidence file does not exist: {local_path}")
            logger.info("[JOB %s] Step 1/5: Copying resolved local evidence.", job_id)
            shutil.copy2(local_path, video_path)
        else:
            logger.info(f"[JOB {job_id}] Step 1/5: Downloading video from {file_url}...")
            response = requests.get(file_url, stream=True, timeout=(10, 300))
            response.raise_for_status()
            with open(video_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
        if not os.path.exists(video_path) or os.path.getsize(video_path) == 0:
            raise RuntimeError("Downloaded evidence video is empty.")
        logger.info(f"[JOB {job_id}] Video downloaded successfully to {video_path}")

        # 2. Extract frames from video
        logger.info(f"[JOB {job_id}] Step 2/5: Extracting frames...")
        _set_step(job_id, 2)
        extractor = FrameExtractor()
        interval = os.getenv("PHOTOGRAMMETRY_OBJECT_INTERVAL_SECONDS", "").strip()
        start_seconds, end_seconds = 0.0, None
        if interval:
            start_seconds, end_seconds = (float(value.strip()) for value in interval.split(","))
        extracted_paths = extractor.extract(video_path, frames_dir, fps=2,
                                            start_seconds=start_seconds, end_seconds=end_seconds)
        logger.info(f"[JOB {job_id}] Quality-mode candidate frames: {len(extracted_paths)} at 2 FPS.")

        # 3. Select best frames
        logger.info(f"[JOB {job_id}] Step 3/5: Selecting best frame candidates...")
        _set_step(job_id, 3)
        selector = FrameSelector()
        selected_paths = selector.select(extracted_paths, max_frames=60)
        source_order = {
            os.path.normcase(os.path.normpath(path)): index
            for index, path in enumerate(extracted_paths)
        }
        selected_paths.sort(key=lambda path: source_order[os.path.normcase(os.path.normpath(path))])
        logger.info(
            f"[JOB {job_id}] Quality-mode selected frames: {len(selected_paths)}/{len(extracted_paths)} "
            "in chronological source-video order."
        )

        if len(selected_paths) < 2:
            raise ValueError("Fewer than two frames passed quality and similarity criteria; reconstruction cannot proceed.")

        # Copy selected frames to selection workspace folder
        for idx, path in enumerate(selected_paths):
            dest_name = f"frame_{idx:03d}.jpg"
            dest_path = os.path.join(selected_dir, dest_name)
            shutil.copy(path, dest_path)

        # 4. Execute COLMAP Reconstruction
        logger.info(f"[JOB {job_id}] Step 4/5: Running COLMAP reconstruction (SfM + MVS)...")
        _set_step(job_id, 4)
        runner = ColmapRunner()
        colmap_res = runner.reconstruct(selected_dir, colmap_dir, minimum_registration_ratio=0.8)
        dense_ply = colmap_res["dense_ply_path"]
        sparse_stats = colmap_res["sparse_stats"]
        registration_percent = 100 * sparse_stats["registered_image_count"] / len(selected_paths)
        logger.info(
            f"[JOB {job_id}] SfM passed quality gate: registered "
            f"{sparse_stats['registered_image_count']}/{len(selected_paths)} "
            f"({registration_percent:.2f}%), sparse points={sparse_stats['sparse_point_count']}."
        )
        logger.info(f"[JOB {job_id}] COLMAP completed. Dense point cloud created: {dense_ply}")

        # 5. Open3D Post-Processing
        logger.info(f"[JOB {job_id}] Step 5/5: Running Open3D cleaning and mesh reconstruction...")
        _set_step(job_id, 6)
        processor = Open3DProcessor()
        o3d_res = processor.process(dense_ply, output_dir)
        logger.info(
            f"[JOB {job_id}] Geometry diagnostics: dense points={o3d_res['dense_point_count']}, "
            f"filtered points={o3d_res['filtered_point_count']}, "
            f"mesh vertices={o3d_res['mesh_vertex_count']}, triangles={o3d_res['mesh_triangle_count']}."
        )
        logger.info(f"[JOB {job_id}] Open3D processing completed. Assets generated.")

        # 6. Upload processed artifacts to Supabase Storage
        model_ply_local = o3d_res["ply_url"]
        model_glb_local = o3d_res["glb_url"]

        # The processor validates geometry before returning. Retain an additional
        # file-level guard here so failed/empty exports are never published.
        for artifact_path, artifact_name in ((model_ply_local, "PLY"), (model_glb_local, "GLB")):
            if not os.path.isfile(artifact_path) or os.path.getsize(artifact_path) == 0:
                raise RuntimeError(f"Generated {artifact_name} artifact is missing or empty.")

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
        _set_step(job_id, 7)
        completed_at = datetime.datetime.now(datetime.timezone.utc)
        db = SessionLocal()
        try:
            job = db.query(PhotogrammetryModel).filter(PhotogrammetryModel.id == uuid.UUID(job_id)).first()
            if not job:
                raise RuntimeError("Photogrammetry job disappeared before completion could be saved.")
            job.status = "Completed"
            job.current_step = 8
            job.model_url = glb_url
            job.point_cloud_url = ply_url
            job.frame_count = len(selected_paths)
            job.completed_at = completed_at
            job.error_message = None
            db.commit()
            logger.info(
                f"[JOB {job_id}] Pipeline execution completed successfully in "
                f"{time.monotonic() - pipeline_started_at:.2f}s. Database record updated."
            )
        except Exception as db_err:
            db.rollback()
            logger.error(f"[JOB {job_id}] Failed to update job database record status: {db_err}")
            raise RuntimeError(f"Could not persist completed job state: {db_err}") from db_err
        finally:
            db.close()

    except BaseException as e:
        logger.error(f"[JOB {job_id}] Pipeline failed after {time.monotonic() - pipeline_started_at:.2f}s: {e}")
        logger.exception(f"[JOB {job_id}] Pipeline execution failed.")
        db = SessionLocal()
        try:
            job = db.query(PhotogrammetryModel).filter(PhotogrammetryModel.id == uuid.UUID(job_id)).first()
            if job:
                job.status = "Failed"
                job.error_message = str(e)[:4000] if str(e) else type(e).__name__
                job.completed_at = datetime.datetime.now(datetime.timezone.utc)
                db.commit()
            logger.info(f"[JOB {job_id}] Job database record marked as Failed.")
        except Exception as db_err:
            db.rollback()
            logger.error(f"[JOB {job_id}] Failed to update job database record status: {db_err}")
        finally:
            db.close()

    # Workspaces are deliberately retained; a scheduled retention policy can remove
    # completed jobs after the evidence-retention period.


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
            status="Pending"
        )
        db.add(db_job)
        db.commit()
        db.refresh(db_job)

        # Spawn pipeline processing thread
        thread = threading.Thread(
            target=run_pipeline_background,
            args=(str(db_job.id), case_id, payload.file_url, payload.local_path),
            name=f"photogrammetry-{db_job.id}",
            daemon=True,
        )
        thread.start()

        return {
            "job_id": str(db_job.id),
            "case_id": str(db_job.case_id),
            "evidence_id": str(db_job.evidence_id),
            "status": "Pending"
        }

    except Exception as e:
        db.rollback()
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
            "job_id": str(row.id),
            "case_id": str(row.case_id),
            "evidence_id": str(row.evidence_id) if row.evidence_id else None,
            "status": row.status,
            "current_step": row.current_step or 0,
            "model_url": row.model_url,
            "point_cloud_url": row.point_cloud_url,
            "frame_count": row.frame_count,
            "created_at": row.created_at.isoformat().replace("+00:00", "Z") if row.created_at else None,
            "completed_at": row.completed_at.isoformat().replace("+00:00", "Z") if row.completed_at else None,
            "error_message": row.error_message
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to query job status for case: {case_id}")
        raise HTTPException(status_code=500, detail=f"Database query failed: {str(e)}")


@app.get("/status/job/{job_id}")
def get_reconstruction_status_by_job(job_id: str, db: Session = Depends(get_db)):
    """Return exactly the reconstruction run that the caller started."""
    try:
        row = db.query(PhotogrammetryModel).filter(PhotogrammetryModel.id == uuid.UUID(job_id)).first()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="job_id must be a valid UUID.") from exc
    if not row:
        raise HTTPException(status_code=404, detail="Photogrammetry reconstruction job was not found.")
    return {
        "job_id": str(row.id), "case_id": str(row.case_id),
        "evidence_id": str(row.evidence_id) if row.evidence_id else None,
        "status": row.status, "current_step": row.current_step or 0,
        "model_url": row.model_url,
        "point_cloud_url": row.point_cloud_url, "frame_count": row.frame_count,
        "created_at": row.created_at.isoformat().replace("+00:00", "Z") if row.created_at else None,
        "completed_at": row.completed_at.isoformat().replace("+00:00", "Z") if row.completed_at else None,
        "error_message": row.error_message,
    }


@app.get("/jobs/{job_id}/evaluation")
def get_job_evaluation(job_id: str):
    """
    Retrieve or compute the evaluation metrics for a specific photogrammetry job.
    """
    jobs_dir = os.getenv("PHOTOGRAMMETRY_WORK_DIR", os.path.join(BASE_DIR, "jobs"))
    job_dir = os.path.join(jobs_dir, job_id)
    if not os.path.exists(job_dir):
        raise HTTPException(status_code=404, detail=f"Job directory not found for job_id: {job_id}")
    
    summary_path = os.path.join(job_dir, "evaluation", "evaluation_summary.json")
    if os.path.exists(summary_path):
        import json
        with open(summary_path, "r", encoding="utf-8") as f:
            return json.load(f)
    
    # Otherwise run evaluator on the fly
    evaluator = PhotogrammetryEvaluator(jobs_dir=jobs_dir)
    res = evaluator.evaluate_job(job_id)
    return res


@app.post("/jobs/{job_id}/evaluate")
def evaluate_job_endpoint(job_id: str, payload: EvaluationRequest | None = None):
    """
    Execute evaluation on a completed job with optional ground truth measurements.
    """
    jobs_dir = os.getenv("PHOTOGRAMMETRY_WORK_DIR", os.path.join(BASE_DIR, "jobs"))
    job_dir = os.path.join(jobs_dir, job_id)
    if not os.path.exists(job_dir):
        raise HTTPException(status_code=404, detail=f"Job directory not found for job_id: {job_id}")
    
    gt_dims = None
    scale = None
    unit = "cm"
    if payload:
        if payload.gt_length is not None and payload.gt_width is not None and payload.gt_height is not None:
            gt_dims = {
                "length": payload.gt_length,
                "width": payload.gt_width,
                "height": payload.gt_height
            }
        scale = payload.scale
        unit = payload.unit or "cm"
    
    evaluator = PhotogrammetryEvaluator(jobs_dir=jobs_dir)
    res = evaluator.evaluate_job(
        job_id=job_id,
        ground_truth_dimensions=gt_dims,
        dimension_unit=unit,
        scale=scale
    )
    return res


@app.get("/jobs/comparison")
def compare_jobs_endpoint():
    """
    Generate comparative analysis across all completed photogrammetry jobs.
    """
    jobs_dir = os.getenv("PHOTOGRAMMETRY_WORK_DIR", os.path.join(BASE_DIR, "jobs"))
    evaluator = PhotogrammetryEvaluator(jobs_dir=jobs_dir)
    available_jobs = evaluator.list_available_jobs()
    if not available_jobs:
        raise HTTPException(status_code=404, detail="No photogrammetry jobs found to compare.")
    
    output_dir = os.path.join(BASE_DIR, "evaluation_benchmark")
    summary = evaluator.compare_multiple_jobs(available_jobs, output_dir=output_dir)
    return summary


# Mount jobs directory for direct access to evaluation artifacts (reports, charts, models)
jobs_mount_dir = os.getenv("PHOTOGRAMMETRY_WORK_DIR", os.path.join(BASE_DIR, "jobs"))
if os.path.exists(jobs_mount_dir):
    app.mount("/artifacts/jobs", StaticFiles(directory=jobs_mount_dir), name="job_artifacts")


if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=8004, reload=True)
