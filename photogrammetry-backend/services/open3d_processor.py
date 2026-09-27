import os
import logging
import numpy as np
import open3d as o3d

logger = logging.getLogger(__name__)


class Open3DProcessor:
    """Conservative dense-cloud cleanup and color-preserving mesh export."""

    def process(self, ply_path: str, output_dir: str, poisson_depth: int = 9) -> dict:
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

        # Conservative settings retain playground ground, equipment, and surrounding structures.
        _, inliers = pcd.remove_statistical_outlier(nb_neighbors=24, std_ratio=3.5)
        cleaned = pcd.select_by_index(inliers)
        if len(cleaned.points) < max(100, dense_count * 0.5):
            logger.warning("Outlier filter rejected too much geometry; preserving fused cloud.")
            cleaned = pcd
        cleaned_count = len(cleaned.points)
        cleaned.estimate_normals(o3d.geometry.KDTreeSearchParamKNN(knn=30))
        cleaned.orient_normals_consistent_tangent_plane(20)

        mesh, _ = o3d.geometry.TriangleMesh.create_from_point_cloud_poisson(
            cleaned, depth=poisson_depth, scale=1.05, linear_fit=True)
        # Scale bounding box crop to 1.25 to prevent cutting off playground boundaries and structures.
        mesh = mesh.crop(cleaned.get_axis_aligned_bounding_box().scale(1.25, cleaned.get_center()))
        if len(mesh.vertices) == 0 or len(mesh.triangles) == 0:
            raise RuntimeError("Poisson reconstruction produced no geometry.")
        mesh.remove_duplicated_vertices(); mesh.remove_degenerate_triangles()
        mesh.remove_duplicated_triangles(); mesh.remove_unreferenced_vertices()
        mesh.compute_vertex_normals()

        out_ply = os.path.join(output_dir, "model.ply")
        out_mesh_ply = os.path.join(output_dir, "mesh.ply")
        out_glb = os.path.join(output_dir, "model.glb")
        if not o3d.io.write_point_cloud(out_ply, cleaned):
            raise RuntimeError("Failed to export processed point cloud.")
        o3d.io.write_triangle_mesh(out_mesh_ply, mesh, write_vertex_normals=True, write_vertex_colors=True)
        if not o3d.io.write_triangle_mesh(out_glb, mesh, write_vertex_normals=True, write_vertex_colors=True):
            raise RuntimeError("Failed to export mesh.")
        with open(out_glb, "rb") as artifact:
            if artifact.read(4) != b"glTF":
                raise RuntimeError("GLB export is missing or invalid.")
        bbox = cleaned.get_axis_aligned_bounding_box()
        return {"ply_url": os.path.normpath(out_ply).replace(os.sep, "/"),
            "glb_url": os.path.normpath(out_glb).replace(os.sep, "/"),
            "dimensions": dict(zip(("x", "y", "z"), map(float, bbox.get_extent()))),
            "dense_point_count": dense_count, "filtered_point_count": cleaned_count,
            "mesh_vertex_count": len(mesh.vertices), "mesh_triangle_count": len(mesh.triangles),
            "removed_point_percent": 100 * (dense_count - cleaned_count) / dense_count}
