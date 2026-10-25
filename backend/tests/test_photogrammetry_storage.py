"""
Secure Audit — Photogrammetry and Storage Gateway Integration Tests (tests/test_photogrammetry_storage.py)

Tests:
1. Local-storage regression: Saving models and reading input evidence via LocalStorageProvider.
2. Cloud/R2 storage with mocked S3 provider: reading canonical evidence and writing models.
3. Immutability and collision prevention: duplicate model key overwrite is strictly rejected.
4. Authenticated model access endpoints: GET /photogrammetry/model/{job_id}/{fmt}.
5. Unauthorized access rejection (403 when user is not assigned/authorized to case).
6. Unauthenticated access rejection (401 when token is missing/invalid).
7. Safe handling of temporary files and intermediate workspace cleanup.
"""
import io
import os
import sys
import uuid
import shutil
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.storage_gateway import (
    LocalStorageProvider,
    S3StorageProvider,
    build_model_storage_key,
    build_storage_key,
    KeyAlreadyExistsError,
    KeyNotFoundError,
    PathTraversalError,
)
from app import app


class PhotogrammetryStorageIntegrationTest(unittest.TestCase):
    """Test photogrammetry storage gateway read/write and key generation."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="photogrammetry_storage_test_")
        self.local_provider = LocalStorageProvider(self.temp_dir)
        self.case_id = str(uuid.uuid4())
        self.job_id = str(uuid.uuid4())

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_build_model_storage_key_canonical_format(self):
        glb_key = build_model_storage_key(self.case_id, self.job_id, "glb")
        ply_key = build_model_storage_key(self.case_id, self.job_id, "ply")

        self.assertEqual(glb_key, f"models/{self.case_id}/{self.job_id}_model.glb")
        self.assertEqual(ply_key, f"models/{self.case_id}/{self.job_id}_model.ply")

    def test_build_model_storage_key_rejects_invalid_extension(self):
        with self.assertRaises(Exception):
            build_model_storage_key(self.case_id, self.job_id, "exe")

    def test_local_storage_model_put_and_get(self):
        glb_key = build_model_storage_key(self.case_id, self.job_id, "glb")
        fake_glb_bytes = b"glTF fake binary content \x00\x01\x02"

        # Put model into local storage
        stored = self.local_provider.put(glb_key, fake_glb_bytes, content_type="model/gltf-binary")
        self.assertEqual(stored.key, glb_key)
        self.assertEqual(stored.size, len(fake_glb_bytes))

        # Re-read model from storage
        stream = self.local_provider.get(glb_key)
        read_back = stream.read()
        stream.close()
        self.assertEqual(read_back, fake_glb_bytes)

    def test_local_storage_rejects_model_overwrite(self):
        glb_key = build_model_storage_key(self.case_id, self.job_id, "glb")
        self.local_provider.put(glb_key, b"initial model")
        with self.assertRaises(KeyAlreadyExistsError):
            self.local_provider.put(glb_key, b"overwritten model")

    def test_mocked_r2_model_put_and_get(self):
        mock_s3 = MagicMock()
        mock_s3.head_object.side_effect = Exception("NoSuchKey")
        mock_s3.head_object.side_effect.response = {"Error": {"Code": "NoSuchKey"}}

        provider = S3StorageProvider(
            bucket_name="forensic-models",
            region_name="auto",
            s3_client=mock_s3
        )

        glb_key = build_model_storage_key(self.case_id, self.job_id, "glb")
        fake_glb = b"R2 synthetic glb binary"
        stored = provider.put(glb_key, fake_glb, content_type="model/gltf-binary")

        self.assertEqual(stored.key, glb_key)
        self.assertEqual(stored.size, len(fake_glb))
        mock_s3.put_object.assert_called_once()
        put_call_kwargs = mock_s3.put_object.call_args[1]
        self.assertEqual(put_call_kwargs["Bucket"], "forensic-models")
        self.assertEqual(put_call_kwargs["Key"], glb_key)
        self.assertEqual(put_call_kwargs["ContentType"], "model/gltf-binary")

    def test_mocked_r2_reading_evidence_video(self):
        mock_s3 = MagicMock()
        evidence_key = f"cases/{self.case_id}/test_video.mp4"
        fake_video_bytes = b"fake video bytes for photogrammetry"
        mock_s3.get_object.return_value = {"Body": io.BytesIO(fake_video_bytes)}

        provider = S3StorageProvider(
            bucket_name="evidence-vault",
            region_name="auto",
            s3_client=mock_s3
        )

        stream = provider.get(evidence_key)
        read_bytes = stream.read()
        self.assertEqual(read_bytes, fake_video_bytes)
        mock_s3.get_object.assert_called_once_with(Bucket="evidence-vault", Key=evidence_key)


class PhotogrammetryModelEndpointTest(unittest.TestCase):
    """Test authenticated endpoints /photogrammetry/model/{job_id}/{fmt}."""

    def setUp(self):
        self.client = TestClient(app)
        self.case_id = str(uuid.uuid4())
        self.job_id = str(uuid.uuid4())

    def test_unauthenticated_request_rejected(self):
        res = self.client.get(f"/photogrammetry/model/{self.job_id}/glb")
        self.assertEqual(res.status_code, 401)

    def test_invalid_format_rejected(self):
        with patch("app.get_current_user_info", return_value={"id": str(uuid.uuid4()), "role": "admin"}):
            res = self.client.get(
                f"/photogrammetry/model/{self.job_id}/exe",
                headers={"Authorization": "Bearer fake_token"}
            )
            self.assertEqual(res.status_code, 400)

    @patch("app.get_current_user_info")
    @patch("app.requests.get")
    def test_nonexistent_job_returns_404(self, mock_requests_get, mock_user):
        mock_user.return_value = {"id": str(uuid.uuid4()), "role": "admin"}
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_requests_get.return_value = mock_resp

        res = self.client.get(
            f"/photogrammetry/model/{self.job_id}/glb",
            headers={"Authorization": "Bearer fake_token"}
        )
        self.assertEqual(res.status_code, 404)

    @patch("app.get_current_user_info")
    @patch("app.requests.get")
    @patch("app.check_case_access")
    def test_unauthorized_case_access_rejected_with_403(self, mock_check_access, mock_requests_get, mock_user):
        from fastapi import HTTPException
        mock_user.return_value = {"id": str(uuid.uuid4()), "role": "investigator"}
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "job_id": self.job_id,
            "case_id": self.case_id,
            "status": "Completed",
            "model_url": f"models/{self.case_id}/{self.job_id}_model.glb"
        }
        mock_requests_get.return_value = mock_resp
        mock_check_access.side_effect = HTTPException(status_code=403, detail="Forbidden: You do not have access to this case")

        res = self.client.get(
            f"/photogrammetry/model/{self.job_id}/glb",
            headers={"Authorization": "Bearer fake_token"}
        )
        self.assertEqual(res.status_code, 403)

    @patch("app.get_current_user_info")
    @patch("app.requests.get")
    @patch("app.check_case_access")
    @patch("app.get_storage_provider")
    @patch("app.write_audit_log")
    def test_authorized_model_view_and_download_stream(
        self, mock_audit, mock_get_provider, mock_check_access, mock_requests_get, mock_user
    ):
        mock_user.return_value = {"id": str(uuid.uuid4()), "role": "lead_investigator"}
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        glb_key = f"models/{self.case_id}/{self.job_id}_model.glb"
        mock_resp.json.return_value = {
            "job_id": self.job_id,
            "case_id": self.case_id,
            "status": "Completed",
            "model_url": glb_key
        }
        mock_requests_get.return_value = mock_resp
        mock_check_access.return_value = None

        fake_glb_stream = io.BytesIO(b"glTF binary stream bytes for viewer")
        mock_provider = MagicMock()
        mock_provider.get.return_value = fake_glb_stream
        mock_get_provider.return_value = mock_provider

        # Test inline viewing (for 3D viewer)
        res = self.client.get(
            f"/photogrammetry/model/{self.job_id}/glb",
            headers={"Authorization": "Bearer fake_token"}
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.content, b"glTF binary stream bytes for viewer")
        self.assertIn("inline", res.headers.get("content-disposition", ""))
        mock_provider.get.assert_called_with(glb_key)
        mock_audit.assert_called()


class PhotogrammetryWorkspaceCleanupTest(unittest.TestCase):
    """Test safe intermediate file cleanup after processing."""

    def setUp(self):
        self.work_dir = tempfile.mkdtemp(prefix="photo_cleanup_test_")
        self.job_dir = os.path.join(self.work_dir, "test_job")
        self.frames_dir = os.path.join(self.job_dir, "frames")
        self.colmap_dir = os.path.join(self.job_dir, "colmap")
        self.output_dir = os.path.join(self.job_dir, "output")
        self.video_path = os.path.join(self.job_dir, "input_video.mp4")

        os.makedirs(self.frames_dir, exist_ok=True)
        os.makedirs(self.colmap_dir, exist_ok=True)
        os.makedirs(self.output_dir, exist_ok=True)

        with open(self.video_path, "wb") as f:
            f.write(b"video bytes")
        with open(os.path.join(self.frames_dir, "frame_001.jpg"), "wb") as f:
            f.write(b"frame 1")
        with open(os.path.join(self.colmap_dir, "sparse.bin"), "wb") as f:
            f.write(b"sparse data")
        with open(os.path.join(self.output_dir, "model.glb"), "wb") as f:
            f.write(b"final model")

    def tearDown(self):
        shutil.rmtree(self.work_dir, ignore_errors=True)

    def test_safe_cleanup_removes_intermediates_and_preserves_output(self):
        # Simulate intermediate cleanup routine
        for temp_path in (self.frames_dir, self.colmap_dir, self.video_path):
            if os.path.isdir(temp_path):
                shutil.rmtree(temp_path, ignore_errors=True)
            elif os.path.isfile(temp_path):
                os.remove(temp_path)

        # Output artifact must be preserved
        self.assertTrue(os.path.isfile(os.path.join(self.output_dir, "model.glb")))
        # Intermediates must be removed
        self.assertFalse(os.path.exists(self.frames_dir))
        self.assertFalse(os.path.exists(self.colmap_dir))
        self.assertFalse(os.path.exists(self.video_path))


if __name__ == "__main__":
    unittest.main()
