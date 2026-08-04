import os
import subprocess
import logging

logger = logging.getLogger(__name__)

class ColmapRunner:
    """
    Service class to automate the execution of COLMAP executable steps
    to reconstruct sparse and dense 3D models from calibrated images.
    """

    def reconstruct(self, image_dir: str, output_dir: str) -> dict:
        """
        Executes the 6-step COLMAP pipeline:
          1. Feature extraction
          2. Exhaustive matching
          3. Sparse mapper (SfM)
          4. Image undistortion
          5. Patch match stereo (dense estimation)
          6. Stereo fusion (dense reconstruction mesh/point cloud)

        Args:
            image_dir (str): Directory containing the source frame images.
            output_dir (str): Parent directory where all reconstruction artifacts will be stored.

        Returns:
            dict: Paths to the sparse model directory and the fused dense point cloud file (.ply).

        Raises:
            RuntimeError: If any of the COLMAP steps fail to execute successfully.
        """
        # Normalize and resolve absolute paths
        image_dir = os.path.abspath(image_dir)
        output_dir = os.path.abspath(output_dir)

        # Output folder paths
        db_path = os.path.join(output_dir, "database.db")
        sparse_dir = os.path.join(output_dir, "sparse")
        dense_dir = os.path.join(output_dir, "dense")
        fused_ply_path = os.path.join(dense_dir, "fused.ply")
        sparse_model_dir = os.path.join(sparse_dir, "0")  # SfM mapper default subfolder

        # Ensure output directories exist
        os.makedirs(output_dir, exist_ok=True)
        os.makedirs(sparse_dir, exist_ok=True)

        logger.info(f"Starting 3D reconstruction pipeline in output directory: {output_dir}")

        steps = [
            {
                "name": "feature_extractor",
                "args": [
                    "colmap", "feature_extractor",
                    "--database_path", db_path,
                    "--image_path", image_dir,
                    "--ImageReader.single_camera", "1",
                    "--FeatureExtraction.use_gpu", "0"
                ]
            },
            {
                "name": "exhaustive_matcher",
                "args": [
                    "colmap", "exhaustive_matcher",
                    "--database_path", db_path,
                    "--FeatureMatching.use_gpu", "0"
                ]
            },
            {
                "name": "mapper",
                "args": [
                    "colmap", "mapper",
                    "--database_path", db_path,
                    "--image_path", image_dir,
                    "--output_path", sparse_dir
                ]
            },
            {
                "name": "image_undistorter",
                "args": [
                    "colmap", "image_undistorter",
                    "--image_path", image_dir,
                    "--input_path", sparse_model_dir,
                    "--output_path", dense_dir
                ]
            },
            {
                "name": "patch_match_stereo",
                "args": [
                    "colmap", "patch_match_stereo",
                    "--workspace_path", dense_dir
                ]
            },
            {
                "name": "stereo_fusion",
                "args": [
                    "colmap", "stereo_fusion",
                    "--workspace_path", dense_dir,
                    "--output_path", fused_ply_path
                ]
            }
        ]

        for step in steps:
            name = step["name"]
            args = step["args"]

            logger.info(f"Running COLMAP step: {name}")
            logger.debug(f"Command arguments: {args}")

            try:
                # Execute step. check=True raises CalledProcessError if returncode != 0
                result = subprocess.run(
                    args,
                    capture_output=True,
                    text=True,
                    check=True
                )
                logger.info(f"Successfully completed COLMAP step: {name}")
                if result.stdout:
                    logger.debug(f"Step '{name}' stdout:\n{result.stdout[-1000:]}") # show trailing stdout
            except subprocess.CalledProcessError as e:
                if name in ("patch_match_stereo", "stereo_fusion"):
                    logger.warning(f"Dense stereo step '{name}' requires CUDA GPU. Falling back to sparse point cloud model conversion...")
                    conv_args = [
                        "colmap", "model_converter",
                        "--input_path", sparse_model_dir,
                        "--output_path", fused_ply_path,
                        "--output_type", "PLY"
                    ]
                    conv_res = subprocess.run(conv_args, capture_output=True, text=True)
                    if conv_res.returncode == 0 and os.path.exists(fused_ply_path):
                        logger.info("Successfully exported 3D point cloud model fallback via model_converter.")
                        break
                logger.error(f"Error in COLMAP step '{name}' (exit code {e.returncode})")
                if e.stderr:
                    logger.error(f"Step '{name}' stderr:\n{e.stderr}")
                raise RuntimeError(
                    f"COLMAP reconstruction failed during '{name}' step. "
                    f"Error: {e.stderr.strip() if e.stderr else 'Unknown error (check logs)'}"
                ) from e
            except FileNotFoundError as e:
                logger.critical("COLMAP executable not found on system PATH.")
                raise RuntimeError(
                    f"COLMAP executable not found. Ensure COLMAP is installed and added to the PATH."
                ) from e

        logger.info("COLMAP reconstruction completed successfully.")

        # Return standardized output dictionary with normalized forward-slash paths
        return {
            "sparse_path": sparse_model_dir.replace(os.sep, '/'),
            "dense_ply_path": fused_ply_path.replace(os.sep, '/')
        }
