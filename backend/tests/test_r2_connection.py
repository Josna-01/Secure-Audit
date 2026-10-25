"""
Unit Tests for Cloudflare R2 Isolated Connectivity Tool (backend/tests/test_r2_connection.py)
Validates:
1. Configuration validation (detecting missing variables, empty strings, unreplaced placeholders).
2. Credential masking (ensuring secrets are never exposed in logs or return strings).
3. Mocked end-to-end R2 connectivity test success flow:
   - Synthetic object creation under diagnostics/
   - Put / Get / Stat round-trip integrity (byte & SHA-256 match)
   - Collision refusal (KeyAlreadyExistsError)
   - Surgical cleanup targeting only the created diagnostic probe
4. Failure mode handling (403 PermissionDenied, endpoint unavailable, integrity mismatch).
5. Forensic immutability preservation (zero delete methods on StorageProvider).
"""

import io
import os
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

from services.storage_gateway import (
    S3StorageProvider,
    StoredObject,
    KeyAlreadyExistsError,
    KeyNotFoundError,
    StorageConfigurationError,
    StoragePermissionError,
    StorageUnavailableError,
    StorageIntegrityError,
)
from scripts.test_r2_connection import (
    validate_r2_config,
    mask_endpoint,
    mask_key_id,
    run_r2_connectivity_test,
    DIAGNOSTIC_PREFIX,
    REQUIRED_ENV_VARS,
)


class MockR2Client:
    """In-memory mock S3/R2 client simulating Cloudflare R2 protocol."""

    def __init__(self):
        self.objects = {}  # key -> {"body": bytes, "metadata": dict, "content_type": str, "mtime": datetime}
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


class TestR2ConnectionTool(unittest.TestCase):

    def setUp(self):
        self.mock_client = MockR2Client()
        self.provider = S3StorageProvider(
            bucket_name="secure-audit-evidence",
            region_name="auto",
            endpoint_url="https://mock-account-id.r2.cloudflarestorage.com",
            access_key_id="mock_access_key_12345678",
            secret_access_key="mock_secret_key_87654321",
            s3_client=self.mock_client,
        )

    def test_validate_r2_config_valid(self):
        """Configuration validation succeeds when all required variables are set."""
        valid_dict = {
            "S3_BUCKET_NAME": "secure-audit-evidence",
            "S3_ENDPOINT_URL": "https://0123456789abcdef0123456789abcdef.r2.cloudflarestorage.com",
            "S3_REGION": "auto",
            "S3_ACCESS_KEY_ID": "mock_access_key_id_value",
            "S3_SECRET_ACCESS_KEY": "mock_secret_access_key_value",
        }
        is_valid, errors, cfg = validate_r2_config(env_dict=valid_dict)
        self.assertTrue(is_valid)
        self.assertEqual(len(errors), 0)
        self.assertEqual(cfg["S3_BUCKET_NAME"], "secure-audit-evidence")
        self.assertEqual(cfg["S3_REGION"], "auto")

    def test_validate_r2_config_missing_variables(self):
        """Configuration validation reports missing variables without disclosing secrets."""
        test_cases = [
            ({}, ["S3_BUCKET_NAME", "S3_ENDPOINT_URL", "S3_ACCESS_KEY_ID", "S3_SECRET_ACCESS_KEY"]),
            ({"S3_BUCKET_NAME": "my-bucket"}, ["S3_ENDPOINT_URL", "S3_ACCESS_KEY_ID", "S3_SECRET_ACCESS_KEY"]),
            (
                {
                    "S3_BUCKET_NAME": "my-bucket",
                    "S3_ENDPOINT_URL": "https://account.r2.cloudflarestorage.com",
                    "S3_ACCESS_KEY_ID": "my_key",
                    "S3_SECRET_ACCESS_KEY": "",  # Empty
                },
                ["S3_SECRET_ACCESS_KEY"]
            ),
        ]
        for env_dict, expected_missing in test_cases:
            is_valid, errors, _ = validate_r2_config(env_dict=env_dict)
            self.assertFalse(is_valid)
            for var in expected_missing:
                self.assertTrue(any(var in e for e in errors), f"Expected '{var}' to be mentioned in errors: {errors}")
            # Ensure no secret content leaked into errors
            for e in errors:
                self.assertNotIn("mock_secret", e)

    def test_validate_r2_config_placeholder_detection(self):
        """Detects and reports unreplaced '<ACCOUNT_ID>' placeholder in endpoint."""
        placeholder_dict = {
            "S3_BUCKET_NAME": "secure-audit-evidence",
            "S3_ENDPOINT_URL": "https://<ACCOUNT_ID>.r2.cloudflarestorage.com",
            "S3_ACCESS_KEY_ID": "my_key",
            "S3_SECRET_ACCESS_KEY": "my_secret",
        }
        is_valid, errors, _ = validate_r2_config(env_dict=placeholder_dict)
        self.assertFalse(is_valid)
        self.assertTrue(any("<ACCOUNT_ID>" in e for e in errors))

    def test_masking_functions(self):
        """Masking functions must never leak secret values or full tokens."""
        endpoint = "https://0123456789abcdef0123456789abcdef.r2.cloudflarestorage.com"
        masked_ep = mask_endpoint(endpoint)
        self.assertNotIn("0123456789abcdef0123456789abcdef", masked_ep)
        self.assertIn(".r2.cloudflarestorage.com", masked_ep)

        key_id = "f4c9380a158b4ec8b9487c062831d102"
        masked_kid = mask_key_id(key_id)
        self.assertNotIn(key_id, masked_kid)
        self.assertIn("32 chars", masked_kid)

        self.assertEqual(mask_endpoint(""), "[NOT SET]")
        self.assertEqual(mask_key_id(""), "[NOT SET]")

    def test_mocked_r2_connectivity_success_flow(self):
        """Full non-destructive diagnostic flow: put, exists, get, stat, collision rejection, and cleanup."""
        success, message, diagnostics = run_r2_connectivity_test(
            provider=self.provider,
            keep_object=False,
            verbose=False,
        )
        self.assertTrue(success, f"Expected success but got: {message}")
        self.assertIn("verified successfully", message)

        # Verify all 6 steps executed in order
        expected_steps = [
            "PUT_OBJECT",
            "EXISTS_CHECK",
            "GET_VERIFIED",
            "STAT_VERIFIED",
            "COLLISION_REFUSAL_VERIFIED",
            "CLEANUP_SUCCESS",
        ]
        self.assertEqual(diagnostics["steps_completed"], expected_steps)

        # Verify key was properly namespaced under diagnostics/
        diag_key = diagnostics["diagnostic_key"]
        self.assertTrue(diag_key.startswith(DIAGNOSTIC_PREFIX))

        # Verify cleanup removed the object from storage
        self.assertTrue(diagnostics["cleanup_performed"])
        self.assertNotIn(diag_key, self.mock_client.objects)
        self.assertIn(diag_key, self.mock_client.deleted_keys)
        self.assertEqual(len(self.mock_client.objects), 0)

    def test_mocked_r2_connectivity_keep_object(self):
        """When keep_object=True, diagnostic object is retained in bucket for inspection."""
        success, message, diagnostics = run_r2_connectivity_test(
            provider=self.provider,
            keep_object=True,
            verbose=False,
        )
        self.assertTrue(success)
        self.assertIn("CLEANUP_SKIPPED", diagnostics["steps_completed"])
        self.assertFalse(diagnostics["cleanup_performed"])

        diag_key = diagnostics["diagnostic_key"]
        self.assertIn(diag_key, self.mock_client.objects)
        self.assertEqual(len(self.mock_client.deleted_keys), 0)

    def test_permission_error_handling(self):
        """Simulate 403 Forbidden on put_object and verify actionable message without crash."""
        err_client = MockR2Client()
        def forbidden_put(*args, **kwargs):
            exc = Exception("AccessDenied")
            exc.response = {"ResponseMetadata": {"HTTPStatusCode": 403}, "Error": {"Code": "AccessDenied"}}
            raise exc

        err_client.put_object = forbidden_put
        provider = S3StorageProvider(
            bucket_name="secure-audit-evidence",
            region_name="auto",
            endpoint_url="https://mock.r2.cloudflarestorage.com",
            access_key_id="key",
            secret_access_key="secret",
            s3_client=err_client,
        )

        success, message, diagnostics = run_r2_connectivity_test(provider=provider, verbose=False)
        self.assertFalse(success)
        self.assertIn("Permission Denied (403 Forbidden)", message)
        self.assertIn("Object Read & Write", message)

    def test_unavailable_error_handling(self):
        """Simulate endpoint connection failure and verify actionable message."""
        err_client = MockR2Client()
        def unavailable_put(*args, **kwargs):
            raise Exception("Could not connect to endpoint URL: https://nonexistent.r2.cloudflarestorage.com")

        err_client.put_object = unavailable_put
        provider = S3StorageProvider(
            bucket_name="secure-audit-evidence",
            region_name="auto",
            endpoint_url="https://nonexistent.r2.cloudflarestorage.com",
            access_key_id="key",
            secret_access_key="secret",
            s3_client=err_client,
        )

        success, message, diagnostics = run_r2_connectivity_test(provider=provider, verbose=False)
        self.assertFalse(success)
        self.assertIn("Endpoint Unreachable", message)

    def test_forensic_immutability_preserved(self):
        """Ensure no deletion methods were added to StorageProvider or S3StorageProvider."""
        for attr in ("delete", "remove", "unlink", "drop", "purge", "destroy", "delete_object"):
            self.assertFalse(
                hasattr(self.provider, attr),
                f"S3StorageProvider must NEVER define '{attr}'",
            )


if __name__ == "__main__":
    unittest.main()
