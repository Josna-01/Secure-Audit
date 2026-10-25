"""
Unit Tests for Storage Gateway and Dry-Run Inventory Logic (Phase 2A)

Tests:
1. LocalStorageProvider:
   - Path traversal rejection (../, absolute paths)
   - Put / get round-trip with cryptographic hash and byte verification
   - Refusal of duplicate keys (KeyAlreadyExistsError)
   - Strict absence of delete / unlink / remove methods (append-only contract)
   - stat() and exists() contract verification
2. Dry-run classification and resolution:
   - URL classification (localhost, supabase, other, null)
   - Safe local path resolution and traversal rejection
   - Dry-run inventory evaluation on mock rows and temp fixtures
"""

import io
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from services.storage_gateway import (
    LocalStorageProvider,
    StorageProvider,
    StoredObject,
    PathTraversalError,
    KeyAlreadyExistsError,
    ObjectNotFoundError,
    build_storage_key,
    sanitize_filename,
    storage_diagnostics,
    validate_storage_configuration,
    StorageConfigurationError,
)
from scripts.storage_migration_dryrun import (
    classify_url,
    resolve_local_path,
    compute_sha256,
)


class TestStorageGateway(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="secure_audit_gateway_test_")
        self.provider = LocalStorageProvider(root_dir=self.test_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_no_delete_method_exists(self):
        """CRITICAL: Ensure no deletion methods exist on provider or interface."""
        for attr in ("delete", "remove", "unlink", "drop", "purge", "destroy"):
            self.assertFalse(
                hasattr(self.provider, attr),
                f"LocalStorageProvider must NOT define '{attr}'",
            )
            self.assertFalse(
                hasattr(StorageProvider, attr),
                f"StorageProvider interface must NOT define '{attr}'",
            )

    def test_put_get_roundtrip(self):
        """Put binary stream and get back identical bytes and SHA-256."""
        case_id = "7ec11592-1eaf-47a8-93f8-9061819a5949"
        key = build_storage_key(case_id, "evidence_sample.png")
        payload = b"FORENSIC_EVIDENCE_PAYLOAD_BYTES_987654321"

        stored = self.provider.put(key, io.BytesIO(payload), content_type="image/png")

        self.assertEqual(stored.key, key)
        self.assertEqual(stored.size, len(payload))
        self.assertEqual(stored.content_type, "image/png")
        self.assertTrue(self.provider.exists(key))

        stat_info = self.provider.stat(key)
        self.assertEqual(stat_info.size, len(payload))
        self.assertEqual(stat_info.sha256, stored.sha256)

        with self.provider.get(key) as stream:
            retrieved_data = stream.read()
        self.assertEqual(retrieved_data, payload)

    def test_put_refuses_existing_key(self):
        """Put must raise KeyAlreadyExistsError if key already exists (atomic refusal)."""
        key = "cases/case-1/unique_file.txt"
        self.provider.put(key, b"FIRST_WRITE")

        with self.assertRaises(KeyAlreadyExistsError):
            self.provider.put(key, b"SECOND_WRITE_ATTEMPT")

    def test_path_traversal_rejection(self):
        """LocalStorageProvider must reject any key attempting to escape root."""
        traversal_keys = [
            "../secret.txt",
            "cases/../../secret.txt",
            "/etc/passwd",
            "C:\\Windows\\system.ini",
            "cases/case-1/../../../etc/shadow",
            "..\\..\\sensitive.dat",
        ]
        for bad_key in traversal_keys:
            with self.subTest(key=bad_key):
                with self.assertRaises((PathTraversalError, ValueError)):
                    self.provider.put(bad_key, b"malicious")

                with self.assertRaises((PathTraversalError, ValueError)):
                    self.provider.get(bad_key)

                with self.assertRaises((PathTraversalError, ValueError)):
                    self.provider.exists(bad_key)

    def test_stat_nonexistent_key(self):
        """Stat raises ObjectNotFoundError for nonexistent keys."""
        with self.assertRaises(ObjectNotFoundError):
            self.provider.stat("cases/nonexistent/missing.bin")

    def test_filename_sanitization(self):
        """Verify sanitize_filename cleans risky paths and characters."""
        self.assertEqual(sanitize_filename("../../etc/passwd"), "passwd")
        self.assertEqual(sanitize_filename("my#file$*&.txt"), "my_file___.txt")
        self.assertEqual(sanitize_filename(""), "unnamed_evidence")


class TestStorageConfiguration(unittest.TestCase):
    def test_local_mode_requires_no_cloud_configuration(self):
        info = validate_storage_configuration("local", environ={"USE_LOCAL_STORAGE": "true"})
        self.assertEqual(info["active_backend"], "local")
        self.assertEqual(info["storage_mode"], "local")
        self.assertTrue(info["local_storage_enabled"])

    def test_cloud_mode_missing_settings_is_actionable_and_secret_safe(self):
        secret = "should-never-appear-in-an-error"
        with self.assertRaises(StorageConfigurationError) as raised:
            validate_storage_configuration("s3", environ={"S3_SECRET_ACCESS_KEY": secret})
        message = str(raised.exception)
        self.assertIn("S3_BUCKET_NAME", message)
        self.assertIn("S3_ENDPOINT_URL", message)
        self.assertIn("S3_ACCESS_KEY_ID", message)
        self.assertNotIn(secret, message)

    def test_cloud_mode_rejects_unsafe_endpoint_without_echoing_it(self):
        endpoint = "http://key:secret@unsafe.example.invalid/?token=secret"
        env = {
            "S3_BUCKET_NAME": "private-bucket",
            "S3_ENDPOINT_URL": endpoint,
            "S3_REGION": "auto",
            "S3_ACCESS_KEY_ID": "access-key",
            "S3_SECRET_ACCESS_KEY": "secret-key",
        }
        with self.assertRaises(StorageConfigurationError) as raised:
            validate_storage_configuration("s3", environ=env)
        self.assertIn("HTTPS", str(raised.exception))
        self.assertNotIn(endpoint, str(raised.exception))

    def test_diagnostics_reveal_presence_not_values(self):
        env = {
            "STORAGE_BACKEND": "s3",
            "USE_LOCAL_STORAGE": "false",
            "S3_BUCKET_NAME": "private-bucket-name",
            "S3_ENDPOINT_URL": "https://account-id.r2.cloudflarestorage.com",
            "S3_REGION": "auto",
            "S3_ACCESS_KEY_ID": "access-key-value",
            "S3_SECRET_ACCESS_KEY": "secret-key-value",
        }
        info = storage_diagnostics(environ=env)
        self.assertEqual(info["active_backend"], "s3")
        self.assertTrue(info["r2_endpoint_detected"])
        self.assertTrue(all(info["required_settings"].values()))
        rendered = str(info)
        for value in (
            env["S3_BUCKET_NAME"],
            env["S3_ENDPOINT_URL"],
            env["S3_ACCESS_KEY_ID"],
            env["S3_SECRET_ACCESS_KEY"],
        ):
            self.assertNotIn(value, rendered)





class TestDryRunClassificationAndResolution(unittest.TestCase):
    def setUp(self):
        self.temp_uploads = tempfile.mkdtemp(prefix="test_uploads_")
        self.uploads_path = Path(self.temp_uploads)

    def tearDown(self):
        shutil.rmtree(self.temp_uploads, ignore_errors=True)

    def test_classify_url(self):
        """Test URL classification logic."""
        self.assertEqual(classify_url(None), "null")
        self.assertEqual(classify_url(""), "null")
        self.assertEqual(classify_url("   "), "null")
        self.assertEqual(
            classify_url("http://localhost:8000/uploads/cases/1/file.txt"),
            "localhost",
        )
        self.assertEqual(
            classify_url("http://127.0.0.1:8000/uploads/cases/1/file.txt"),
            "localhost",
        )
        self.assertEqual(classify_url("/uploads/cases/1/file.txt"), "localhost")
        self.assertEqual(
            classify_url("https://taskxnlhzeaaddnxqxbw.supabase.co/storage/v1/object/public/evidence/f.txt"),
            "supabase",
        )
        self.assertEqual(classify_url("https://s3.amazonaws.com/bucket/f.txt"), "other")

    def test_resolve_local_path_safe(self):
        """Test valid local path resolution."""
        test_file = self.uploads_path / "cases" / "case-1" / "doc.pdf"
        test_file.parent.mkdir(parents=True, exist_ok=True)
        test_file.write_bytes(b"TEST_PDF")

        url = "http://localhost:8000/uploads/cases/case-1/doc.pdf"
        resolved, err = resolve_local_path(url, self.uploads_path)
        self.assertIsNone(err)
        self.assertEqual(resolved, test_file.resolve())

    def test_resolve_local_path_traversal(self):
        """Test rejection of traversal in URLs."""
        url = "http://localhost:8000/uploads/../../windows/system32/cmd.exe"
        resolved, err = resolve_local_path(url, self.uploads_path)
        self.assertIsNone(resolved)
        self.assertIn("traversal", (err or "").lower())


if __name__ == "__main__":
    unittest.main()
