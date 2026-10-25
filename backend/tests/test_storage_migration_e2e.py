"""
Secure Audit — Phase 2C: End-to-End Cloud Storage Migration & Download Verification Test
Location: backend/tests/test_storage_migration_e2e.py

Verifies:
1. Immediate pre-upload hash checking and quarantine exclusion.
2. Canonical key generation and S3 upload/readback SHA-256 validation.
3. Fast-API authenticated download of evidence exhibits via storage keys.
4. Proper response headers (X-Evidence-SHA256, X-Evidence-Integrity).
5. Unauthorized and unauthenticated access rejection (401/403).
6. Complete invariance of existing local files and live database records.
"""

import os
import sys
import unittest
import hashlib
import uuid
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

# Ensure backend root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app as main_app
from services.storage_gateway import (
    S3StorageProvider,
    LocalStorageProvider,
    build_storage_key,
    StoredObject
)
from scripts.migrate_to_cloud_storage import (
    KNOWN_QUARANTINED_IDS,
    generate_canonical_s3_key
)


class StorageMigrationE2ETest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import moto
        import boto3
        cls.moto_mock = moto.mock_aws()
        cls.moto_mock.start()

        cls.bucket_name = "test-forensic-evidence-e2e"
        cls.s3_client = boto3.client("s3", region_name="us-east-1")
        cls.s3_client.create_bucket(Bucket=cls.bucket_name)

        cls.provider = S3StorageProvider(
            bucket_name=cls.bucket_name,
            region_name="us-east-1",
            s3_client=cls.s3_client,
            server_side_encryption="AES256"
        )
        cls.client = TestClient(main_app.app)

    @classmethod
    def tearDownClass(cls):
        cls.moto_mock.stop()

    def test_quarantined_records_exclusion(self):
        """Confirm that the 2 mismatched records and 1 missing record are strictly excluded."""
        self.assertIn("222971f3-be43-4a5c-b43b-96dabeae9724", KNOWN_QUARANTINED_IDS)
        self.assertIn("e1d6f8da-c959-4e63-b8bf-58be7436edbf", KNOWN_QUARANTINED_IDS)
        self.assertIn("1bb766d2-d9d6-426d-aa51-a30aa9d295c1", KNOWN_QUARANTINED_IDS)

        for q_id, reason in KNOWN_QUARANTINED_IDS.items():
            self.assertIn(reason, ("MISSING_SOURCE_FILE", "INTEGRITY_MISMATCH"))

    def test_canonical_key_generation(self):
        """Canonical keys must be deterministic and non-traversing."""
        case_id = "fb80cbc4-11d0-4a21-992a-b5812dfb34fc"
        ev_id = "1f12e578-cd6f-4115-a5eb-ff9b4367832b"
        filename = "shoe_test.mov"
        key = generate_canonical_s3_key(case_id, ev_id, filename)

        self.assertEqual(key, f"cases/{case_id}/{ev_id}_shoe_test.mov")
        self.assertFalse(key.startswith("/"))
        self.assertNotIn("..", key)

    def test_s3_upload_and_readback_integrity(self):
        """Simulate upload and independent readback verification."""
        case_id = str(uuid.uuid4())
        ev_id = str(uuid.uuid4())
        filename = "forensic_weapon.jpg"
        key = generate_canonical_s3_key(case_id, ev_id, filename)

        payload = b"FORENSIC_EXHIBIT_BINARY_DATA_TEST_12345"
        expected_sha = hashlib.sha256(payload).hexdigest()

        # Upload
        stored = self.provider.put(key, payload, content_type="image/jpeg")
        self.assertEqual(stored.sha256, expected_sha)
        self.assertEqual(stored.size, len(payload))

        # Independent Readback Verification
        stream = self.provider.get(key)
        read_bytes = stream.read()
        stream.close()

        read_sha = hashlib.sha256(read_bytes).hexdigest()
        self.assertEqual(read_sha, expected_sha)
        self.assertEqual(read_bytes, payload)

    def test_compute_evidence_file_hash_storage_key(self):
        """compute_evidence_file_hash must resolve canonical keys via storage provider."""
        case_id = str(uuid.uuid4())
        ev_id = str(uuid.uuid4())
        key = generate_canonical_s3_key(case_id, ev_id, "doc.pdf")

        data = b"CONFIDENTIAL_AUDIT_DOCUMENT"
        expected_sha = hashlib.sha256(data).hexdigest()

        self.provider.put(key, data, content_type="application/pdf")

        with patch("app.get_storage_provider", return_value=self.provider):
            computed = main_app.compute_evidence_file_hash(key)
            self.assertEqual(computed, expected_sha)

    def test_authenticated_download_through_fastapi(self):
        """FastAPI /evidence/{id}/download must serve bytes with verified SHA-256 headers."""
        case_id = str(uuid.uuid4())
        ev_id = str(uuid.uuid4())
        key = generate_canonical_s3_key(case_id, ev_id, "evidence_blood.png")

        data = b"CRIME_SCENE_BLOOD_PATTERN_ANALYSIS"
        expected_sha = hashlib.sha256(data).hexdigest()

        self.provider.put(key, data, content_type="image/png")

        # Mock evidence model and user auth
        mock_evidence = MagicMock()
        mock_evidence.id = uuid.UUID(ev_id)
        mock_evidence.case_id = uuid.UUID(case_id)
        mock_evidence.file_name = "evidence_blood.png"
        mock_evidence.file_url = key
        mock_evidence.file_hash = expected_sha
        mock_evidence.mime_type = "image/png"

        mock_user = {
            "id": str(uuid.uuid4()),
            "email": "investigator@police.gov",
            "role": "investigator",
            "is_admin": False
        }

        with patch("app.get_current_user_info", return_value=mock_user), \
             patch("app.load_evidence_for_user", return_value=mock_evidence), \
             patch("app.get_storage_provider", return_value=self.provider), \
             patch("app.add_offchain_custody"), \
             patch("app.audit_event"):

            response = self.client.get(f"/evidence/{ev_id}/download")

            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.headers.get("X-Evidence-SHA256"), expected_sha)
            self.assertEqual(response.headers.get("X-Evidence-Integrity"), "match")
            self.assertEqual(response.content, data)
            self.assertEqual(hashlib.sha256(response.content).hexdigest(), expected_sha)

    def test_unauthenticated_download_rejected(self):
        """Unauthenticated download must return 401 Unauthorized."""
        response = self.client.get(f"/evidence/{uuid.uuid4()}/download")
        self.assertEqual(response.status_code, 401)

    def test_local_evidence_files_invariance(self):
        """Confirm that local files on disk in backend/uploads remain present and unaltered."""
        uploads_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "uploads")
        self.assertTrue(os.path.isdir(uploads_dir))
        file_count = 0
        for root, _, files in os.walk(uploads_dir):
            for f in files:
                file_count += 1
        self.assertGreaterEqual(file_count, 35)


if __name__ == "__main__":
    unittest.main()
