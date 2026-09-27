import os
import glob
import subprocess
import logging
import math
import re

logger = logging.getLogger(__name__)


class ColmapRunner:
    """
    Automates the COLMAP GPU reconstruction pipeline:
      1. Feature extraction
      2. Sequential matching
      3. Sparse mapper (SfM)
      4. Image undistortion
      5. Patch match stereo (dense depth estimation)
      6. Stereo fusion (dense point cloud)
    """

    COLMAP_EXE = r"C:\COLMAP_GPU\bin\colmap.exe"

    def reconstruct(self, image_dir: str, output_dir: str, minimum_registration_ratio: float = 0.8,
                    dense_mask_path: str | None = None) -> dict:

        image_dir = os.path.abspath(image_dir)
        output_dir = os.path.abspath(output_dir)

        db_path = os.path.join(output_dir, "database.db")
        sparse_dir = os.path.join(output_dir, "sparse")
        dense_dir = os.path.join(output_dir, "dense")

        fused_ply_path = os.path.join(
            dense_dir,
            "fused.ply"
        )

        selected_sparse_model_dir = None
        sparse_stats = None

        os.makedirs(output_dir, exist_ok=True)
        os.makedirs(sparse_dir, exist_ok=True)
        candidate_image_count = len(glob.glob(os.path.join(image_dir, "*.jpg")))
        if candidate_image_count < 2:
            raise RuntimeError("At least two selected images are required for SfM.")

        logger.info(
            f"Starting COLMAP reconstruction in: {output_dir}"
        )

        # Make sure the exact GPU-enabled COLMAP exists
        if not os.path.exists(self.COLMAP_EXE):
            raise RuntimeError(
                f"COLMAP executable not found at: {self.COLMAP_EXE}"
            )

        steps = [

            # -------------------------------------------------
            # 1. FEATURE EXTRACTION - GPU
            # -------------------------------------------------
            {
                "name": "feature_extractor",
                "args": [
                    self.COLMAP_EXE,
                    "feature_extractor",
                    "--database_path",
                    db_path,
                    "--image_path",
                    image_dir,
                    "--ImageReader.single_camera",
                    "1",
                    "--FeatureExtraction.use_gpu",
                    "1",
                    "--FeatureExtraction.gpu_index",
                    "0",
                    "--FeatureExtraction.num_threads",
                    "4",
                    "--FeatureExtraction.max_image_size",
                    "2400",
                    "--SiftExtraction.max_num_features",
                    "20000",
                    "--SiftExtraction.peak_threshold",
                    "0.004",
                    "--SiftExtraction.domain_size_pooling",
                    "1",
                ],
            },

            # -------------------------------------------------
            # 2. FEATURE MATCHING - GPU
            # -------------------------------------------------
            {
                "name": "sequential_matcher",
                "args": [
                    self.COLMAP_EXE,
                    "sequential_matcher",
                    "--database_path",
                    db_path,
                    "--FeatureMatching.use_gpu",
                    "1",
                    "--FeatureMatching.gpu_index",
                    "0",
                    "--FeatureMatching.num_threads",
                    "1",
                    "--FeatureMatching.guided_matching",
                    "1",
                    "--SequentialMatching.overlap",
                    "15",
                    "--SequentialMatching.quadratic_overlap",
                    "1",
                    "--SiftMatching.max_ratio",
                    "0.8",
                    "--TwoViewGeometry.max_error",
                    "3",
                ],
            },

            # -------------------------------------------------
            # 3. SPARSE RECONSTRUCTION / SfM
            # -------------------------------------------------
            {
                "name": "mapper",
                "args": [
                    self.COLMAP_EXE,
                    "mapper",
                    "--database_path",
                    db_path,
                    "--image_path",
                    image_dir,
                    "--output_path",
                    sparse_dir,
                    "--Mapper.ba_global_max_num_iterations",
                    "100",
                    "--Mapper.ba_global_max_refinements",
                    "10",
                    "--Mapper.filter_max_reproj_error",
                    "3",
                ],
            },

            # -------------------------------------------------
            # 4. IMAGE UNDISTORTION
            # -------------------------------------------------
            {
                "name": "image_undistorter",
                "args": [
                    self.COLMAP_EXE,
                    "image_undistorter",
                    "--image_path",
                    image_dir,
                    "--input_path",
                    sparse_dir,
                    "--output_path",
                    dense_dir,
                    "--output_type",
                    "COLMAP",
                ],
            },

            # -------------------------------------------------
            # 5. PATCH MATCH STEREO - GPU
            # -------------------------------------------------
            {
                "name": "patch_match_stereo",
                "args": [
                    self.COLMAP_EXE,
                    "patch_match_stereo",
                    "--workspace_path",
                    dense_dir,
                    "--workspace_format",
                    "COLMAP",
                    "--PatchMatchStereo.gpu_index",
                    "0",
                    "--PatchMatchStereo.geom_consistency",
                    "1",
                    "--PatchMatchStereo.num_samples",
                    "20",
                    "--PatchMatchStereo.num_iterations",
                    "7",
                    "--PatchMatchStereo.filter_min_num_consistent",
                    "2",
                    "--PatchMatchStereo.write_consistency_graph",
                    "1",
                ],
            },

            # -------------------------------------------------
            # 6. STEREO FUSION
            # -------------------------------------------------
            {
                "name": "stereo_fusion",
                "args": [
                    self.COLMAP_EXE,
                    "stereo_fusion",
                    "--workspace_path",
                    dense_dir,
                    "--workspace_format",
                    "COLMAP",
                    "--output_path",
                    fused_ply_path,
                    "--input_type",
                    "geometric",
                    "--StereoFusion.min_num_pixels",
                    "3",
                    "--StereoFusion.check_num_images",
                    "60",
                    "--StereoFusion.max_reproj_error",
                    "1.5",
                ],
            },
        ]

        # Masks are deliberately applied only at fusion.  SfM and PatchMatch
        # continue to see full images, retaining the registration context that
        # tracked-object experiments require.
        if dense_mask_path:
            dense_mask_path = os.path.abspath(dense_mask_path)
            if not os.path.isdir(dense_mask_path):
                raise RuntimeError(f"Dense fusion mask directory does not exist: {dense_mask_path}")
            fusion_step = next(step for step in steps if step["name"] == "stereo_fusion")
            fusion_step["args"].extend(["--StereoFusion.mask_path", dense_mask_path])

        expected_outputs = {
            "feature_extractor": [db_path],
            # The mapper may write more than one numbered sparse model.  Its
            # outputs are validated and selected immediately after it runs.
            "mapper": [],
            "image_undistorter": [os.path.join(dense_dir, "sparse", "images.bin")],
            "patch_match_stereo": [os.path.join(dense_dir, "stereo", "depth_maps")],
            "stereo_fusion": [fused_ply_path],
        }

        # Execute pipeline
        for step in steps:

            name = step["name"]
            args = step["args"]

            logger.info(f"Running COLMAP step: {name}")
            logger.info(f"Command: {' '.join(args)}")

            try:

                result = subprocess.run(
                    args,
                    capture_output=True,
                    text=True,
                    check=True
                )

                if result.stdout:
                    logger.debug(
                        f"{name} stdout:\n{result.stdout[-3000:]}"
                    )

                if result.stderr:
                    logger.debug(
                        f"{name} stderr:\n{result.stderr[-3000:]}"
                    )

                logger.info(
                    f"COLMAP step completed successfully: {name}"
                )

                for artifact in expected_outputs.get(name, []):
                    if not os.path.exists(artifact):
                        raise RuntimeError(f"COLMAP step '{name}' completed but required output is missing: {artifact}")
                    if os.path.isfile(artifact) and os.path.getsize(artifact) == 0:
                        raise RuntimeError(f"COLMAP step '{name}' produced an empty required output: {artifact}")
                if name == "patch_match_stereo" and not glob.glob(os.path.join(dense_dir, "stereo", "depth_maps", "*.bin")):
                    raise RuntimeError("COLMAP patch_match_stereo completed without producing any depth maps.")
                if name == "mapper":
                    sparse_models = self._discover_sparse_models(sparse_dir)
                    if not sparse_models:
                        raise RuntimeError("COLMAP mapper completed without producing a valid sparse model.")

                    logger.info("COLMAP mapper produced %s sparse model(s).", len(sparse_models))
                    for model in sparse_models:
                        stats = model["stats"]
                        model_registration_percent = 100 * stats["registered_image_count"] / candidate_image_count
                        logger.info(
                            "Sparse model %s: registered=%s/%s (%.2f%%), sparse_points=%s, "
                            "observations=%s, mean_reprojection_error=%s",
                            model["name"],
                            stats["registered_image_count"],
                            candidate_image_count,
                            model_registration_percent,
                            stats["sparse_point_count"],
                            stats.get("observation_count"),
                            stats.get("mean_reprojection_error"),
                        )

                    selected_model = max(
                        sparse_models,
                        key=lambda model: (
                            model["stats"]["registered_image_count"],
                            model["stats"]["sparse_point_count"],
                            -float(model["stats"].get("mean_reprojection_error") or 999.0),
                        ),
                    )
                    selected_sparse_model_dir = selected_model["path"]
                    sparse_stats = selected_model["stats"]
                    logger.info(
                        "Selected sparse model %s at %s: highest registered-image count, "
                        "then sparse-point count.",
                        selected_model["name"],
                        selected_sparse_model_dir,
                    )

                    undistorter_step = next(step for step in steps if step["name"] == "image_undistorter")
                    undistorter_input_index = undistorter_step["args"].index("--input_path") + 1
                    undistorter_step["args"][undistorter_input_index] = selected_sparse_model_dir

                    registered_count = sparse_stats["registered_image_count"]
                    required_count = math.ceil(candidate_image_count * minimum_registration_ratio)
                    registration_percent = 100 * registered_count / candidate_image_count
                    logger.info(
                        "SfM diagnostics: candidates=%s, registered=%s, registration=%.2f%%, sparse_points=%s",
                        candidate_image_count,
                        registered_count,
                        registration_percent,
                        sparse_stats["sparse_point_count"],
                    )
                    if registered_count < required_count:
                        raise RuntimeError(
                            "Insufficient SfM coverage: "
                            f"registered {registered_count}/{candidate_image_count} images "
                            f"({registration_percent:.2f}%), but quality mode requires at least "
                            f"{required_count}/{candidate_image_count} images ({minimum_registration_ratio:.0%}). "
                            "Dense MVS was not started."
                        )

            except subprocess.CalledProcessError as e:

                logger.error(
                    f"COLMAP step failed: {name}"
                )

                logger.error(
                    f"Exit code: {e.returncode}"
                )

                if e.stderr:
                    logger.error(e.stderr)

                raise RuntimeError(
                    f"COLMAP reconstruction failed during "
                    f"'{name}'.\n{e.stderr}"
                ) from e

        # -------------------------------------------------
        # FINAL VALIDATION
        # -------------------------------------------------

        if not os.path.exists(fused_ply_path):
            raise RuntimeError(
                "COLMAP completed but fused.ply was not created."
            )

        logger.info(
            "COLMAP reconstruction completed successfully."
        )

        return {
            "sparse_path": selected_sparse_model_dir.replace(os.sep, "/"),
            "dense_ply_path": fused_ply_path.replace(os.sep, "/"),
            "sparse_stats": sparse_stats,
        }

    def _discover_sparse_models(self, sparse_dir: str) -> list[dict]:
        sparse_models = []
        for entry in sorted(os.scandir(sparse_dir), key=lambda item: int(item.name) if item.name.isdigit() else -1):
            if not entry.is_dir() or not entry.name.isdigit():
                continue

            required_files = ("cameras.bin", "images.bin", "points3D.bin")
            missing_files = [filename for filename in required_files if not os.path.isfile(os.path.join(entry.path, filename))]
            if missing_files:
                logger.warning("Ignoring incomplete sparse model %s; missing: %s", entry.path, ", ".join(missing_files))
                continue

            sparse_models.append({
                "name": entry.name,
                "path": entry.path,
                "stats": self._read_sparse_statistics(entry.path),
            })
        return sparse_models

    def _read_sparse_statistics(self, sparse_model_dir: str) -> dict:
        result = subprocess.run(
            [self.COLMAP_EXE, "model_analyzer", "--path", sparse_model_dir],
            capture_output=True,
            text=True,
            check=True,
        )
        # COLMAP 4.1 on Windows writes model_analyzer metrics to stderr even
        # when it exits successfully, so inspect both streams.
        report = "\n".join((result.stdout, result.stderr))

        def integer_metric(label: str) -> int:
            match = re.search(rf"{re.escape(label)}:\s*(\d+)", report)
            if not match:
                raise RuntimeError(f"COLMAP model_analyzer did not report '{label}'.")
            return int(match.group(1))

        def optional_float_metric(label: str) -> float | None:
            match = re.search(rf"{re.escape(label)}:\s*([0-9]+(?:\.[0-9]+)?)", report)
            return float(match.group(1)) if match else None

        return {
            "image_count": integer_metric("Images"),
            "registered_image_count": integer_metric("Registered images"),
            "sparse_point_count": integer_metric("Points"),
            "observation_count": integer_metric("Observations"),
            "mean_reprojection_error": optional_float_metric("Mean reprojection error"),
        }
