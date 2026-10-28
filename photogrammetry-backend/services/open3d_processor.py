import os
import logging
import numpy as np
import open3d as o3d
from scipy.spatial import cKDTree

logger = logging.getLogger(__name__)


class Open3DProcessor:
    """High-fidelity point cloud cleanup, density trimming, smoothing, and color-preserving mesh export."""

    def process(self, ply_path: str, output_dir: str, poisson_depth: int = 10) -> dict:
        if not os.path.isfile(ply_path):
            raise RuntimeError(f"Point cloud file not found: {ply_path}")
        os.makedirs(output_dir, exist_ok=True)
        pcd = o3d.io.read_point_cloud(ply_path)
        if pcd.is_empty():
            raise RuntimeError("Point cloud file is empty or unreadable.")
        points = np.asarray(pcd.points)
        if not np.isfinite(points).all():
            pcd = pcd.select_by_index(np.flatnonzero(np.isfinite(points).all(axis=1)))
        dense_count = len(pcd.points)

        # Statistical outlier removal to eliminate stray noise points
        _, inliers = pcd.remove_statistical_outlier(nb_neighbors=24, std_ratio=3.0)
        cleaned = pcd.select_by_index(inliers)
        if len(cleaned.points) < max(100, dense_count * 0.5):
            logger.warning("Outlier filter rejected too much geometry; preserving fused cloud.")
            cleaned = pcd
        cleaned_count = len(cleaned.points)

        # High-quality normal estimation & consistent orientation
        cleaned.estimate_normals(o3d.geometry.KDTreeSearchParamKNN(knn=30))
        cleaned.orient_normals_consistent_tangent_plane(20)

        # Poisson Surface Reconstruction with detail resolution
        mesh, densities = o3d.geometry.TriangleMesh.create_from_point_cloud_poisson(
            cleaned, depth=poisson_depth, scale=1.05, linear_fit=True
        )

        # Crop directly to point cloud bounding box to retain solid watertight surface without ballooning
        bbox = cleaned.get_axis_aligned_bounding_box()
        mesh = mesh.crop(bbox)

        # Remove small disconnected floating islands / speckles
        triangle_clusters, num_triangles, _ = mesh.cluster_connected_triangles()
        triangle_clusters = np.asarray(triangle_clusters)
        num_triangles = np.asarray(num_triangles)
        if len(num_triangles) > 0:
            min_cluster_size = max(500, int(len(mesh.triangles) * 0.005))
            triangles_to_remove = num_triangles[triangle_clusters] < min_cluster_size
            mesh.remove_triangles_by_mask(triangles_to_remove)

        # Clean duplicate and degenerate geometric topology
        mesh.remove_duplicated_vertices()
        mesh.remove_degenerate_triangles()
        mesh.remove_duplicated_triangles()
        mesh.remove_unreferenced_vertices()

        # Simplify mesh with quadric error decimation for crisp geometry and fast web rendering
        if len(mesh.triangles) > 350000:
            mesh = mesh.simplify_quadric_decimation(target_number_of_triangles=350000)

        # Surface smoothing: Taubin smoothing eliminates mesh noise without shrinking features
        mesh = mesh.filter_smooth_taubin(number_of_iterations=10)

        # High-fidelity color transfer: map vibrant RGB colors from dense point cloud to mesh vertices
        if cleaned.has_colors() and len(cleaned.colors) > 0:
            pcd_points = np.asarray(cleaned.points)
            pcd_colors = np.asarray(cleaned.colors)
            mesh_verts = np.asarray(mesh.vertices)
            
            tree = cKDTree(pcd_points)
            _, indices = tree.query(mesh_verts, k=3)
            # Weighted/averaged color from nearest 3 point cloud points
            vertex_colors = np.mean(pcd_colors[indices], axis=1)
            mesh.vertex_colors = o3d.utility.Vector3dVector(vertex_colors)

        # Compute smooth vertex normals for natural light reflection in 3D viewers
        mesh.compute_vertex_normals()

        # Voxel downsample exported point cloud for fast web viewer loading
        pcd_export = cleaned.voxel_down_sample(voxel_size=0.02)

        out_ply = os.path.join(output_dir, "model.ply")
        out_mesh_ply = os.path.join(output_dir, "mesh.ply")
        out_glb = os.path.join(output_dir, "model.glb")
        
        if not o3d.io.write_point_cloud(out_ply, pcd_export):
            raise RuntimeError("Failed to export processed point cloud.")
        o3d.io.write_triangle_mesh(out_mesh_ply, mesh, write_vertex_normals=True, write_vertex_colors=True)
        if not o3d.io.write_triangle_mesh(out_glb, mesh, write_vertex_normals=True, write_vertex_colors=True):
            raise RuntimeError("Failed to export mesh.")
            
        with open(out_glb, "rb") as artifact:
            if artifact.read(4) != b"glTF":
                raise RuntimeError("GLB export is missing or invalid.")
                
        bbox = cleaned.get_axis_aligned_bounding_box()
        return {
            "ply_url": os.path.normpath(out_ply).replace(os.sep, "/"),
            "glb_url": os.path.normpath(out_glb).replace(os.sep, "/"),
            "dimensions": dict(zip(("x", "y", "z"), map(float, bbox.get_extent()))),
            "dense_point_count": dense_count,
            "filtered_point_count": cleaned_count,
            "mesh_vertex_count": len(mesh.vertices),
            "mesh_triangle_count": len(mesh.triangles),
            "removed_point_percent": 100 * (dense_count - cleaned_count) / dense_count
        }

