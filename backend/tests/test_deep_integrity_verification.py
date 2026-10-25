"""
Secure Audit — Deep Evidence Integrity Verification Unit Tests (tests/test_deep_integrity_verification.py)

Tests:
1. Deep byte-level hash calculation independent of stored metadata.
2. Comparison against database hash, storage provider metadata, and blockchain on-chain registration.
3. Tampered byte detection when metadata or database matches expected hash but actual file bytes do not.
4. Fast metadata-only check separation from deep verification (metadata match never marks status Verified).
5. Missing object detection (HTTP 404 / Missing status).
6. Unreadable object handling (I/O or stream failure -> HTTP 503 / Verification Failed without altering status).
7. Unavailable blockchain verification (node down -> HTTP 503 / Verification Failed without altering status).
8. Unregistered object handling (HTTP 409 / Unregistered).
9. Storage provider read_bytes_sha256 implementations for LocalStorageProvider and S3StorageProvider.
"""
import io
import os
import sys
import uuid
import shutil
import hashlib
import tempfile
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services import evidence_integrity as integrity
from services.storage_gateway import (
    LocalStorageProvider,
    S3StorageProvider,
    StoredObject,
    KeyNotFoundError,
    StorageError,
    StorageUnavailableError,
)

HASH_ORIGINAL = hashlib.sha256(b"original genuine evidence bytes").hexdigest()
HASH_TAMPERED = hashlib.sha256(b"tampered modified evidence bytes").hexdigest()
HASH_METADATA = hashlib.sha256(b"metadata reported hash").hexdigest()


def make_evidence(**overrides):
    base = {
        "id": uuid.uuid4(),
        "case_id": uuid.uuid4(),
        "file_name": "surveillance_clip.mp4",
        "file_hash": HASH_ORIGINAL,
        "file_url": f"cases/00000000-0000-0000-0000-000000000000/{uuid.uuid4()}_clip.mp4",
        "blockchain_tx_hash": "0x" + "a" * 64,
        "blockchain_block_number": 12,
        "blockchain_contract_address": "0xAbC0000000000000000000000000000000000001",
        "blockchain_registered_at": datetime(2026, 10, 1, tzinfo=timezone.utc),
        "status": "Pending",
        "last_verification_result": None,
        "last_verification_reason": None,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def make_registration(**overrides):
    base = {
        "sha256Hash": HASH_ORIGINAL,
        "fileName": "surveillance_clip.mp4",
        "caseId": "00000000-0000-0000-0000-000000000000",
    }
    base.update(overrides)
    return base


RECEIPT = {"blockNumber": 12, "contractAddress": "0xabc0000000000000000000000000000000000001"}


class DeepIntegrityVerificationRulesTest(unittest.TestCase):
    """Unit tests for evidence_integrity.deep_integrity_verification logic."""

    def test_fully_verified_all_match(self):
        ev = make_evidence()
        reg = make_registration(caseId=str(ev.case_id))
        report = integrity.deep_integrity_verification(
            evidence=ev,
            calculated_byte_hash=HASH_ORIGINAL,
            total_bytes=31,
            storage_metadata_hash=HASH_ORIGINAL,
            registration=reg,
            receipt=RECEIPT,
            duplicate_ids=[],
            blockchain_available=True,
        )
        self.assertEqual(report["status"], integrity.VERIFIED)
        self.assertEqual(report["reason"], "HASH_MATCH")
        self.assertTrue(report["db_matches_bytes"])
        self.assertTrue(report["metadata_matches_bytes"])
        self.assertTrue(report["chain_matches_bytes"])
        self.assertEqual(len(report["warnings"]), 0)

    def test_tampered_bytes_with_matching_db_and_metadata(self):
        """CRITICAL FORENSIC TEST:
        If stored metadata and DB both say HASH_ORIGINAL, but actual byte stream
        calculates HASH_TAMPERED, the deep check MUST reject and flag Tampered!
        """
        ev = make_evidence(file_hash=HASH_ORIGINAL)
        reg = make_registration(sha256Hash=HASH_ORIGINAL, caseId=str(ev.case_id))
        report = integrity.deep_integrity_verification(
            evidence=ev,
            calculated_byte_hash=HASH_TAMPERED,
            total_bytes=31,
            storage_metadata_hash=HASH_ORIGINAL,  # Storage metadata matches DB, but bytes are altered!
            registration=reg,
            receipt=RECEIPT,
            duplicate_ids=[],
            blockchain_available=True,
        )
        self.assertEqual(report["status"], integrity.TAMPERED)
        self.assertEqual(report["reason"], "HASH_MISMATCH")
        self.assertFalse(report["db_matches_bytes"])
        self.assertFalse(report["metadata_matches_bytes"])
        self.assertFalse(report["chain_matches_bytes"])
        self.assertTrue(any("Calculated byte-stream hash differs" in w for w in report["warnings"]))

    def test_tampered_bytes_with_altered_database_record(self):
        ev = make_evidence(file_hash=HASH_TAMPERED)
        reg = make_registration(sha256Hash=HASH_ORIGINAL, caseId=str(ev.case_id))
        report = integrity.deep_integrity_verification(
            evidence=ev,
            calculated_byte_hash=HASH_ORIGINAL,
            total_bytes=31,
            storage_metadata_hash=HASH_ORIGINAL,
            registration=reg,
            receipt=RECEIPT,
            duplicate_ids=[],
            blockchain_available=True,
        )
        self.assertEqual(report["status"], integrity.TAMPERED)
        self.assertFalse(report["db_matches_bytes"])

    def test_missing_object_distinction(self):
        ev = make_evidence()
        report = integrity.deep_integrity_verification(
            evidence=ev,
            calculated_byte_hash=None,
            is_missing=True,
            blockchain_available=True,
        )
        self.assertEqual(report["status"], integrity.MISSING)
        self.assertEqual(report["reason"], "EVIDENCE_MISSING")
        self.assertTrue(report["is_missing"])
        self.assertFalse(report["is_unreadable"])

    def test_unreadable_object_distinction(self):
        ev = make_evidence()
        report = integrity.deep_integrity_verification(
            evidence=ev,
            calculated_byte_hash=None,
            is_unreadable=True,
            error_detail="Timeout connecting to S3 storage gateway",
            blockchain_available=True,
        )
        self.assertEqual(report["status"], integrity.VERIFICATION_FAILED)
        self.assertEqual(report["reason"], "STORAGE_UNAVAILABLE")
        self.assertFalse(report["is_missing"])
        self.assertTrue(report["is_unreadable"])

    def test_blockchain_unavailable_fallback(self):
        ev = make_evidence()
        report = integrity.deep_integrity_verification(
            evidence=ev,
            calculated_byte_hash=HASH_ORIGINAL,
            total_bytes=31,
            storage_metadata_hash=HASH_ORIGINAL,
            registration=None,
            receipt=None,
            duplicate_ids=[],
            blockchain_available=False,
        )
        self.assertEqual(report["status"], integrity.VERIFICATION_FAILED)
        self.assertEqual(report["reason"], "BLOCKCHAIN_UNAVAILABLE")
        self.assertFalse(report["blockchain_available"])
        self.assertTrue(report["db_matches_bytes"])
        self.assertIsNone(report["chain_matches_bytes"])

    def test_unregistered_evidence_with_intact_bytes(self):
        ev = make_evidence()
        report = integrity.deep_integrity_verification(
            evidence=ev,
            calculated_byte_hash=HASH_ORIGINAL,
            total_bytes=31,
            storage_metadata_hash=HASH_ORIGINAL,
            registration=None,
            receipt=None,
            duplicate_ids=[],
            blockchain_available=True,
        )
        self.assertEqual(report["status"], integrity.UNREGISTERED)
        self.assertEqual(report["reason"], "NOT_REGISTERED")
        self.assertTrue(report["db_matches_bytes"])
        self.assertIsNone(report["chain_matches_bytes"])


class StorageProviderDeepReadBytesTest(unittest.TestCase):
    """Test read_bytes_sha256 on LocalStorageProvider and S3StorageProvider."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="secure_audit_deep_test_")
        self.local_provider = LocalStorageProvider(self.temp_dir)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_local_provider_read_bytes_sha256(self):
        test_content = b"forensic evidentiary data for unit test"
        expected_hash = hashlib.sha256(test_content).hexdigest()
        key = "cases/11111111-1111-1111-1111-111111111111/file.dat"
        self.local_provider.put(key, test_content)

        calculated_hash, total_size = self.local_provider.read_bytes_sha256(key)
        self.assertEqual(calculated_hash, expected_hash)
        self.assertEqual(total_size, len(test_content))

    def test_local_provider_read_bytes_nonexistent_key(self):
        with self.assertRaises(KeyNotFoundError):
            self.local_provider.read_bytes_sha256("cases/11111111-1111-1111-1111-111111111111/missing.dat")

    def test_s3_provider_read_bytes_sha256_mocked(self):
        mock_s3 = MagicMock()
        test_bytes = b"mocked cloud evidence exhibit stream bytes"
        expected_hash = hashlib.sha256(test_bytes).hexdigest()

        # Mock get_object to return a readable stream
        mock_body = io.BytesIO(test_bytes)
        mock_s3.get_object.return_value = {"Body": mock_body}

        provider = S3StorageProvider(
            bucket_name="test-bucket",
            region_name="auto",
            s3_client=mock_s3
        )

        key = "cases/22222222-2222-2222-2222-222222222222/cloud_file.mp4"
        calculated_hash, total_size = provider.read_bytes_sha256(key)

        self.assertEqual(calculated_hash, expected_hash)
        self.assertEqual(total_size, len(test_bytes))
        mock_s3.get_object.assert_called_once_with(Bucket="test-bucket", Key=key)


class FastMetadataVerificationApiTest(unittest.TestCase):
    """Unit tests for verify_evidence_hash when deep=False (fast metadata-only check)."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="secure_audit_fast_meta_")
        self.patcher_env = patch.dict(os.environ, {"UPLOADS_DIR": self.temp_dir, "STORAGE_BACKEND": "local"})
        self.patcher_env.start()

        import app
        self.app = app
        self.orig_uploads_dir = self.app.UPLOADS_DIR
        self.app.UPLOADS_DIR = self.temp_dir
        self.orig_load = app.load_evidence_for_user
        self.orig_user = app.get_current_user_info
        self.app.get_current_user_info = lambda r: {"id": str(uuid.uuid4()), "role": "Admin", "name": "Admin"}
        self.mock_db = MagicMock()
        self.mock_req = MagicMock()
        self.mock_req.headers = {"Authorization": "Bearer test"}

    def tearDown(self):
        self.app.UPLOADS_DIR = self.orig_uploads_dir
        self.app.load_evidence_for_user = self.orig_load
        self.app.get_current_user_info = self.orig_user
        self.patcher_env.stop()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_legacy_local_url_fast_verification_success(self):
        # Create a real local file under self.temp_dir
        case_id = str(uuid.uuid4())
        case_dir = os.path.join(self.temp_dir, "cases", case_id)
        os.makedirs(case_dir, exist_ok=True)
        file_path = os.path.join(case_dir, "sample.mp4")
        with open(file_path, "wb") as f:
            f.write(b"sample video bytes")

        ev = SimpleNamespace(
            id=uuid.uuid4(),
            case_id=uuid.UUID(case_id),
            file_hash="a" * 64,
            file_url=f"http://localhost:8000/uploads/cases/{case_id}/sample.mp4",
        )
        self.app.load_evidence_for_user = lambda eid, user, d: ev

        res = self.app.verify_evidence_hash(str(ev.id), self.mock_req, deep=False, db=self.mock_db)
        data = res["data"]
        self.assertFalse(data["deepVerification"])
        self.assertTrue(data["metadataOnly"])
        self.assertIsNone(data["storageMetadataHash"])
        self.assertEqual(data["status"], "MetadataUnavailable")
        self.assertIn("out-of-band SHA-256 metadata is not available on local storage", data["note"])

    def test_legacy_local_url_missing_file_raises_404(self):
        case_id = str(uuid.uuid4())
        ev = SimpleNamespace(
            id=uuid.uuid4(),
            case_id=uuid.UUID(case_id),
            file_hash="a" * 64,
            file_url=f"http://localhost:8000/uploads/cases/{case_id}/nonexistent.mp4",
        )
        self.app.load_evidence_for_user = lambda eid, user, d: ev

        from fastapi import HTTPException
        with self.assertRaises(HTTPException) as cm:
            self.app.verify_evidence_hash(str(ev.id), self.mock_req, deep=False, db=self.mock_db)
        self.assertEqual(cm.exception.status_code, 404)
        self.assertIn("Evidence file not found in local storage", cm.exception.detail)

    def test_legacy_local_url_path_traversal_raises_400(self):
        ev = SimpleNamespace(
            id=uuid.uuid4(),
            case_id=uuid.uuid4(),
            file_hash="a" * 64,
            file_url="http://localhost:8000/uploads/../../etc/passwd",
        )
        self.app.load_evidence_for_user = lambda eid, user, d: ev

        from fastapi import HTTPException
        with self.assertRaises(HTTPException) as cm:
            self.app.verify_evidence_hash(str(ev.id), self.mock_req, deep=False, db=self.mock_db)
        self.assertEqual(cm.exception.status_code, 400)
        self.assertIn("resolves outside", cm.exception.detail)

    def test_canonical_key_metadata_match(self):
        from services.storage_gateway import get_storage_provider, build_storage_key
        provider = get_storage_provider()
        case_id = str(uuid.uuid4())
        key = build_storage_key(case_id, "evidence.dat")
        obj = provider.put(key, b"canonical evidence content")

        ev = SimpleNamespace(
            id=uuid.uuid4(),
            case_id=uuid.UUID(case_id),
            file_hash=obj.sha256,
            file_url=key,
        )
        self.app.load_evidence_for_user = lambda eid, user, d: ev

        res = self.app.verify_evidence_hash(str(ev.id), self.mock_req, deep=False, db=self.mock_db)
        data = res["data"]
        self.assertFalse(data["deepVerification"])
        self.assertTrue(data["metadataOnly"])
        self.assertEqual(data["storageMetadataHash"], obj.sha256)
        self.assertTrue(data["matchesDatabase"])
        self.assertEqual(data["status"], "MetadataMatch")


if __name__ == "__main__":
    unittest.main()
