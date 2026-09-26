"""Run the existing photogrammetry services against the real sample video.

This is a diagnostic harness only: it neither mocks COLMAP nor creates geometry.
"""
import json
import os
import shutil
import sqlite3
import sys
import time
from pathlib import Path

import cv2
import open3d as o3d

from services.colmap_runner import ColmapRunner
from services.frame_extractor import FrameExtractor
from services.frame_selector import FRAME_SELECTOR_CONFIGS, FrameSelector
from services.open3d_processor import Open3DProcessor


ROOT = Path(__file__).resolve().parent
VIDEO = ROOT / "test_data" / "sampleVideo.mp4"
RUN = ROOT / "test_runs" / f"baseline_{int(time.time())}"
FRAMES = RUN / "frames"
SELECTED = RUN / "selected"
COLMAP = RUN / "colmap"
OUTPUT = RUN / "output"


def video_metrics():
    cap = cv2.VideoCapture(str(VIDEO))
    if not cap.isOpened():
        raise RuntimeError(f"Could not open {VIDEO}")
    fps = cap.get(cv2.CAP_PROP_FPS)
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cap.release()
    return {
        "width": width,
        "height": height,
        "fps": fps,
        "frame_count": frame_count,
        "duration_seconds": frame_count / fps if fps else None,
    }


def selection_metrics(paths, mode):
    config = FRAME_SELECTOR_CONFIGS[mode]
    reasons = {"invalid": 0, "blur": 0, "lighting": 0, "similarity": 0}
    accepted = []
    previous = None
    for path in paths:
        image = cv2.imread(path)
        if image is None:
            reasons["invalid"] += 1
            continue
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        if cv2.Laplacian(gray, cv2.CV_64F).var() < config["blur_threshold"]:
            reasons["blur"] += 1
            continue
        if float(cv2.cvtColor(image, cv2.COLOR_BGR2HSV)[:, :, 2].mean()) < config["lighting_threshold"]:
            reasons["lighting"] += 1
            continue
        if previous is not None and float(cv2.absdiff(gray, previous).mean()) < config["similarity_threshold"]:
            reasons["similarity"] += 1
            continue
        previous = gray
        accepted.append(path)
    return config, reasons, accepted


def sqlite_metrics(database):
    if not database.exists():
        return {}
    connection = sqlite3.connect(database)
    try:
        images = connection.execute("SELECT image_id, rows FROM keypoints").fetchall()
        pairs = connection.execute("SELECT rows FROM two_view_geometries").fetchall()
        return {
            "images": len(images),
            "sift_features_per_image": {str(image_id): count for image_id, count in images},
            "total_geometric_matches": sum(count for (count,) in pairs),
            "matched_pairs": len(pairs),
        }
    finally:
        connection.close()


def sparse_metrics(path):
    if not path.exists():
        return {}
    reconstruction = o3d.io.read_point_cloud(str(path))
    return {"sparse_points": len(reconstruction.points)}


def main():
    if not VIDEO.exists():
        raise FileNotFoundError(VIDEO)
    for directory in (FRAMES, SELECTED, COLMAP, OUTPUT):
        directory.mkdir(parents=True, exist_ok=True)
    report = {"run_dir": str(RUN), "video": video_metrics()}

    started = time.perf_counter()
    extracted = FrameExtractor().extract(str(VIDEO), str(FRAMES), fps=1)
    report["extraction"] = {"frames": len(extracted), "seconds": time.perf_counter() - started}

    mode = os.environ.get("PHOTOGRAMMETRY_MODE", "TEST").upper()
    config, reasons, _ = selection_metrics(extracted, mode)
    started = time.perf_counter()
    selected = FrameSelector().select(extracted, max_frames=25)
    report["selection"] = {
        "mode": mode,
        "thresholds": config,
        "selected": len(selected),
        "rejected": len(extracted) - len(selected),
        "reasons_before_max_frame_cap": reasons,
        "seconds": time.perf_counter() - started,
    }
    for index, source in enumerate(selected):
        shutil.copy2(source, SELECTED / f"frame_{index:03d}.jpg")

    started = time.perf_counter()
    try:
        result = ColmapRunner().reconstruct(str(SELECTED), str(COLMAP))
        report["colmap"] = {"status": "passed", "seconds": time.perf_counter() - started, **sqlite_metrics(COLMAP / "database.db")}
        fused = Path(result["dense_ply_path"])
        cloud = o3d.io.read_point_cloud(str(fused))
        report["dense"] = {"fused_ply": str(fused), "points": len(cloud.points), "bytes": fused.stat().st_size}
    except Exception as error:
        report["colmap"] = {"status": "failed", "seconds": time.perf_counter() - started, "error": str(error), **sqlite_metrics(COLMAP / "database.db")}
        print(json.dumps(report, indent=2), flush=True)
        return 1

    started = time.perf_counter()
    try:
        mesh_result = Open3DProcessor().process(str(fused), str(OUTPUT))
        mesh = o3d.io.read_triangle_mesh(mesh_result["glb_url"])
        report["mesh"] = {
            "status": "passed",
            "seconds": time.perf_counter() - started,
            "vertices": len(mesh.vertices),
            "triangles": len(mesh.triangles),
            "model_ply": str(OUTPUT / "model.ply"),
            "model_glb": str(OUTPUT / "model.glb"),
            "model_glb_bytes": (OUTPUT / "model.glb").stat().st_size,
        }
    except Exception as error:
        report["mesh"] = {"status": "failed", "seconds": time.perf_counter() - started, "error": str(error)}
    print(json.dumps(report, indent=2), flush=True)
    return 0 if report["mesh"]["status"] == "passed" else 1


if __name__ == "__main__":
    sys.exit(main())
