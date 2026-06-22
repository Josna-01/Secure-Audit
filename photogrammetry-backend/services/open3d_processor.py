import os
import logging
import numpy as np
import open3d as o3d

logger = logging.getLogger(__name__)

class Open3DProcessor:
    """
    Service class responsible for point cloud post-processing,
    3D mesh generation, and spatial measurement computation.
    """

    def process(self, ply_path: str, output_dir: str) -> dict:
        """
        Cleans the point cloud, reconstructs a 3D triangle mesh,
        saves the processed files, and measures the dimensions of the model.

        Args:
            ply_path (str): Path to the source fused point cloud (.ply) file.
            output_dir (str): Directory where the output assets will be saved.

        Returns:
            dict: URLs/paths to the output ply/glb files and measured bounding dimensions.

        Raises:
            RuntimeError: If the input file is not found or if any step in Open3D processing fails.
        """
        if not os.path.exists(ply_path):
            logger.error(f"Point cloud file not found: {ply_path}")
            raise RuntimeError(f"Point cloud file not found: {ply_path}")

        # Ensure output directory exists
        os.makedirs(output_dir, exist_ok=True)
        logger.info(f"Starting Open3D post-processing on point cloud: {ply_path}")

        try:
            # Step 1: Load point cloud
            logger.info("Step 1: Reading point cloud file...")
            pcd = o3d.io.read_point_cloud(ply_path)
            if pcd.is_empty():
                logger.error("Loaded point cloud contains zero points.")
                raise ValueError("Point cloud file is empty or unreadable.")
            logger.info(f"Point cloud loaded with {len(pcd.points)} points.")

            # Step 2: Noise removal
            logger.info("Step 2: Removing statistical outliers...")
            cl, ind = pcd.remove_statistical_outlier(nb_neighbors=20, std_ratio=2.0)
            pcd = pcd.select_by_index(ind)
            logger.info(f"Point cloud cleaned. Remaining points: {len(pcd.points)}.")

            # Step 3: Mesh generation
            logger.info("Step 3: Estimating point cloud normals...")
            pcd.estimate_normals()

            logger.info("Generating 3D mesh via Poisson Surface Reconstruction...")
            mesh, densities = o3d.geometry.TriangleMesh.create_from_point_cloud_poisson(pcd, depth=9)
            logger.info(f"Poisson mesh reconstructed. Vertices: {len(mesh.vertices)}, Triangles: {len(mesh.triangles)}")

            logger.info("Removing low-density vertices to clean reconstruction artifacts...")
            densities = np.asarray(densities)
            # Filter out vertices that fall in the lowest 5% density percentile
            density_threshold = np.percentile(densities, 5)
            vertices_to_remove = densities < density_threshold
            mesh.remove_vertices_by_mask(vertices_to_remove)
            logger.info(f"Artifacts filtered. Cleaned mesh vertices remaining: {len(mesh.vertices)}")

            # Step 4: Save outputs
            logger.info("Step 4: Writing output files...")
            out_ply = os.path.join(output_dir, "model.ply")
            out_glb = os.path.join(output_dir, "model.glb")

            # Write cleaned point cloud (.ply)
            o3d.io.write_point_cloud(out_ply, pcd)
            logger.info(f"Cleaned point cloud saved to: {out_ply}")

            # Write reconstructed triangle mesh (.glb)
            success = o3d.io.write_triangle_mesh(out_glb, mesh)
            if not success:
                logger.error(f"Failed to write reconstructed mesh to GLB format at: {out_glb}")
                raise IOError(f"Failed to write mesh to: {out_glb}")
            logger.info(f"Reconstructed GLB mesh saved to: {out_glb}")

            # Step 5: Compute basic measurements
            logger.info("Step 5: Estimating bounding box dimensions...")
            bbox = pcd.get_axis_aligned_bounding_box()
            min_bound = bbox.get_min_bound()
            max_bound = bbox.get_max_bound()
            dimensions = max_bound - min_bound

            dim_x = float(dimensions[0])
            dim_y = float(dimensions[1])
            dim_z = float(dimensions[2])
            logger.info(f"Calculated dimensions (X, Y, Z): ({dim_x:.4f}, {dim_y:.4f}, {dim_z:.4f})")

            # Normalize paths to use forward slashes
            norm_ply_path = os.path.normpath(out_ply).replace(os.sep, '/')
            norm_glb_path = os.path.normpath(out_glb).replace(os.sep, '/')

            return {
                "ply_url": norm_ply_path,
                "glb_url": norm_glb_path,
                "dimensions": {
                    "x": dim_x,
                    "y": dim_y,
                    "z": dim_z
                }
            }

        except Exception as e:
            logger.exception("An error occurred during Open3D processing steps.")
            raise RuntimeError(f"Open3D processing failed: {str(e)}") from e
