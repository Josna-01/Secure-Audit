"""Photogrammetry Evaluation and Research Reporting Module.

Collects objective metrics across the reconstruction pipeline (video, frame selection,
COLMAP SfM, MVS dense cloud, Open3D mesh), evaluates physical dimension accuracy,
generates research reports (Markdown, JSON, CSV), and exports comparison charts.
"""
import os
import glob
import json
import struct
import logging
from typing import Dict, Any, List, Optional, Tuple

import cv2
import numpy as np
import pandas as pd
import open3d as o3d
import matplotlib
matplotlib.use("Agg")  # Headless backend for headless server environments
import matplotlib.pyplot as plt

logger = logging.getLogger("photogrammetry-evaluator")
logger.setLevel(logging.INFO)


class PhotogrammetryEvaluator:
    """Comprehensive evaluation engine for 3D Photogrammetry reconstructions."""

    def __init__(self, jobs_root: str):
        self.jobs_root = os.path.abspath(jobs_root)

    def _resolve_job_dir(self, job_id_or_path: str) -> str:
        if os.path.isabs(job_id_or_path) and os.path.isdir(job_id_or_path):
            return job_id_or_path
        job_dir = os.path.join(self.jobs_root, job_id_or_path)
        if os.path.isdir(job_dir):
            return job_dir
        raise FileNotFoundError(f"Photogrammetry job directory not found: {job_id_or_path}")

    # --------------------------------------------------------------------------
    # 1. Metric Extraction Helpers
    # --------------------------------------------------------------------------
    def extract_video_metrics(self, job_dir: str) -> Dict[str, Any]:
        """Extracts input video metadata (resolution, FPS, duration, size)."""
        video_files = glob.glob(os.path.join(job_dir, "input_video.*"))
        if not video_files:
            # Check root of job for any .mp4/.mov
            video_files = glob.glob(os.path.join(job_dir, "*.mp4")) + glob.glob(os.path.join(job_dir, "*.mov"))

        if not video_files:
            return {
                "filename": None,
                "file_size_bytes": None,
                "file_size_mb": None,
                "resolution": None,
                "width": None,
                "height": None,
                "fps": None,
                "frame_count": None,
                "duration_seconds": None,
                "status": "unavailable"
            }

        video_path = video_files[0]
        file_size = os.path.getsize(video_path)
        cap = cv2.VideoCapture(video_path)

        if not cap.isOpened():
            return {
                "filename": os.path.basename(video_path),
                "file_size_bytes": file_size,
                "file_size_mb": round(file_size / (1024 * 1024), 2),
                "status": "unreadable"
            }

        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = float(cap.get(cv2.CAP_PROP_FPS))
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = round(total_frames / fps, 2) if fps > 0 else None
        cap.release()

        return {
            "filename": os.path.basename(video_path),
            "file_size_bytes": file_size,
            "file_size_mb": round(file_size / (1024 * 1024), 2),
            "resolution": f"{w}x{h}",
            "width": w,
            "height": h,
            "fps": round(fps, 2),
            "frame_count": total_frames,
            "duration_seconds": duration,
            "status": "available"
        }

    def extract_frame_metrics(self, job_dir: str) -> Dict[str, Any]:
        """Counts raw extracted frames and selected keyframes."""
        frames_dir = os.path.join(job_dir, "frames")
        selected_dir = os.path.join(job_dir, "selected")

        extracted_count = len(glob.glob(os.path.join(frames_dir, "*.[jJ][pP][gG]")) +
                              glob.glob(os.path.join(frames_dir, "*.[pP][nN][gG]"))) if os.path.isdir(frames_dir) else 0

        selected_count = len(glob.glob(os.path.join(selected_dir, "*.[jJ][pP][gG]")) +
                             glob.glob(os.path.join(selected_dir, "*.[pP][nN][gG]"))) if os.path.isdir(selected_dir) else 0

        selection_ratio = round((selected_count / extracted_count) * 100, 2) if extracted_count > 0 else 0.0

        return {
            "extracted_frames_count": extracted_count,
            "selected_frames_count": selected_count,
            "selection_ratio_percent": selection_ratio,
            "rejected_frames_count": max(0, extracted_count - selected_count)
        }

    def extract_colmap_sparse_metrics(self, job_dir: str) -> Dict[str, Any]:
        """Parses COLMAP sparse reconstruction model (images.bin, points3D.bin)."""
        # Look in colmap/sparse/0 or colmap_workspace/sparse/0
        sparse_dirs = [
            os.path.join(job_dir, "colmap", "sparse", "0"),
            os.path.join(job_dir, "colmap", "sparse"),
            os.path.join(job_dir, "colmap_workspace", "sparse", "0"),
            os.path.join(job_dir, "colmap_workspace", "sparse")
        ]
        target_dir = None
        for d in sparse_dirs:
            if os.path.isfile(os.path.join(d, "images.bin")) or os.path.isfile(os.path.join(d, "images.txt")):
                target_dir = d
                break

        if not target_dir:
            return {
                "status": "unavailable",
                "registered_images": None,
                "sparse_points_count": None,
                "mean_reprojection_error_px": None,
                "max_reprojection_error_px": None,
                "total_observations": None
            }

        images_bin = os.path.join(target_dir, "images.bin")
        points_bin = os.path.join(target_dir, "points3D.bin")

        reg_count = None
        observations = 0
        if os.path.isfile(images_bin):
            try:
                with open(images_bin, "rb") as f:
                    reg_count = struct.unpack("<Q", f.read(8))[0]
                    for _ in range(reg_count):
                        f.read(4)  # image_id
                        f.read(32) # qvec
                        f.read(24) # tvec
                        f.read(4)  # camera_id
                        # read null-terminated name
                        while f.read(1) != b"\x00":
                            pass
                        num_pts2d = struct.unpack("<Q", f.read(8))[0]
                        f.read(num_pts2d * 24)
            except Exception as e:
                logger.warning(f"Error reading images.bin: {e}")

        sparse_points = None
        mean_err = None
        max_err = None
        if os.path.isfile(points_bin):
            try:
                with open(points_bin, "rb") as f:
                    sparse_points = struct.unpack("<Q", f.read(8))[0]
                    errors = []
                    for _ in range(sparse_points):
                        f.read(8)  # point3d_id
                        f.read(24) # xyz
                        f.read(3)  # rgb
                        err = struct.unpack("<d", f.read(8))[0]
                        errors.append(err)
                        track_len = struct.unpack("<Q", f.read(8))[0]
                        observations += track_len
                        f.read(track_len * 8)
                    if errors:
                        mean_err = round(float(np.mean(errors)), 4)
                        max_err = round(float(np.max(errors)), 4)
            except Exception as e:
                logger.warning(f"Error reading points3D.bin: {e}")

        return {
            "status": "available",
            "registered_images": reg_count,
            "sparse_points_count": sparse_points,
            "mean_reprojection_error_px": mean_err,
            "max_reprojection_error_px": max_err,
            "total_observations": observations
        }

    def extract_pointcloud_and_mesh_metrics(self, job_dir: str) -> Dict[str, Any]:
        """Analyzes dense point cloud and reconstructed 3D surface mesh."""
        # Find dense cloud: colmap/dense/fused.ply or output/model.ply
        fused_candidates = [
            os.path.join(job_dir, "colmap", "dense", "fused.ply"),
            os.path.join(job_dir, "colmap", "dense", "0", "fused.ply"),
            os.path.join(job_dir, "output", "dense.ply")
        ]
        fused_path = next((p for p in fused_candidates if os.path.isfile(p)), None)

        cleaned_candidates = [
            os.path.join(job_dir, "output", "model.ply"),
            os.path.join(job_dir, "output", "cleaned_model.ply")
        ]
        cleaned_path = next((p for p in cleaned_candidates if os.path.isfile(p)), None)

        mesh_candidates = [
            os.path.join(job_dir, "output", "mesh.ply"),
            os.path.join(job_dir, "output", "mesh.glb"),
            os.path.join(job_dir, "output", "model.glb"),
            os.path.join(job_dir, "enhanced_shoe", "textured_model", "mesh.ply")
        ]
        mesh_ply = next((p for p in mesh_candidates if os.path.isfile(p) and p.endswith(".ply")), None)
        mesh_glb = next((p for p in mesh_candidates if os.path.isfile(p) and p.endswith(".glb")), None)

        res: Dict[str, Any] = {
            "fused_point_count": None,
            "fused_ply_size_bytes": os.path.getsize(fused_path) if fused_path else None,
            "cleaned_point_count": None,
            "cleaned_ply_size_bytes": os.path.getsize(cleaned_path) if cleaned_path else None,
            "points_removed_count": None,
            "points_removed_percent": None,
            "has_colors": False,
            "has_normals": False,
            "dense_bbox_extent": None,
            "mesh_vertex_count": None,
            "mesh_triangle_count": None,
            "mesh_bbox_extent": None,
            "mesh_ply_size_bytes": os.path.getsize(mesh_ply) if mesh_ply else None,
            "mesh_glb_size_bytes": os.path.getsize(mesh_glb) if mesh_glb else None
        }

        # Analyze fused point cloud
        if fused_path:
            try:
                pcd_fused = o3d.io.read_point_cloud(fused_path)
                res["fused_point_count"] = len(pcd_fused.points)
                if len(pcd_fused.points) > 0:
                    extent = pcd_fused.get_axis_aligned_bounding_box().get_extent()
                    res["dense_bbox_extent"] = [round(float(v), 4) for v in extent]
            except Exception as e:
                logger.warning(f"Error reading fused point cloud {fused_path}: {e}")

        # Analyze cleaned point cloud
        if cleaned_path:
            try:
                pcd_clean = o3d.io.read_point_cloud(cleaned_path)
                res["cleaned_point_count"] = len(pcd_clean.points)
                res["has_colors"] = pcd_clean.has_colors()
                res["has_normals"] = pcd_clean.has_normals()
                if not res["dense_bbox_extent"] and len(pcd_clean.points) > 0:
                    extent = pcd_clean.get_axis_aligned_bounding_box().get_extent()
                    res["dense_bbox_extent"] = [round(float(v), 4) for v in extent]
            except Exception as e:
                logger.warning(f"Error reading cleaned point cloud {cleaned_path}: {e}")

        # Calculate filtering reduction
        if res["fused_point_count"] and res["cleaned_point_count"]:
            rem = res["fused_point_count"] - res["cleaned_point_count"]
            res["points_removed_count"] = max(0, rem)
            res["points_removed_percent"] = round((max(0, rem) / res["fused_point_count"]) * 100, 2)

        # Analyze mesh
        if mesh_ply:
            try:
                mesh = o3d.io.read_triangle_mesh(mesh_ply)
                res["mesh_vertex_count"] = len(mesh.vertices)
                res["mesh_triangle_count"] = len(mesh.triangles)
                if len(mesh.vertices) > 0:
                    extent = mesh.get_axis_aligned_bounding_box().get_extent()
                    res["mesh_bbox_extent"] = [round(float(v), 4) for v in extent]
            except Exception as e:
                logger.warning(f"Error reading mesh {mesh_ply}: {e}")

        return res

    def extract_timing_and_logs(self, job_dir: str) -> Dict[str, Any]:
        """Gathers stage timings from manifest or log files if present."""
        # Look for experiment_report.json or report.json or comparison_report.json
        report_files = [
            os.path.join(job_dir, "experiment_report.json"),
            os.path.join(job_dir, "report.json"),
            os.path.join(job_dir, "enhanced_shoe", "comparison_report.json"),
            os.path.join(job_dir, "manifest.json")
        ]
        timings: Dict[str, Any] = {}
        for rf in report_files:
            if os.path.isfile(rf):
                try:
                    with open(rf, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    if "timing" in data or "stages" in data or "stage_timings" in data:
                        timings = data.get("stage_timings") or data.get("timing") or data.get("stages") or {}
                        break
                except Exception:
                    pass

        return {
            "stage_timings": timings if timings else None,
            "has_timing_data": bool(timings)
        }

    # --------------------------------------------------------------------------
    # 2. Physical Dimension Accuracy Evaluation
    # --------------------------------------------------------------------------
    def evaluate_physical_dimensions(
        self,
        reconstructed_extent: List[float],
        ground_truth: Dict[str, float],
        unit: str = "cm",
        scale_factor: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Evaluates physical dimension accuracy.
        ground_truth format: {"length": L_gt, "width": W_gt, "height": H_gt}
        reconstructed_extent format: [dx, dy, dz] in model coordinate space.
        """
        if not reconstructed_extent or len(reconstructed_extent) < 3:
            return {"status": "unavailable", "error": "Reconstructed bounding box extent is missing."}

        # Sort extents descending to align axes [Length (longest), Width (middle), Height (shortest)]
        rec_dims = sorted([float(v) for v in reconstructed_extent], reverse=True)
        gt_dims = sorted([float(ground_truth.get("length", 0)), float(ground_truth.get("width", 0)), float(ground_truth.get("height", 0))], reverse=True)

        if any(g <= 0 for g in gt_dims):
            return {"status": "unavailable", "error": "Ground truth dimensions must be strictly positive."}

        # Calculate scale factor if not explicitly given
        if scale_factor is None or scale_factor <= 0:
            # Scale alignment based on median ratio of dimensions
            ratios = [gt / rec for gt, rec in zip(gt_dims, rec_dims) if rec > 0]
            scale_factor = float(np.median(ratios)) if ratios else 1.0
            scale_note = "Estimated via optimal median dimensional alignment"
        else:
            scale_note = "User-specified scale calibration factor"

        scaled_dims = [round(r * scale_factor, 3) for r in rec_dims]
        abs_errors = [round(abs(s - g), 3) for s, g in zip(scaled_dims, gt_dims)]
        rel_errors = [round((abs(s - g) / g) * 100, 2) for s, g in zip(scaled_dims, gt_dims)]

        mae = round(float(np.mean(abs_errors)), 3)
        mape = round(float(np.mean(rel_errors)), 2)

        dimension_names = ["Length (Major Axis)", "Width (Intermediate Axis)", "Height (Minor Axis)"]
        details = []
        for name, gt, raw, scaled, ae, re in zip(dimension_names, gt_dims, rec_dims, scaled_dims, abs_errors, rel_errors):
            details.append({
                "dimension": name,
                "ground_truth": gt,
                "raw_model_extent": round(raw, 4),
                "scaled_reconstructed": scaled,
                "absolute_error": ae,
                "relative_error_percent": re,
                "unit": unit
            })

        return {
            "status": "evaluated",
            "unit": unit,
            "scale_factor": round(scale_factor, 6),
            "scale_alignment_method": scale_note,
            "mean_absolute_error": mae,
            "mean_absolute_percentage_error": mape,
            "dimension_details": details
        }

    # --------------------------------------------------------------------------
    # 3. Comprehensive Single-Job Evaluation
    # --------------------------------------------------------------------------
    def evaluate_job(
        self,
        job_id_or_path: str,
        ground_truth: Optional[Dict[str, float]] = None,
        unit: str = "cm",
        scale_factor: Optional[float] = None
    ) -> Dict[str, Any]:
        """Collects full metrics, runs evaluations, and generates research outputs."""
        job_dir = self._resolve_job_dir(job_id_or_path)
        job_id = os.path.basename(job_dir)
        logger.info(f"Evaluating photogrammetry job: {job_id}")

        # Gather metrics across stages
        video_m = self.extract_video_metrics(job_dir)
        frame_m = self.extract_frame_metrics(job_dir)
        sparse_m = self.extract_colmap_sparse_metrics(job_dir)
        geom_m = self.extract_pointcloud_and_mesh_metrics(job_dir)
        timing_m = self.extract_timing_and_logs(job_dir)

        # Calculate registration percentage
        reg_percent = None
        if sparse_m["registered_images"] is not None and frame_m["selected_frames_count"] > 0:
            reg_percent = round((sparse_m["registered_images"] / frame_m["selected_frames_count"]) * 100, 2)

        # Physical accuracy evaluation
        phys_eval = None
        if ground_truth and geom_m.get("dense_bbox_extent"):
            phys_eval = self.evaluate_physical_dimensions(
                reconstructed_extent=geom_m["dense_bbox_extent"],
                ground_truth=ground_truth,
                unit=unit,
                scale_factor=scale_factor
            )

        # Combine into complete metrics dict
        metrics: Dict[str, Any] = {
            "job_id": job_id,
            "job_directory": job_dir,
            "evaluation_status": "Success",
            "video": video_m,
            "frame_processing": frame_m,
            "colmap_sfm": {
                **sparse_m,
                "registration_percentage": reg_percent
            },
            "geometry_and_mesh": geom_m,
            "timing": timing_m,
            "physical_dimension_accuracy": phys_eval
        }

        # Save outputs inside job evaluation directory: jobs/{job_id}/evaluation/
        eval_dir = os.path.join(job_dir, "evaluation")
        os.makedirs(eval_dir, exist_ok=True)

        self._save_research_outputs(eval_dir, metrics)
        return metrics

    # --------------------------------------------------------------------------
    # 4. Research Output Generation (MD, JSON, CSV, Charts)
    # --------------------------------------------------------------------------
    def _save_research_outputs(self, eval_dir: str, metrics: Dict[str, Any]) -> None:
        """Saves metrics.json, metrics.csv, evaluation_report.md, and visualization PNGs."""
        # 1. metrics.json
        with open(os.path.join(eval_dir, "metrics.json"), "w", encoding="utf-8") as f:
            json.dump(metrics, f, indent=2)

        # 2. evaluation_summary.json
        summary = {
            "job_id": metrics["job_id"],
            "video_resolution": metrics["video"].get("resolution"),
            "extracted_frames": metrics["frame_processing"].get("extracted_frames_count"),
            "selected_frames": metrics["frame_processing"].get("selected_frames_count"),
            "registered_images": metrics["colmap_sfm"].get("registered_images"),
            "registration_percent": metrics["colmap_sfm"].get("registration_percentage"),
            "sparse_points": metrics["colmap_sfm"].get("sparse_points_count"),
            "reprojection_error_px": metrics["colmap_sfm"].get("mean_reprojection_error_px"),
            "fused_dense_points": metrics["geometry_and_mesh"].get("fused_point_count"),
            "cleaned_points": metrics["geometry_and_mesh"].get("cleaned_point_count"),
            "points_removed_percent": metrics["geometry_and_mesh"].get("points_removed_percent"),
            "mesh_vertices": metrics["geometry_and_mesh"].get("mesh_vertex_count"),
            "mesh_triangles": metrics["geometry_and_mesh"].get("mesh_triangle_count"),
            "physical_mape": metrics["physical_dimension_accuracy"].get("mean_absolute_percentage_error") if metrics["physical_dimension_accuracy"] else None
        }
        with open(os.path.join(eval_dir, "evaluation_summary.json"), "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)

        # 3. metrics.csv
        flat_df = pd.json_normalize(metrics)
        flat_df.to_csv(os.path.join(eval_dir, "metrics.csv"), index=False)

        # 4. evaluation_report.md
        md_content = self._generate_markdown_report(metrics)
        with open(os.path.join(eval_dir, "evaluation_report.md"), "w", encoding="utf-8") as f:
            f.write(md_content)

        # 5. Visualizations
        self._generate_point_count_chart(eval_dir, metrics)
        if metrics.get("physical_dimension_accuracy") and metrics["physical_dimension_accuracy"].get("status") == "evaluated":
            self._generate_dimension_accuracy_chart(eval_dir, metrics["physical_dimension_accuracy"])
        if metrics.get("timing") and metrics["timing"].get("stage_timings"):
            self._generate_timing_chart(eval_dir, metrics["timing"]["stage_timings"])

    def _generate_markdown_report(self, m: Dict[str, Any]) -> str:
        v = m["video"]
        f_proc = m["frame_processing"]
        sfm = m["colmap_sfm"]
        geom = m["geometry_and_mesh"]
        phys = m["physical_dimension_accuracy"]

        dur_str = f"{v.get('duration_seconds')} s" if v.get("duration_seconds") else "N/A"
        fsize_str = f"{v.get('file_size_mb')} MB" if v.get("file_size_mb") else "N/A"
        sparse_pts_str = f"{sfm.get('sparse_points_count'):,}" if sfm.get("sparse_points_count") else "N/A"
        reproj_str = f"{sfm.get('mean_reprojection_error_px')} px" if sfm.get("mean_reprojection_error_px") is not None else "N/A"
        obs_str = f"{sfm.get('total_observations'):,}" if sfm.get("total_observations") else "N/A"
        fused_pts_str = f"{geom.get('fused_point_count'):,}" if geom.get("fused_point_count") else "N/A"
        clean_pts_str = f"{geom.get('cleaned_point_count'):,}" if geom.get("cleaned_point_count") else "N/A"
        rem_pts_str = f"{geom.get('points_removed_count'):,}" if geom.get("points_removed_count") is not None else "N/A"
        vtx_str = f"{geom.get('mesh_vertex_count'):,}" if geom.get("mesh_vertex_count") else "N/A"
        tri_str = f"{geom.get('mesh_triangle_count'):,}" if geom.get("mesh_triangle_count") else "N/A"
        ply_mb_str = f"{round(geom.get('cleaned_ply_size_bytes', 0)/(1024*1024), 2)} MB" if geom.get("cleaned_ply_size_bytes") else "N/A"
        glb_mb_str = f"{round(geom.get('mesh_glb_size_bytes', 0)/(1024*1024), 2)} MB" if geom.get("mesh_glb_size_bytes") else "N/A"

        lines = [
            "# 3D Photogrammetry Reconstruction Research Evaluation",
            "",
            f"**Job ID:** `{m['job_id']}`  ",
            f"**Evaluation Status:** `{m['evaluation_status']}`  ",
            "",
            "---",
            "",
            "## 1. Input Acquisition & Video Properties",
            "",
            "| Metric | Value |",
            "| :--- | :--- |",
            f"| Input Video Filename | `{v.get('filename') or 'N/A'}` |",
            f"| Resolution | {v.get('resolution') or 'N/A'} |",
            f"| Frame Rate (FPS) | {v.get('fps') or 'N/A'} |",
            f"| Total Video Frames | {v.get('frame_count') or 'N/A'} |",
            f"| Duration | {dur_str} |",
            f"| File Size | {fsize_str} |",
            "",
            "## 2. Keyframe Selection & Structure-from-Motion (SfM)",
            "",
            "| Pipeline Stage | Measurement |",
            "| :--- | :--- |",
            f"| Extracted Candidate Frames | {f_proc.get('extracted_frames_count', 'N/A')} |",
            f"| Quality Selected Keyframes | {f_proc.get('selected_frames_count', 'N/A')} ({f_proc.get('selection_ratio_percent', 'N/A')}%) |",
            f"| Registered Images in SfM | {sfm.get('registered_images') or 'N/A'} / {f_proc.get('selected_frames_count', 'N/A')} ({sfm.get('registration_percentage', 'N/A')}%) |",
            f"| Sparse 3D Point Count | {sparse_pts_str} |",
            f"| Mean Reprojection Error | {reproj_str} |",
            f"| Total Observations | {obs_str} |",
            "",
            "## 3. Multi-View Stereo (MVS) & Surface Reconstruction",
            "",
            "| Geometric Artifact | Value |",
            "| :--- | :--- |",
            f"| Raw Fused Dense Points | {fused_pts_str} |",
            f"| Cleaned / Filtered Points | {clean_pts_str} |",
            f"| Statistical Outliers Removed | {rem_pts_str} ({geom.get('points_removed_percent', 'N/A')}%) |",
            f"| Point Cloud RGB Colors | {'Present' if geom.get('has_colors') else 'Absent'} |",
            f"| Surface Normals | {'Present' if geom.get('has_normals') else 'Absent'} |",
            f"| Dense Bounding Box Extent (X, Y, Z) | {str(geom.get('dense_bbox_extent') or 'N/A')} |",
            f"| Reconstructed Mesh Vertices | {vtx_str} |",
            f"| Reconstructed Mesh Triangles | {tri_str} |",
            f"| Exported Model PLY Size | {ply_mb_str} |",
            f"| Exported Model GLB Size | {glb_mb_str} |",
            ""
        ]

        if phys and phys.get("status") == "evaluated":
            lines.extend([
                f"## 4. Physical Dimension Accuracy Evaluation",
                f"",
                f"- **Scale Calibration:** `{phys.get('scale_alignment_method')}` (Scale Factor: `{phys.get('scale_factor')}`)",
                f"- **Mean Absolute Error (MAE):** **{phys.get('mean_absolute_error')} {phys.get('unit')}**",
                f"- **Mean Absolute Percentage Error (MAPE):** **{phys.get('mean_absolute_percentage_error')}%**",
                f"",
                f"| Axis / Dimension | Ground Truth ({phys.get('unit')}) | Scaled Reconstructed ({phys.get('unit')}) | Absolute Error | Relative Error (%) |",
                f"| :--- | :--- | :--- | :--- | :--- |"
            ])
            for d in phys.get("dimension_details", []):
                lines.append(f"| {d['dimension']} | {d['ground_truth']} | {d['scaled_reconstructed']} | {d['absolute_error']} {d['unit']} | {d['relative_error_percent']}% |")
            lines.append("")

        lines.extend([
            f"---",
            f"*Generated automatically by the Secure Audit Photogrammetry Research Evaluation Module.*"
        ])
        return "\n".join(lines)

    def _generate_point_count_chart(self, eval_dir: str, metrics: Dict[str, Any]) -> None:
        """Creates bar chart comparing pipeline point counts."""
        f_proc = metrics["frame_processing"]
        sfm = metrics["colmap_sfm"]
        geom = metrics["geometry_and_mesh"]

        stages = []
        counts = []
        colors = []

        if f_proc.get("extracted_frames_count"):
            stages.append("Extracted Frames")
            counts.append(f_proc["extracted_frames_count"])
            colors.append("#4a90e2")

        if f_proc.get("selected_frames_count"):
            stages.append("Selected Keyframes")
            counts.append(f_proc["selected_frames_count"])
            colors.append("#50e3c2")

        if sfm.get("sparse_points_count"):
            stages.append("Sparse 3D Points")
            counts.append(sfm["sparse_points_count"])
            colors.append("#f5a623")

        if geom.get("fused_point_count"):
            stages.append("Fused Dense Points")
            counts.append(geom["fused_point_count"])
            colors.append("#9013fe")

        if geom.get("cleaned_point_count"):
            stages.append("Cleaned Points")
            counts.append(geom["cleaned_point_count"])
            colors.append("#7ed321")

        if geom.get("mesh_vertex_count"):
            stages.append("Mesh Vertices")
            counts.append(geom["mesh_vertex_count"])
            colors.append("#bd10e0")

        if not stages:
            return

        fig, ax = plt.subplots(figsize=(10, 5), dpi=150)
        bars = ax.bar(stages, counts, color=colors, edgecolor="#333333", width=0.55)
        ax.set_yscale("log")
        ax.set_ylabel("Entity Count (Log Scale)", fontsize=11, fontweight="bold")
        ax.set_title(f"3D Photogrammetry Pipeline Entity Progression\nJob: {metrics['job_id'][:16]}...", fontsize=12, fontweight="bold", pad=12)
        ax.grid(axis="y", linestyle="--", alpha=0.6)

        for bar in bars:
            height = bar.get_height()
            ax.annotate(f"{int(height):,}",
                        xy=(bar.get_x() + bar.get_width() / 2, height),
                        xytext=(0, 4),
                        textcoords="offset points",
                        ha="center", va="bottom", fontsize=9, fontweight="bold")

        plt.xticks(rotation=15, ha="right", fontsize=9)
        plt.tight_layout()
        plt.savefig(os.path.join(eval_dir, "point_count_comparison.png"))
        plt.close(fig)

    def _generate_dimension_accuracy_chart(self, eval_dir: str, phys: Dict[str, Any]) -> None:
        """Plots ground truth vs reconstructed physical dimensions with absolute errors."""
        details = phys.get("dimension_details", [])
        if not details:
            return

        dims = [d["dimension"].split(" (")[0] for d in details]
        gt_vals = [d["ground_truth"] for d in details]
        rec_vals = [d["scaled_reconstructed"] for d in details]

        x = np.arange(len(dims))
        width = 0.35

        fig, ax = plt.subplots(figsize=(8, 4.5), dpi=150)
        rects1 = ax.bar(x - width/2, gt_vals, width, label="Ground Truth", color="#4a90e2", edgecolor="#333333")
        rects2 = ax.bar(x + width/2, rec_vals, width, label="Reconstructed", color="#50e3c2", edgecolor="#333333")

        ax.set_ylabel(f"Dimension ({phys.get('unit', 'cm')})", fontsize=11, fontweight="bold")
        ax.set_title(f"Physical Dimension Accuracy Comparison\nMAPE: {phys.get('mean_absolute_percentage_error')}% (MAE: {phys.get('mean_absolute_error')} {phys.get('unit')})", fontsize=12, fontweight="bold", pad=12)
        ax.set_xticks(x)
        ax.set_xticklabels(dims, fontsize=10, fontweight="bold")
        ax.legend(frameon=True)
        ax.grid(axis="y", linestyle="--", alpha=0.5)

        for rect in rects1 + rects2:
            h = rect.get_height()
            ax.annotate(f"{h:.1f}",
                        xy=(rect.get_x() + rect.get_width() / 2, h),
                        xytext=(0, 3),
                        textcoords="offset points",
                        ha="center", va="bottom", fontsize=9)

        plt.tight_layout()
        plt.savefig(os.path.join(eval_dir, "dimension_accuracy.png"))
        plt.close(fig)

    def _generate_timing_chart(self, eval_dir: str, timings: Dict[str, Any]) -> None:
        """Generates stage processing breakdown pie/bar chart."""
        stages = list(timings.keys())
        values = [float(v) for v in timings.values() if isinstance(v, (int, float))]
        if not values or len(values) != len(stages):
            return

        fig, ax = plt.subplots(figsize=(8, 4.5), dpi=150)
        ax.barh(stages, values, color="#4a90e2", edgecolor="#333333")
        ax.set_xlabel("Processing Time (Seconds)", fontsize=11, fontweight="bold")
        ax.set_title("Reconstruction Stage Execution Times", fontsize=12, fontweight="bold", pad=12)
        ax.grid(axis="x", linestyle="--", alpha=0.5)

        for i, v in enumerate(values):
            ax.text(v + (max(values)*0.01), i, f"{v:.1f}s", va="center", fontsize=9, fontweight="bold")

        plt.tight_layout()
        plt.savefig(os.path.join(eval_dir, "processing_time.png"))
        plt.close(fig)

    # --------------------------------------------------------------------------
    # 5. Multi-Job Comparison Engine
    # --------------------------------------------------------------------------
    def compare_multiple_jobs(self, job_identifiers: List[str], output_dir: str) -> Dict[str, Any]:
        """Compares multiple completed jobs (scene-level vs object-level)."""
        os.makedirs(output_dir, exist_ok=True)
        all_metrics = []

        for j_id in job_identifiers:
            try:
                m = self.evaluate_job(j_id)
                all_metrics.append(m)
            except Exception as e:
                logger.warning(f"Could not evaluate job {j_id}: {e}")

        if not all_metrics:
            raise RuntimeError("No valid jobs found for comparison.")

        # Build comparison table
        rows = []
        for m in all_metrics:
            v = m["video"]
            f_proc = m["frame_processing"]
            sfm = m["colmap_sfm"]
            geom = m["geometry_and_mesh"]
            rows.append({
                "Job ID": m["job_id"][:12] + "...",
                "Full Job ID": m["job_id"],
                "Video Resolution": v.get("resolution") or "N/A",
                "Video FPS": v.get("fps") or "N/A",
                "Extracted Frames": f_proc.get("extracted_frames_count") or 0,
                "Selected Frames": f_proc.get("selected_frames_count") or 0,
                "Registered Images": sfm.get("registered_images") or 0,
                "Registration %": sfm.get("registration_percentage") or 0.0,
                "Sparse Points": sfm.get("sparse_points_count") or 0,
                "Reprojection Error (px)": sfm.get("mean_reprojection_error_px") or 0.0,
                "Dense Points": geom.get("cleaned_point_count") or geom.get("fused_point_count") or 0,
                "Mesh Vertices": geom.get("mesh_vertex_count") or 0,
                "Mesh Triangles": geom.get("mesh_triangle_count") or 0,
                "GLB Size (MB)": round((geom.get("mesh_glb_size_bytes") or 0) / (1024 * 1024), 2)
            })

        df = pd.DataFrame(rows)
        csv_path = os.path.join(output_dir, "multi_job_comparison.csv")
        df.to_csv(csv_path, index=False)

        def _df_to_markdown(dataframe: pd.DataFrame) -> str:
            headers = list(dataframe.columns)
            res_lines = ["| " + " | ".join(str(h) for h in headers) + " |"]
            res_lines.append("| " + " | ".join(["---"] * len(headers)) + " |")
            for _, r in dataframe.iterrows():
                res_lines.append("| " + " | ".join(str(v) for v in r.values) + " |")
            return "\n".join(res_lines)

        # Markdown comparison report
        md_lines = [
            "# Multi-Job Photogrammetry Experimental Comparison",
            "",
            f"Total evaluated jobs: **{len(all_metrics)}**  ",
            "",
            "## 1. Experimental Comparison Table",
            "",
            _df_to_markdown(df.drop(columns=["Full Job ID"])),
            "",
            "## 2. Observations & Analysis",
            "",
            "- **Registration Completeness:** Tracks camera pose estimation and SfM alignment ratio across diverse capture conditions.",
            "- **Dense Point Density:** Compares MVS surface detail between broad outdoor scenes and localized evidence objects.",
            "- **Mesh Complexity:** Evaluates polygon counts and output GLB web optimization for browser rendering.",
            "",
            "---",
            "*Generated by Secure Audit Multi-Job Photogrammetry Benchmark Engine.*"
        ]

        md_path = os.path.join(output_dir, "multi_job_comparison.md")
        with open(md_path, "w", encoding="utf-8") as f:
            f.write("\n".join(md_lines))

        # Comparative Chart
        self._generate_multi_job_chart(output_dir, df)

        summary_path = os.path.join(output_dir, "comparison_summary.json")
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(rows, f, indent=2)

        return {
            "comparison_csv": csv_path,
            "comparison_md": md_path,
            "comparison_summary": summary_path,
            "job_count": len(all_metrics)
        }

    def _generate_multi_job_chart(self, output_dir: str, df: pd.DataFrame) -> None:
        """Generates side-by-side comparison chart for multiple jobs."""
        if len(df) < 1:
            return

        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5), dpi=150)
        jobs = df["Job ID"].tolist()

        # Chart 1: Points & Mesh Vertices
        x = np.arange(len(jobs))
        width = 0.35
        ax1.bar(x - width/2, df["Sparse Points"], width, label="Sparse Points", color="#f5a623", edgecolor="#333333")
        ax1.bar(x + width/2, df["Dense Points"], width, label="Dense Points", color="#7ed321", edgecolor="#333333")
        ax1.set_yscale("log")
        ax1.set_ylabel("Point Count (Log Scale)", fontsize=10, fontweight="bold")
        ax1.set_title("Point Cloud Density Comparison", fontsize=11, fontweight="bold")
        ax1.set_xticks(x)
        ax1.set_xticklabels(jobs, rotation=15, ha="right", fontsize=8)
        ax1.legend()
        ax1.grid(axis="y", linestyle="--", alpha=0.5)

        # Chart 2: Registration % and Reprojection Error
        ax2.bar(x - width/2, df["Registration %"], width, label="Registration %", color="#4a90e2", edgecolor="#333333")
        ax2_twin = ax2.twinx()
        ax2_twin.plot(x, df["Reprojection Error (px)"], color="#d0021b", marker="o", linewidth=2, label="Reprojection Error (px)")
        ax2.set_ylabel("Registration Ratio (%)", fontsize=10, fontweight="bold")
        ax2_twin.set_ylabel("Reprojection Error (px)", fontsize=10, fontweight="bold", color="#d0021b")
        ax2.set_title("SfM Registration Quality & Error", fontsize=11, fontweight="bold")
        ax2.set_xticks(x)
        ax2.set_xticklabels(jobs, rotation=15, ha="right", fontsize=8)
        ax2.set_ylim(0, 105)
        ax2.grid(axis="y", linestyle="--", alpha=0.5)

        plt.tight_layout()
        plt.savefig(os.path.join(output_dir, "multi_job_comparison.png"))
        plt.close(fig)
