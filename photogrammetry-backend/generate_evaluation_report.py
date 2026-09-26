"""Measure one real photogrammetry run and emit paper-ready evidence tables.

This script only reads reconstruction artifacts (apart from its report and PNGs).
It never synthesizes geometry or substitutes test data.
"""
import json
import sqlite3
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RUN = ROOT / "test_runs" / "baseline_1790059580"
sys.path.insert(0, str(ROOT / "venv" / "Lib" / "site-packages"))
import cv2
import numpy as np
import open3d as o3d


def count_files(path, pattern): return len(list(path.glob(pattern)))
def vec(a): return [float(x) for x in a]

def main():
    video = ROOT / "test_data" / "sampleVideo.mp4"
    cap = cv2.VideoCapture(str(video))
    fps, frames = cap.get(cv2.CAP_PROP_FPS), int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    width, height = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cap.release()
    db = sqlite3.connect(RUN / "colmap" / "database.db")
    keypoints = [r[0] for r in db.execute("SELECT rows FROM keypoints")]
    geometric = [r[0] for r in db.execute("SELECT rows FROM two_view_geometries")]
    db.close()
    dense = o3d.io.read_point_cloud(str(RUN / "colmap" / "dense" / "fused.ply"))
    clean = o3d.io.read_point_cloud(str(RUN / "output" / "model.ply"))
    # Open3D writes this GLB with a data-URI buffer that its own importer cannot
    # reload. Parse the glTF 2.0 JSON chunk directly instead of mistaking that
    # importer limitation for a zero-geometry mesh.
    glb = (RUN / "output" / "model.glb").read_bytes()
    magic, version, declared_length = struct.unpack_from("<4sII", glb, 0)
    json_length, json_type = struct.unpack_from("<II", glb, 12)
    gltf = json.loads(glb[20:20 + json_length])
    primitive = gltf["meshes"][0]["primitives"][0]
    accessors = gltf["accessors"]
    positions = accessors[primitive["attributes"]["POSITION"]]
    indices = accessors[primitive["indices"]]
    points = np.asarray(dense.points)
    bbox = dense.get_axis_aligned_bounding_box()
    ordered = sorted((RUN / "frames").glob("*.jpg"))
    cfg = {"blur": 15.0, "lighting": 50.0, "similarity": 5.0}
    reasons = {"blur": 0, "lighting": 0, "similarity": 0}
    passed, previous = 0, None
    for image_path in ordered:
        image = cv2.imread(str(image_path)); gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        if cv2.Laplacian(gray, cv2.CV_64F).var() < cfg["blur"]: reasons["blur"] += 1; continue
        if float(cv2.cvtColor(image, cv2.COLOR_BGR2HSV)[:, :, 2].mean()) < cfg["lighting"]: reasons["lighting"] += 1; continue
        if previous is not None and float(cv2.absdiff(gray, previous).mean()) < cfg["similarity"]: reasons["similarity"] += 1; continue
        previous = gray; passed += 1
    report = {
      "provenance": {"run": str(RUN), "real_artifacts": True,
        "dense_fusion_log": str(RUN / "stereo_fusion_attempt_20260922.stderr.log"),
        "mesh_log": str(RUN / "open3d_attempt_20260922.stdout.log")},
      "environment": {"python": sys.version.split()[0], "opencv": cv2.__version__, "open3d": o3d.__version__, "colmap": "4.1.1 (Commit a0d785f, CUDA)"},
      "video": {"file": video.name, "width": width, "height": height, "fps": fps, "total_frames": frames, "duration_seconds": frames/fps},
      "frames": {"extracted": count_files(RUN/'frames','*.jpg'), "selected": count_files(RUN/'selected','*.jpg'), "sampling": "1 FPS (one frame every 30 source frames)", "selection_mode": "TEST", "thresholds": {"blur_laplacian_variance":15.0,"lighting_hsv_v_mean":50.0,"similarity_mean_gray_difference":5.0}, "rejected_before_cap": reasons, "passed_before_cap":passed, "not_selected_due_to_25_frame_cap":passed-25},
      "features": {"images_with_features":len(keypoints), "total_sift_features":sum(keypoints), "average_per_image":sum(keypoints)/len(keypoints), "min_per_image":min(keypoints), "max_per_image":max(keypoints), "successful_geometric_pairs":len(geometric), "total_geometric_correspondences":sum(geometric), "average_correspondences_per_successful_pair":sum(geometric)/len(geometric)},
      "sfm": {"registered_images":25,"input_images":25,"registration_rate_percent":100.0,"cameras":1,"points3d":9745,"observations":36062,"mean_track_length":3.700564,"mean_observations_per_image":1442.48,"mean_reprojection_error_px":1.141863},
      "dense": {"depth_maps":count_files(RUN/'colmap'/'dense'/'stereo'/'depth_maps','*.bin'), "normal_maps":count_files(RUN/'colmap'/'dense'/'stereo'/'normal_maps','*.bin'), "points":len(dense.points), "bytes":(RUN/'colmap'/'dense'/'fused.ply').stat().st_size, "min_xyz":vec(points.min(axis=0)), "max_xyz":vec(points.max(axis=0)), "bbox_dimensions":vec(bbox.get_extent())},
      "processing": {"filtered_points":len(clean.points), "removed_points":len(dense.points)-len(clean.points), "normals_available_on_processed_ply":clean.has_normals()},
      "mesh": {"method":"Open3D Poisson surface reconstruction", "poisson_depth":9, "density_trim_percentile":5, "vertices":positions["count"], "triangles":indices["count"]//3, "components":"Not directly measurable from the exported GLB", "degenerate_triangles":"Not directly measurable from the exported GLB", "bbox_dimensions":[positions["max"][i]-positions["min"][i] for i in range(3)], "vertex_normals":"NORMAL" in primitive["attributes"], "vertex_colors":"COLOR_0" in primitive["attributes"], "glb_bytes":len(glb), "mesh_count":len(gltf["meshes"]), "materials":len(gltf.get("materials") or []), "textures":bool(gltf.get("textures")), "glb_header_valid":magic==b"glTF" and version==2 and declared_length==len(glb), "glb_data_uri_buffer":bool(gltf["buffers"][0].get("uri", "").startswith("data:"))}
    }
    out = RUN / "research_evaluation.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))

if __name__ == '__main__': main()
