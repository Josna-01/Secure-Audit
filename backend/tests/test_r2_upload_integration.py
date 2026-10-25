"""
Phase 3A Integration Tests: Cloudflare R2 Uploads, Local-Mode Regression,
Duplicate Checks, Error Handling, and Download/Hash Verification.

Runs completely offline without real Cloudflare credentials, PostgreSQL, or Ganache.
"""

import io
import os
import sys
import uuid
import hashlib
import tempfile
import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.dialects.postgresql import JSONB, UUID

# Compile PostgreSQL types for SQLite in-memory testing
@compiles(JSONB, "sqlite")
def compile_jsonb_sqlite(type_, compiler, **kw):
    return "JSON"

@compiles(UUID, "sqlite")
def compile_uuid_sqlite(type_, compiler, **kw):
    return "TEXT"

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db import Base, get_db
from models import Case, Evidence, User
from services.storage_gateway import (
    S3StorageProvider,
    LocalStorageProvider,
    StoredObject,
    KeyAlreadyExistsError,
    KeyNotFoundError,
    StorageError,
    StoragePermissionError,
    StorageUnavailableError,
)
import app as main_app
from app import app, compute_evidence_file_hash
from fastapi.testclient import TestClient


class MockR2Client:
    """In-memory S3/R2 mock client."""

    def __init__(self):
        self.objects = {}
        self.put_calls = []
        self.deleted_keys = []

    def head_object(self, Bucket, Key):
        if Key not in self.objects:
            err = Exception("NoSuchKey")
            err.response = {"ResponseMetadata": {"HTTPStatusCode": 404}, "Error": {"Code": "NoSuchKey"}}
            raise err
        obj = self.objects[Key]
        return {
            "ContentLength": len(obj["body"]),
            "ContentType": obj["content_type"],
            "LastModified": obj["mtime"],
            "Metadata": obj["metadata"],
        }

    def put_object(self, Bucket, Key, Body, ContentType="application/octet-stream", Metadata=None, **kwargs):
        if Key in self.objects:
            err = Exception("PreconditionFailed")
            err.response = {"ResponseMetadata": {"HTTPStatusCode": 412}, "Error": {"Code": "PreconditionFailed"}}
            raise err
        body_bytes = Body if isinstance(Body, bytes) else Body.read()
        self.put_calls.append({"Bucket": Bucket, "Key": Key, "size": len(body_bytes), "Metadata": Metadata})
        self.objects[Key] = {
            "body": body_bytes,
            "metadata": Metadata or {},
            "content_type": ContentType,
            "mtime": datetime.now(timezone.utc),
        }
        return {"ETag": '"mock-etag"'}

    def get_object(self, Bucket, Key):
        if Key not in self.objects:
            err = Exception("NoSuchKey")
            err.response = {"ResponseMetadata": {"HTTPStatusCode": 404}, "Error": {"Code": "NoSuchKey"}}
            raise err
        obj = self.objects[Key]
        return {"Body": io.BytesIO(obj["body"])}

    def delete_object(self, Bucket, Key):
        self.deleted_keys.append(Key)
        self.objects.pop(Key, None)
        return {"ResponseMetadata": {"HTTPStatusCode": 204}}


class TestR2UploadIntegration(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(cls.engine)
        cls.TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=cls.engine)

        # Intercept get_db dependency and internal SessionLocal calls
        def override_get_db():
            db = cls.TestingSessionLocal()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db
        cls.orig_session_local = main_app.SessionLocal
        main_app.SessionLocal = cls.TestingSessionLocal

        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        app.dependency_overrides.clear()
        main_app.SessionLocal = cls.orig_session_local

    def setUp(self):
        self.db = self.TestingSessionLocal()
        # Seed test user and case
        self.user_id = uuid.uuid4()
        self.case_id = uuid.uuid4()

        test_user = User(
            id=self.user_id,
            email=f"officer_{uuid.uuid4().hex[:6]}@police.gov.in",
            full_name="Forensic Inspector",
            role="admin",
            clearance_level=3,
        )
        test_case = Case(
            id=self.case_id,
            title="Forensic Investigation Case",
            offence_type="Armed Robbery",
            case_number=f"CR-{uuid.uuid4().hex[:8]}",
            created_by=self.user_id,
        )
        self.db.add(test_user)
        self.db.add(test_case)
        self.db.commit()

        self.mock_r2_client = MockR2Client()
        self.mock_s3_provider = S3StorageProvider(
            bucket_name="secure-audit-evidence",
            region_name="auto",
            endpoint_url="https://test.r2.cloudflarestorage.com",
            access_key_id="test_key",
            secret_access_key="test_secret",
            s3_client=self.mock_r2_client,
        )

        self.user_info_patch = patch(
            "app.get_current_user_info",
            return_value={"id": str(self.user_id), "role": "admin", "name": "Forensic Inspector"}
        )
        self.user_info_patch.start()

        self.case_access_patch = patch("app.check_case_access", return_value=None)
        self.case_access_patch.start()

        def fake_register(*args, **kwargs):
            return {
                "transactionHash": "0x" + uuid.uuid4().hex + uuid.uuid4().hex,
                "blockNumber": 1234,
                "contractAddress": "0x" + "bb" * 20,
                "gasUsed": 21000,
                "timestamp": datetime.now(timezone.utc),
                "from": "0x" + "cc" * 20,
                "chainId": 1337,
            }

        self.blockchain_patch = patch(
            "app.blockchain_service.register_evidence",
            side_effect=fake_register
        )
        self.mock_register = self.blockchain_patch.start()

    def tearDown(self):
        self.user_info_patch.stop()
        self.case_access_patch.stop()
        self.blockchain_patch.stop()
        self.db.close()

    def test_r2_mode_upload_success(self):
        """When STORAGE_BACKEND=s3, evidence uploads to R2 and stores canonical key."""
        payload_bytes = b"CONFIDENTIAL FORENSIC EXHIBIT DATA: Weapon Serial 998822"
        expected_hash = hashlib.sha256(payload_bytes).hexdigest()

        with patch.dict(os.environ, {"STORAGE_BACKEND": "s3"}):
            with patch("app.get_storage_provider", return_value=self.mock_s3_provider):
                response = self.client.post(
                    "/evidence/upload",
                    data={
                        "case_id": str(self.case_id),
                        "evidence_type": "Document",
                        "description": "Crime Scene Weapon Certificate",
                    },
                    files={"file": ("weapon_cert.pdf", payload_bytes, "application/pdf")},
                )

        self.assertEqual(response.status_code, 200, f"Upload failed: {response.text}")
        data = response.json()["data"]

        # Canonical key must be stored in file_url
        file_url = data["file_url"]
        self.assertTrue(file_url.startswith(f"cases/{self.case_id}/"), f"Unexpected key: {file_url}")
        self.assertTrue(file_url.endswith("_weapon_cert.pdf"))
        self.assertEqual(data["file_hash"], expected_hash)

        # Object must be stored in the mock S3/R2 client
        self.assertIn(file_url, self.mock_r2_client.objects)
        stored_bytes = self.mock_r2_client.objects[file_url]["body"]
        self.assertEqual(stored_bytes, payload_bytes)
        self.assertEqual(self.mock_r2_client.objects[file_url]["metadata"]["sha256"], expected_hash)

        # Database record must reflect canonical key
        ev_id = uuid.UUID(data["id"])
        db_ev = self.db.query(Evidence).filter(Evidence.id == ev_id).first()
        self.assertIsNotNone(db_ev)
        self.assertEqual(db_ev.file_url, file_url)
        self.assertEqual(db_ev.file_hash, expected_hash)
        self.assertEqual(db_ev.file_name, "weapon_cert.pdf")

        # Blockchain registration must have been called with the hash
        self.mock_register.assert_called_once()
        args = self.mock_register.call_args[0]
        self.assertEqual(args[1], str(self.case_id))
        self.assertEqual(args[3], expected_hash)

    @patch("app.require_admin")
    def test_storage_diagnostics_are_admin_guarded_and_secret_free(self, mock_require_admin):
        env = {
            "STORAGE_BACKEND": "s3",
            "S3_BUCKET_NAME": "bucket-must-not-be-returned",
            "S3_ENDPOINT_URL": "https://account-must-not-be-returned.r2.cloudflarestorage.com",
            "S3_REGION": "auto",
            "S3_ACCESS_KEY_ID": "access-must-not-be-returned",
            "S3_SECRET_ACCESS_KEY": "secret-must-not-be-returned",
        }
        with patch.dict(os.environ, env, clear=False):
            response = self.client.get("/admin/storage/diagnostics")

        self.assertEqual(response.status_code, 200)
        mock_require_admin.assert_called_once()
        body = response.json()
        self.assertEqual(body["data"]["active_backend"], "s3")
        self.assertTrue(body["data"]["r2_endpoint_detected"])
        rendered = response.text
        for value in env.values():
            self.assertNotIn(value, rendered)

    def test_local_mode_upload_regression(self):
        """When STORAGE_BACKEND=local, legacy local disk upload remains 100% active."""
        payload_bytes = b"LOCAL EVIDENCE ARTIFACT"
        expected_hash = hashlib.sha256(payload_bytes).hexdigest()

        with patch.dict(os.environ, {"STORAGE_BACKEND": "local", "USE_LOCAL_STORAGE": "True"}):
            response = self.client.post(
                "/evidence/upload",
                data={
                    "case_id": str(self.case_id),
                    "evidence_type": "Physical",
                    "description": "Local Evidence Exhibit",
                },
                files={"file": ("local_artifact.txt", payload_bytes, "text/plain")},
            )

        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]

        file_url = data["file_url"]
        self.assertIn("/uploads/cases/", file_url)
        self.assertEqual(data["file_hash"], expected_hash)

        # Verify mock R2 client was NOT touched
        self.assertEqual(len(self.mock_r2_client.objects), 0)

    def test_r2_upload_storage_failure_leaves_no_misleading_db_record(self):
        """Failed storage upload must return 502 and never commit a dangling evidence row."""
        failing_provider = MagicMock()
        failing_provider.put.side_effect = StorageUnavailableError("R2 connection timed out")

        initial_count = self.db.query(Evidence).count()

        with patch.dict(os.environ, {"STORAGE_BACKEND": "s3"}):
            with patch("app.get_storage_provider", return_value=failing_provider):
                response = self.client.post(
                    "/evidence/upload",
                    data={
                        "case_id": str(self.case_id),
                        "evidence_type": "Audio",
                        "description": "Failing Upload Exhibit",
                    },
                    files={"file": ("sample.wav", b"AUDIO_DATA", "audio/wav")},
                )

        self.assertEqual(response.status_code, 502)
        self.assertIn("Evidence cloud storage provider unreachable", response.json()["detail"])

        # No record should be committed in the database
        final_count = self.db.query(Evidence).count()
        self.assertEqual(final_count, initial_count)
        self.mock_register.assert_not_called()

    def test_duplicate_file_in_same_case_rejected(self):
        """Duplicate SHA-256 within the same case must return HTTP 409 Conflict."""
        payload_bytes = b"IDENTICAL FORENSIC BYTES FOR DUPLICATE CHECK"

        with patch.dict(os.environ, {"STORAGE_BACKEND": "s3"}):
            with patch("app.get_storage_provider", return_value=self.mock_s3_provider):
                res1 = self.client.post(
                    "/evidence/upload",
                    data={"case_id": str(self.case_id), "evidence_type": "Document"},
                    files={"file": ("doc_v1.pdf", payload_bytes, "application/pdf")},
                )
                self.assertEqual(res1.status_code, 200)

                # Second upload with identical bytes
                res2 = self.client.post(
                    "/evidence/upload",
                    data={"case_id": str(self.case_id), "evidence_type": "Document"},
                    files={"file": ("doc_v2.pdf", payload_bytes, "application/pdf")},
                )
                self.assertEqual(res2.status_code, 409)
                self.assertTrue(res2.json()["duplicate"])
                self.assertIn("Duplicate file detected", res2.json()["detail"])

        # Exactly 1 object stored in R2 mock
        self.assertEqual(len(self.mock_r2_client.objects), 1)

    def test_download_canonical_r2_key_verified(self):
        """Download endpoint retrieves canonical key from R2 and validates SHA-256 headers."""
        file_bytes = b"RECOVERED CRIME SCENE EVIDENCE STREAM"
        file_hash = hashlib.sha256(file_bytes).hexdigest()
        canonical_key = f"cases/{self.case_id}/test_recovered_exhibit.bin"

        # Pre-populate object in mock R2
        self.mock_r2_client.objects[canonical_key] = {
            "body": file_bytes,
            "metadata": {"sha256": file_hash, "verified_size": str(len(file_bytes))},
            "content_type": "application/octet-stream",
            "mtime": datetime.now(timezone.utc),
        }

        # Create DB record referencing canonical key
        ev = Evidence(
            id=uuid.uuid4(),
            case_id=self.case_id,
            evidence_type="Digital",
            file_url=canonical_key,
            file_hash=file_hash,
            file_name="test_recovered_exhibit.bin",
            file_size=len(file_bytes),
            uploaded_by=self.user_id,
        )
        self.db.add(ev)
        self.db.commit()

        with patch.dict(os.environ, {"STORAGE_BACKEND": "s3"}):
            with patch("app.get_storage_provider", return_value=self.mock_s3_provider):
                res = self.client.get(f"/evidence/{ev.id}/download")

        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.content, file_bytes)
        self.assertEqual(res.headers["X-Evidence-SHA256"], file_hash)
        self.assertEqual(res.headers["X-Evidence-Integrity"], "match")

    def test_compute_evidence_file_hash_canonical_r2_key(self):
        """compute_evidence_file_hash uses provider.stat() to verify canonical R2 exhibits."""
        file_bytes = b"CRIME SCENE WEAPON METROLOGY SCAN"
        file_hash = hashlib.sha256(file_bytes).hexdigest()
        canonical_key = f"cases/{self.case_id}/scan_01.dat"

        self.mock_r2_client.objects[canonical_key] = {
            "body": file_bytes,
            "metadata": {"sha256": file_hash, "verified_size": str(len(file_bytes))},
            "content_type": "application/octet-stream",
            "mtime": datetime.now(timezone.utc),
        }

        with patch.dict(os.environ, {"STORAGE_BACKEND": "s3"}):
            with patch("app.get_storage_provider", return_value=self.mock_s3_provider):
                computed = compute_evidence_file_hash(canonical_key)

        self.assertEqual(computed, file_hash)

    def test_r2_upload_blockchain_failure_rollback_and_immutability(self):
        """When blockchain registration fails, DB is rolled back and evidence is not silently deleted."""
        from services.blockchain_service import BlockchainUnavailable

        failing_register = MagicMock(side_effect=BlockchainUnavailable("RPC Ganache node disconnected"))

        with patch.dict(os.environ, {"STORAGE_BACKEND": "s3"}):
            with patch("app.get_storage_provider", return_value=self.mock_s3_provider):
                with patch("app.blockchain_service.register_evidence", failing_register):
                    res = self.client.post(
                        "/evidence/upload",
                        data={"case_id": str(self.case_id), "evidence_type": "Video"},
                        files={"file": ("evidence.mp4", b"VIDEO_BYTES", "video/mp4")},
                    )

        self.assertEqual(res.status_code, 503)
        self.assertIn("blockchain registration failed", res.json()["detail"])

        # DB must have rolled back
        evidence_in_db = self.db.query(Evidence).filter(Evidence.file_name == "evidence.mp4").first()
        self.assertIsNone(evidence_in_db)

        # Immutability: Cloud object was NOT silently deleted from storage
        self.assertEqual(len(self.mock_r2_client.deleted_keys), 0)

    def test_r2_upload_key_collision_returns_409(self):
        """When S3 put fails due to KeyAlreadyExistsError, HTTP 409 is returned."""
        collision_provider = MagicMock()
        collision_provider.put.side_effect = KeyAlreadyExistsError("Collision detected in bucket")

        with patch.dict(os.environ, {"STORAGE_BACKEND": "s3"}):
            with patch("app.get_storage_provider", return_value=collision_provider):
                res = self.client.post(
                    "/evidence/upload",
                    data={"case_id": str(self.case_id), "evidence_type": "Document"},
                    files={"file": ("colliding_doc.pdf", b"DATA", "application/pdf")},
                )

        self.assertEqual(res.status_code, 409)
        self.assertIn("already exists", res.json()["detail"])

    def test_r2_upload_hash_mismatch_raises_500(self):
        """When S3 put returns a mismatched SHA-256 hash, HTTP 500 integrity error is raised."""
        mismatch_provider = MagicMock()
        mismatch_provider.put.return_value = StoredObject(
            key=f"cases/{self.case_id}/test.pdf",
            size=10,
            sha256="00" * 32,  # Corrupted hash
            content_type="application/pdf",
        )

        with patch.dict(os.environ, {"STORAGE_BACKEND": "s3"}):
            with patch("app.get_storage_provider", return_value=mismatch_provider):
                res = self.client.post(
                    "/evidence/upload",
                    data={"case_id": str(self.case_id), "evidence_type": "Document"},
                    files={"file": ("corrupt.pdf", b"ORIGINAL_BYTES", "application/pdf")},
                )

        self.assertEqual(res.status_code, 500)
        self.assertIn("integrity error", res.json()["detail"])

    def test_download_canonical_r2_key_missing_returns_404(self):
        """When an exhibit key does not exist in R2, download returns 404."""
        canonical_key = f"cases/{self.case_id}/ghost_file.bin"
        ev = Evidence(
            id=uuid.uuid4(),
            case_id=self.case_id,
            evidence_type="Digital",
            file_url=canonical_key,
            file_hash="aa" * 32,
            file_name="ghost_file.bin",
            file_size=100,
            uploaded_by=self.user_id,
        )
        self.db.add(ev)
        self.db.commit()

        with patch.dict(os.environ, {"STORAGE_BACKEND": "s3"}):
            with patch("app.get_storage_provider", return_value=self.mock_s3_provider):
                res = self.client.get(f"/evidence/{ev.id}/download")

        self.assertEqual(res.status_code, 404)
        self.assertIn("not found", res.json()["detail"])


if __name__ == "__main__":
    unittest.main()
