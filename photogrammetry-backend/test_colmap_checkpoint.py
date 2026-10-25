import os
import shutil
import tempfile
import unittest
from services.colmap_runner import ColmapRunner

class TestColmapCheckpoint(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.input_dir = os.path.join(self.test_dir, "selected")
        self.output_dir = os.path.join(self.test_dir, "colmap")
        os.makedirs(self.input_dir, exist_ok=True)
        os.makedirs(self.output_dir, exist_ok=True)
        # Create 3 dummy image files
        for i in range(3):
            with open(os.path.join(self.input_dir, f"frame_{i:03d}.jpg"), "wb") as f:
                f.write(b"\xFF\xD8\xFF\xE0" + b"\x00" * 50)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_checkpoint_skip_when_fused_ply_exists(self):
        dense_dir = os.path.join(self.output_dir, "dense")
        os.makedirs(dense_dir, exist_ok=True)
        fused_path = os.path.join(dense_dir, "fused.ply")
        # Write dummy fused.ply > 1000 bytes
        with open(fused_path, "wb") as f:
            f.write(b"ply\nformat ascii 1.0\nelement vertex 10\nend_header\n" + b"0.0 0.0 0.0\n" * 100)

        runner = ColmapRunner()
        res = runner.reconstruct(self.input_dir, self.output_dir)
        self.assertEqual(res["dense_ply_path"], fused_path.replace(os.sep, "/"))
        self.assertIn("sparse_stats", res)
        self.assertGreaterEqual(res["sparse_stats"]["registered_image_count"], 1)

if __name__ == "__main__":
    unittest.main()
