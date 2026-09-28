"""
Controlled Maximum-Quality 60-Frame Photogrammetry Reconstruction Experiment.
Preserves existing working pipeline and COLMAP CUDA MVS + Open3D stack.
"""
import os
import sys
import time
import json
import shutil
import struct
import logging
import numpy as np
import open3d as o3d

from services.frame_extractor import FrameExtractor
from services.frame_selector import FrameSelector
from services.colmap_runner import ColmapRunner
from services.open3d_processor import Open3DProcessor

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("max_quality_experiment")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
VIDEO_PATH = r"C:\Users\amish\Desktop\Secure Audit\backend\uploads\cases\9e4d6ff1-f096-4495-b84a-1364e2912e92\814d4430-523f-4f58-a6e1-de98873bdd57_tt_playground_neural.mp4"
BASELINE_JOB_DIR = os.path.join(BASE_DIR, "jobs", "6b41c4db-a6e4-43ca-bbae-e9531fe7f235")
EXP_JOB_DIR = os.path.join(BASE_DIR, "jobs", "max_quality_60f_experiment")

def run_experiment():
    total_start_time = time.monotonic()
    runtimes = {}

    if not os.path.isfile(VIDEO_PATH):
        raise FileNotFoundError(f"Input video not found: {VIDEO_PATH}")

    # Set up workspace
    frames_dir = os.path.join(EXP_JOB_DIR, "frames")
    selected_dir = os.path.join(EXP_JOB_DIR, "selected")
    colmap_dir = os.path.join(EXP_JOB_DIR, "colmap")
    output_dir = os.path.join(EXP_JOB_DIR, "output")

    os.makedirs(EXP_JOB_DIR, exist_ok=True)
    os.makedirs(frames_dir, exist_ok=True)
    os.makedirs(selected_dir, exist_ok=True)
    os.makedirs(colmap_dir, exist_ok=True)
    os.makedirs(output_dir, exist_ok=True)

    # 1. FRAME EXTRACTION (~4 FPS for ~15 second video)
    t0 = time.monotonic()
    logger.info("--- Stage 1: Frame Extraction at 4 FPS ---")
    extractor = FrameExtractor()
    extracted_paths = extractor.extract(VIDEO_PATH, frames_dir, fps=4)
    runtimes["frame_extraction"] = time.monotonic() - t0
    logger.info(f"Extracted {len(extracted_paths)} candidate frames in {runtimes['frame_extraction']:.2f}s")

    # 2. FRAME SELECTION (up to 60 frames, chronological, quality filtered)
    t0 = time.monotonic()
    logger.info("--- Stage 2: Frame Selection (Target: 60 frames) ---")
    selector = FrameSelector()
    selected_paths = selector.select(extracted_paths, max_frames=60, mode="PRODUCTION")
    source_order = {
        os.path.normcase(os.path.normpath(path)): idx
        for idx, path in enumerate(extracted_paths)
    }
    selected_paths.sort(key=lambda p: source_order[os.path.normcase(os.path.normpath(p))])
    runtimes["frame_selection"] = time.monotonic() - t0
    logger.info(f"Selected {len(selected_paths)} frames in {runtimes['frame_selection']:.2f}s")
    frame_selection_diagnostics = selector.last_diagnostics

    # Copy selected frames to workspace
    for idx, path in enumerate(selected_paths):
        dest_name = f"frame_{idx:03d}.jpg"
        shutil.copy2(path, os.path.join(selected_dir, dest_name))

    # 3-6. COLMAP SfM & MVS
    t0 = time.monotonic()
    logger.info("--- Stages 3-6: COLMAP Reconstruction (SfM + MVS + Stereo Fusion) ---")
    runner = ColmapRunner()
    colmap_result = runner.reconstruct(selected_dir, colmap_dir, minimum_registration_ratio=0.8)
    runtimes["colmap_total"] = time.monotonic() - t0
    logger.info(f"COLMAP completed in {runtimes['colmap_total']:.2f}s")

    fused_ply_path = colmap_result["dense_ply_path"]
    sparse_stats = colmap_result["sparse_stats"]

    # 7. OPEN3D PROCESSING (Mesh generation & cleanup)
    t0 = time.monotonic()
    logger.info("--- Stage 7: Open3D Cleanup & Poisson Surface Mesh Reconstruction ---")
    processor = Open3DProcessor()
    o3d_result = processor.process(fused_ply_path, output_dir, poisson_depth=9)
    runtimes["open3d_processing"] = time.monotonic() - t0
    logger.info(f"Open3D processing completed in {runtimes['open3d_processing']:.2f}s")

    runtimes["total_experiment"] = time.monotonic() - total_start_time

    # 8. PROGRAMMATIC VALIDATION & INSPECTION
    logger.info("--- Stage 8: Programmatic Validation & Analysis ---")
    dense_ply = o3d_result["ply_url"]
    mesh_glb = o3d_result["glb_url"]
    mesh_ply = os.path.join(output_dir, "mesh.ply")

    # Read point clouds
    raw_pcd = o3d.io.read_point_cloud(fused_ply_path)
    raw_pts = np.asarray(raw_pcd.points)
    filt_pcd = o3d.io.read_point_cloud(dense_ply)
    filt_pts = np.asarray(filt_pcd.points)

    raw_count = len(raw_pts)
    filt_count = len(filt_pts)
    removed_count = raw_count - filt_count
    removed_pct = (removed_count / raw_count * 100.0) if raw_count > 0 else 0.0

    raw_finite = bool(np.isfinite(raw_pts).all())
    filt_finite = bool(np.isfinite(filt_pts).all())
    raw_has_colors = bool(raw_pcd.has_colors())
    filt_has_colors = bool(filt_pcd.has_colors())
    raw_has_normals = bool(raw_pcd.has_normals())
    filt_has_normals = bool(filt_pcd.has_normals())

    bbox = filt_pcd.get_axis_aligned_bounding_box()
    bbox_min = [float(v) for v in bbox.get_min_bound()]
    bbox_max = [float(v) for v in bbox.get_max_bound()]
    bbox_extent = [float(v) for v in bbox.get_extent()]

    # Read GLB structure
    glb_size = os.path.getsize(mesh_glb)
    ply_size = os.path.getsize(dense_ply)
    mesh_ply_size = os.path.getsize(mesh_ply) if os.path.exists(mesh_ply) else 0
    fused_ply_size = os.path.getsize(fused_ply_path)

    glb_valid = False
    glb_vertices = 0
    glb_triangles = 0
    with open(mesh_glb, "rb") as f:
        magic, version, length = struct.unpack("<4sII", f.read(12))
        if magic == b"glTF" and version == 2 and length == glb_size:
            glb_valid = True
            chunk_len, chunk_type = struct.unpack("<I4s", f.read(8))
            json_data = json.loads(f.read(chunk_len).decode("utf-8"))
            accessors = json_data.get("accessors", [])
            if len(accessors) >= 2:
                glb_triangles = accessors[0].get("count", 0) // 3
                glb_vertices = accessors[1].get("count", 0)

    # MVS view counts
    depth_maps_dir = os.path.join(colmap_dir, "dense", "stereo", "depth_maps")
    normal_maps_dir = os.path.join(colmap_dir, "dense", "stereo", "normal_maps")
    depth_files = os.listdir(depth_maps_dir) if os.path.exists(depth_maps_dir) else []
    normal_files = os.listdir(normal_maps_dir) if os.path.exists(normal_maps_dir) else []

    geom_depth_count = len([f for f in depth_files if "geometric" in f])
    photo_depth_count = len([f for f in depth_files if "photometric" in f])
    geom_normal_count = len([f for f in normal_files if "geometric" in f])
    photo_normal_count = len([f for f in normal_files if "photometric" in f])

    # Baseline comparisons
    baseline_stats = {
        "job_id": "6b41c4db-a6e4-43ca-bbae-e9531fe7f235",
        "selected_frames": 30,
        "registered_images": 30,
        "registration_percent": 100.0,
        "sparse_points": 13956,
        "observations": 47820,
        "mean_track_length": 47820 / 13956,
        "mean_reprojection_error": 0.519916,
        "mvs_views": 30,
        "raw_dense_points": 842136,
        "filtered_dense_points": 837639,
        "removed_points": 842136 - 837639,
        "removed_percent": 0.53,
        "mesh_vertices": 88504,
        "mesh_triangles": 175746,
        "bbox_extent": [43.71, 5.18, 30.40],
        "fused_ply_size_bytes": 43105436,
        "model_glb_size_bytes": 7061340,
        "model_ply_size_bytes": 42719855,
    }

    report = {
        "configuration": {
            "target_frames": 60,
            "extraction_fps": 4,
            "feature_type": "SIFT",
            "max_features_per_image": 20000,
            "sift_peak_threshold": 0.004,
            "domain_size_pooling": True,
            "matcher": "sequential_matcher",
            "overlap": 15,
            "guided_matching": True,
            "mvs_stereo_num_iterations": 7,
            "mvs_stereo_num_samples": 20,
            "geom_consistency": True,
            "fusion_min_num_pixels": 3,
            "fusion_check_num_images": 60,
            "fusion_max_reproj_error": 1.5,
            "poisson_depth": 9,
            "bbox_crop_scale": 1.25,
            "outlier_std_ratio": 3.5,
        },
        "frame_selection": {
            "total_extracted": len(extracted_paths),
            "total_selected": len(selected_paths),
            "diagnostics": frame_selection_diagnostics,
        },
        "sfm": {
            "candidate_images": len(selected_paths),
            "registered_images": sparse_stats["registered_image_count"],
            "registration_percent": (sparse_stats["registered_image_count"] / len(selected_paths)) * 100.0,
            "sparse_points": sparse_stats["sparse_point_count"],
            "observations": sparse_stats.get("observation_count"),
            "mean_track_length": (sparse_stats.get("observation_count") / sparse_stats["sparse_point_count"]) if sparse_stats.get("observation_count") else None,
            "mean_reprojection_error": sparse_stats.get("mean_reprojection_error"),
            "selected_sparse_dir": colmap_result["sparse_path"],
        },
        "mvs": {
            "views_processed": len(selected_paths),
            "depth_maps_geometric": geom_depth_count,
            "depth_maps_photometric": photo_depth_count,
            "normal_maps_geometric": geom_normal_count,
            "normal_maps_photometric": photo_normal_count,
            "total_depth_maps": len(depth_files),
            "total_normal_maps": len(normal_files),
        },
        "dense_point_cloud": {
            "raw_dense_points": raw_count,
            "filtered_dense_points": filt_count,
            "removed_points": removed_count,
            "removed_percent": removed_pct,
            "finite_points": filt_finite,
            "has_colors": filt_has_colors,
            "has_normals": filt_has_normals,
            "bbox_min": bbox_min,
            "bbox_max": bbox_max,
            "bbox_extent": bbox_extent,
        },
        "mesh": {
            "glb_valid": glb_valid,
            "mesh_vertices": glb_vertices or o3d_result["mesh_vertex_count"],
            "mesh_triangles": glb_triangles or o3d_result["mesh_triangle_count"],
            "glb_file_size_bytes": glb_size,
            "model_ply_file_size_bytes": ply_size,
            "mesh_ply_file_size_bytes": mesh_ply_size,
            "fused_ply_file_size_bytes": fused_ply_size,
        },
        "runtimes_seconds": runtimes,
        "baseline_comparison": {
            "baseline": baseline_stats,
            "delta": {
                "selected_frames": len(selected_paths) - baseline_stats["selected_frames"],
                "sparse_points_diff": sparse_stats["sparse_point_count"] - baseline_stats["sparse_points"],
                "sparse_points_pct_change": ((sparse_stats["sparse_point_count"] - baseline_stats["sparse_points"]) / baseline_stats["sparse_points"]) * 100.0,
                "raw_dense_points_diff": raw_count - baseline_stats["raw_dense_points"],
                "raw_dense_points_pct_change": ((raw_count - baseline_stats["raw_dense_points"]) / baseline_stats["raw_dense_points"]) * 100.0,
                "filtered_dense_points_diff": filt_count - baseline_stats["filtered_dense_points"],
                "filtered_dense_points_pct_change": ((filt_count - baseline_stats["filtered_dense_points"]) / baseline_stats["filtered_dense_points"]) * 100.0,
                "mesh_vertices_diff": (glb_vertices or o3d_result["mesh_vertex_count"]) - baseline_stats["mesh_vertices"],
                "mesh_vertices_pct_change": (((glb_vertices or o3d_result["mesh_vertex_count"]) - baseline_stats["mesh_vertices"]) / baseline_stats["mesh_vertices"]) * 100.0,
                "mesh_triangles_diff": (glb_triangles or o3d_result["mesh_triangle_count"]) - baseline_stats["mesh_triangles"],
                "mesh_triangles_pct_change": (((glb_triangles or o3d_result["mesh_triangle_count"]) - baseline_stats["mesh_triangles"]) / baseline_stats["mesh_triangles"]) * 100.0,
            }
        },
        "artifact_paths": {
            "fused_ply": fused_ply_path,
            "filtered_point_cloud_ply": dense_ply,
            "mesh_ply": mesh_ply,
            "model_glb": mesh_glb,
        }
    }

    report_path = os.path.join(EXP_JOB_DIR, "experiment_report.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    logger.info(f"Experiment completed successfully! Report saved to {report_path}")
    print("\n" + "="*70)
    print("EXPERIMENT EXECUTION SUMMARY")
    print("="*70)
    print(f"Frames: {len(selected_paths)}/{len(extracted_paths)} (Registered: {sparse_stats['registered_image_count']})")
    print(f"Sparse points: {sparse_stats['sparse_point_count']} (Mean reproj err: {sparse_stats.get('mean_reprojection_error'):.4f} px)")
    print(f"Raw dense points: {raw_count:,}")
    print(f"Filtered dense points: {filt_count:,}")
    print(f"Mesh vertices: {glb_vertices:,} | Triangles: {glb_triangles:,}")
    print(f"Total Runtime: {runtimes['total_experiment']:.2f}s ({runtimes['total_experiment']/60:.2f} min)")
    print(f"GLB Output: {mesh_glb} ({glb_size:,} bytes)")
    print(f"PLY Output: {dense_ply} ({ply_size:,} bytes)")
    print("="*70)

if __name__ == "__main__":
    run_experiment()
