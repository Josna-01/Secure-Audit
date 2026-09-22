import os
import subprocess
import logging

logger = logging.getLogger(__name__)


class ColmapRunner:
    """
    Automates the COLMAP GPU reconstruction pipeline:
      1. Feature extraction
      2. Exhaustive matching
      3. Sparse mapper (SfM)
      4. Image undistortion
      5. Patch match stereo (dense depth estimation)
      6. Stereo fusion (dense point cloud)
    """

    COLMAP_EXE = r"C:\COLMAP_GPU\bin\colmap.exe"

    def reconstruct(self, image_dir: str, output_dir: str) -> dict:

        image_dir = os.path.abspath(image_dir)
        output_dir = os.path.abspath(output_dir)

        db_path = os.path.join(output_dir, "database.db")
        sparse_dir = os.path.join(output_dir, "sparse")
        dense_dir = os.path.join(output_dir, "dense")

        fused_ply_path = os.path.join(
            dense_dir,
            "fused.ply"
        )

        sparse_model_dir = os.path.join(
            sparse_dir,
            "0"
        )

        os.makedirs(output_dir, exist_ok=True)
        os.makedirs(sparse_dir, exist_ok=True)

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
                ],
            },

            # -------------------------------------------------
            # 2. FEATURE MATCHING - GPU
            # -------------------------------------------------
            {
                "name": "exhaustive_matcher",
                "args": [
                    self.COLMAP_EXE,
                    "exhaustive_matcher",
                    "--database_path",
                    db_path,
                    "--FeatureMatching.use_gpu",
                    "1",
                    "--FeatureMatching.gpu_index",
                    "0",
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
                    sparse_model_dir,
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
                ],
            },
        ]

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
            "sparse_path": sparse_model_dir.replace(os.sep, "/"),
            "dense_ply_path": fused_ply_path.replace(os.sep, "/"),
        }  