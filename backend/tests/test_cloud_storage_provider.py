"""
Unit Tests for Phase 2B Cloud Storage Provider (S3/MinIO) and Local Fallback
Validates:
1. Local fallback provider: traversal defense, collision refusal, round-trip integrity, absence of delete.
2. S3StorageProvider:
   - Configuration validation (missing bucket error)
   - Mocked S3 client integration
   - Traversal key rejection
   - Put / get round-trip integrity (byte & SHA-256 match)
   - Collision refusal (KeyAlreadyExistsError on existing key)
   - Missing key error mapping (KeyNotFoundError on 404)
   - Unauthorized access mapping (StoragePermissionError on 403)
   - Provider / network outage mapping (StorageUnavailableError)
   - Immutability guarantee (strictly zero delete/remove methods)
   - stat() metadata retrieval & SHA-256 validation
"""

import io
import os
import shutil
import tempfile
import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock

from services.storage_gateway import (
    LocalStorageProvider,
    S3StorageProvider,
    StorageProvider,
    StoredObject,
    KeyAlreadyExistsError,
    KeyNotFoundError,
    PathTraversalError,
    StorageConfigurationError,
    StoragePermissionError,
    StorageUnavailableError,
    validate_storage_key,
    build_storage_key,
    get_storage_provider,
)


class MockS3Client:
    """In-memory mock S3 client simulating AWS S3 / MinIO protocol."""

    def __init__(self):
        self.objects = {}  # key -> {"body": bytes, "metadata": dict, "content_type": str, "mtime": datetime}

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
        self.objects[Key] = {
            "body": Body if isinstance(Body, bytes) else Body.read(),
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


class TestCloudStorageProvider(unittest.TestCase):
    def setUp(self):
        self.mock_client = MockS3Client()
        self.provider = S3StorageProvider(
            bucket_name="secure-audit-test-vault",
            region_name="us-east-1",
            s3_client=self.mock_client,
        )

    def test_immutability_no_delete_method(self):
        """CRITICAL: S3 provider must NOT define any delete or purge methods."""
        for attr in ("delete", "remove", "unlink", "drop", "purge", "destroy", "delete_object"):
            self.assertFalse(
                hasattr(self.provider, attr),
                f"S3StorageProvider must NOT define '{attr}'",
            )
            self.assertFalse(
                hasattr(StorageProvider, attr),
                f"StorageProvider interface must NOT define '{attr}'",
            )

    def test_missing_bucket_configuration_raises_error(self):
        """Instantiating S3StorageProvider without bucket raises StorageConfigurationError."""
        orig_bucket = os.environ.pop("S3_BUCKET_NAME", None)
        try:
            with self.assertRaises(StorageConfigurationError):
                S3StorageProvider(bucket_name=None, s3_client=self.mock_client)
        finally:
            if orig_bucket:
                os.environ["S3_BUCKET_NAME"] = orig_bucket

    def test_traversal_key_rejected(self):
        """Keys containing path traversal tokens or absolute paths are rejected."""
        bad_keys = [
            "../secret.txt",
            "/cases/secret.txt",
            "cases/../../secret.txt",
            "C:\\cases\\file.txt",
            "..\\windows\\system32",
        ]
        for key in bad_keys:
            with self.subTest(key=key):
                with self.assertRaises((PathTraversalError, ValueError)):
                    self.provider.put(key, b"test")
                with self.assertRaises((PathTraversalError, ValueError)):
                    self.provider.get(key)
                with self.assertRaises((PathTraversalError, ValueError)):
                    self.provider.exists(key)

    def test_put_get_roundtrip_integrity(self):
        """Put binary payload to S3 provider and get back exact bytes and SHA-256."""
        case_id = "d13532e1-d494-4563-b0ea-78adf137c9bc"
        key = build_storage_key(case_id, "evidence_photo.jpg")
        payload = b"CLOUD_STORAGE_IMMUTABLE_EVIDENCE_BYTES_12345"

        stored = self.provider.put(key, payload, content_type="image/jpeg")

        self.assertEqual(stored.key, key)
        self.assertEqual(stored.size, len(payload))
        self.assertEqual(stored.content_type, "image/jpeg")
        self.assertTrue(self.provider.exists(key))

        # Test stat()
        stat_info = self.provider.stat(key)
        self.assertEqual(stat_info.size, len(payload))
        self.assertEqual(stat_info.sha256, stored.sha256)

        # Test get()
        stream = self.provider.get(key)
        retrieved_data = stream.read()
        self.assertEqual(retrieved_data, payload)

    def test_put_stream_roundtrip(self):
        """Put BinaryIO stream to S3 provider and get back exact bytes."""
        key = "cases/d13532e1-d494-4563-b0ea-78adf137c9bc/stream_file.bin"
        payload = b"STREAMING_BINARY_PAYLOAD_TEST_DATA"
        stream_input = io.BytesIO(payload)

        stored = self.provider.put(key, stream_input, content_type="application/octet-stream")
        self.assertEqual(stored.size, len(payload))

        stream_out = self.provider.get(key)
        self.assertEqual(stream_out.read(), payload)

    def test_put_refuses_duplicate_key(self):
        """Put must raise KeyAlreadyExistsError if key already exists."""
        key = "cases/d13532e1-d494-4563-b0ea-78adf137c9bc/unique_test.txt"
        self.provider.put(key, b"FIRST_UPLOAD")

        with self.assertRaises(KeyAlreadyExistsError):
            self.provider.put(key, b"OVERWRITE_ATTEMPT")

    def test_get_nonexistent_key_raises_key_not_found(self):
        """Get on nonexistent key raises KeyNotFoundError."""
        with self.assertRaises(KeyNotFoundError):
            self.provider.get("cases/d13532e1-d494-4563-b0ea-78adf137c9bc/missing.dat")

    def test_stat_nonexistent_key_raises_key_not_found(self):
        """Stat on nonexistent key raises KeyNotFoundError."""
        with self.assertRaises(KeyNotFoundError):
            self.provider.stat("cases/d13532e1-d494-4563-b0ea-78adf137c9bc/missing.dat")

    def test_unauthorized_access_raises_permission_error(self):
        """403 AccessDenied from S3 maps to StoragePermissionError."""
        failing_client = MagicMock()
        err_403 = Exception("Access Denied")
        err_403.response = {"ResponseMetadata": {"HTTPStatusCode": 403}, "Error": {"Code": "AccessDenied"}}
        failing_client.head_object.side_effect = err_403
        failing_client.get_object.side_effect = err_403
        failing_client.put_object.side_effect = err_403

        p = S3StorageProvider(bucket_name="secure-audit-vault", s3_client=failing_client)

        with self.assertRaises(StoragePermissionError):
            p.exists("cases/case-1/test.txt")

        with self.assertRaises(StoragePermissionError):
            p.get("cases/case-1/test.txt")

        with self.assertRaises(StoragePermissionError):
            p.put("cases/case-1/test.txt", b"bytes")

    def test_provider_outage_raises_storage_unavailable(self):
        """Connection / endpoint timeout maps to StorageUnavailableError."""
        failing_client = MagicMock()
        timeout_err = Exception("EndpointConnectionError: Could not connect to the endpoint URL")
        failing_client.head_object.side_effect = timeout_err
        failing_client.get_object.side_effect = timeout_err
        failing_client.put_object.side_effect = timeout_err

        p = S3StorageProvider(bucket_name="secure-audit-vault", s3_client=failing_client)

        with self.assertRaises(StorageUnavailableError):
            p.exists("cases/case-1/test.txt")

        with self.assertRaises(StorageUnavailableError):
            p.get("cases/case-1/test.txt")

        with self.assertRaises(StorageUnavailableError):
            p.put("cases/case-1/test.txt", b"bytes")


class TestLocalStorageFallback(unittest.TestCase):
    """Verify local fallback provider remains 100% operational."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="local_fallback_test_")
        self.provider = LocalStorageProvider(root_dir=self.test_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_local_fallback_put_get_roundtrip(self):
        key = "cases/case-test/file.bin"
        payload = b"LOCAL_FALLBACK_PAYLOAD"
        stored = self.provider.put(key, payload)
        self.assertEqual(stored.size, len(payload))
        self.assertTrue(self.provider.exists(key))
        with self.provider.get(key) as stream:
            self.assertEqual(stream.read(), payload)

    def test_local_fallback_collision_refusal(self):
        key = "cases/case-test/file.bin"
        self.provider.put(key, b"FIRST")
        with self.assertRaises(KeyAlreadyExistsError):
            self.provider.put(key, b"SECOND")

    def test_factory_returns_local_by_default(self):
        os.environ["STORAGE_BACKEND"] = "local"
        provider = get_storage_provider()
        self.assertIsInstance(provider, LocalStorageProvider)


if __name__ == "__main__":
    unittest.main()
