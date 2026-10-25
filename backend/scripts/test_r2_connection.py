#!/usr/bin/env python3
"""
Secure Audit — Isolated Cloudflare R2 Connectivity & Integrity Verification Tool
Location: backend/scripts/test_r2_connection.py

NON-DESTRUCTIVE DIAGNOSTIC GUARANTEES:
1. Zero Production Impact: Leaves STORAGE_BACKEND=local and local files unchanged.
2. Isolated Diagnostic Namespace: Only writes to unique 'diagnostics/r2_connectivity_test_*' keys.
3. Cryptographic Verification: Computes and validates SHA-256 for put, get, and stat round-trips.
4. Forensic Immutability Check: Verifies collision rejection (KeyAlreadyExistsError).
5. Surgical Cleanup: Only removes the exact synthetic diagnostic object created in this run.
   Does not add deletion methods to the append-only StorageProvider interface.
6. Zero Credential Exposure: Never logs or prints secrets, passwords, or full access keys.
"""

import os
import sys
import io
import uuid
import hashlib
import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

# Ensure backend root is on sys.path
SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent
PROJECT_ROOT = BACKEND_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

from services.storage_gateway import (
    S3StorageProvider,
    StoredObject,
    KeyAlreadyExistsError,
    KeyNotFoundError,
    StorageError,
    StorageConfigurationError,
    StoragePermissionError,
    StorageUnavailableError,
    StorageIntegrityError,
    validate_storage_key,
)

DIAGNOSTIC_PREFIX = "diagnostics/r2_connectivity_test_"
REQUIRED_ENV_VARS = [
    "S3_BUCKET_NAME",
    "S3_ENDPOINT_URL",
    "S3_ACCESS_KEY_ID",
    "S3_SECRET_ACCESS_KEY",
]


def mask_endpoint(endpoint: Optional[str]) -> str:
    """Mask account identifier within endpoint URL for safe display."""
    if not endpoint:
        return "[NOT SET]"
    if "<ACCOUNT_ID>" in endpoint:
        return endpoint  # Show unreplaced placeholder indicator
    try:
        from urllib.parse import urlparse
        parsed = urlparse(endpoint)
        host = parsed.netloc or parsed.path
        parts = host.split(".")
        if len(parts) >= 3:
            account_id = parts[0]
            if len(account_id) > 8:
                masked_account = f"{account_id[:4]}...{account_id[-4:]}"
            else:
                masked_account = "****"
            masked_host = ".".join([masked_account] + parts[1:])
            return f"{parsed.scheme}://{masked_host}"
        return f"{parsed.scheme}://{host}"
    except Exception:
        return "https://***.r2.cloudflarestorage.com"


def mask_key_id(key_id: Optional[str]) -> str:
    """Mask Access Key ID showing only character count and boundary bytes."""
    if not key_id:
        return "[NOT SET]"
    clean = str(key_id).strip()
    if len(clean) <= 8:
        return f"[CONFIGURED ({len(clean)} chars)]"
    return f"{clean[:4]}...{clean[-4:]} ({len(clean)} chars)"


def validate_r2_config(
    env_path: Optional[Path] = None,
    env_dict: Optional[Dict[str, str]] = None
) -> Tuple[bool, List[str], Dict[str, str]]:
    """
    Validate that required Cloudflare R2 environment variables are present and non-empty.
    Returns (is_valid, list_of_error_messages, config_dict).
    Guarantees zero credential exposure in error messages.
    """
    config: Dict[str, str] = {}
    errors: List[str] = []

    if env_dict is not None:
        source = env_dict
    else:
        target_env = env_path or (BACKEND_DIR / ".env")
        if target_env.is_file() and load_dotenv:
            load_dotenv(dotenv_path=target_env, override=False)
        source = os.environ

    for var in REQUIRED_ENV_VARS:
        val = (source.get(var) or "").strip()
        config[var] = val
        if not val:
            errors.append(f"Missing required environment variable: '{var}'")

    config["S3_REGION"] = (source.get("S3_REGION") or "auto").strip()
    config["S3_SERVER_SIDE_ENCRYPTION"] = (source.get("S3_SERVER_SIDE_ENCRYPTION") or "").strip()

    endpoint = config.get("S3_ENDPOINT_URL", "")
    if endpoint and ("<ACCOUNT_ID>" in endpoint or "<" in endpoint or ">" in endpoint):
        errors.append(
            "S3_ENDPOINT_URL contains an unreplaced placeholder ('<ACCOUNT_ID>'). "
            "Please replace it with your 32-character Cloudflare Account ID."
        )

    return (len(errors) == 0, errors, config)


def run_r2_connectivity_test(
    provider: Optional[S3StorageProvider] = None,
    s3_client: Optional[Any] = None,
    env_path: Optional[Path] = None,
    keep_object: bool = False,
    verbose: bool = True
) -> Tuple[bool, str, Dict[str, Any]]:
    """
    Execute non-destructive R2 connectivity, round-trip integrity, and metadata verification.
    Returns (success: bool, message: str, diagnostics: dict).
    """
    diagnostics: Dict[str, Any] = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "steps_completed": [],
        "errors": [],
        "cleanup_performed": False,
    }

    # 1. Validate configuration if provider not directly supplied
    if provider is None:
        is_valid, errors, cfg = validate_r2_config(env_path=env_path)
        if not is_valid:
            error_summary = "R2 Configuration Incomplete:\n" + "\n".join(f"  - {e}" for e in errors)
            diagnostics["errors"] = errors
            if verbose:
                print("=" * 80)
                print("SECURE AUDIT — CLOUDFLARE R2 ISOLATED CONNECTIVITY VERIFICATION")
                print("=" * 80)
                print(f"[!] {error_summary}\n")
                print("Action Required: Please populate the missing variables in backend/.env.")
                print("Keep STORAGE_BACKEND=local until this verification passes.\n")
            return False, error_summary, diagnostics

        try:
            provider = S3StorageProvider(
                bucket_name=cfg["S3_BUCKET_NAME"],
                region_name=cfg["S3_REGION"],
                endpoint_url=cfg["S3_ENDPOINT_URL"],
                access_key_id=cfg["S3_ACCESS_KEY_ID"],
                secret_access_key=cfg["S3_SECRET_ACCESS_KEY"],
                server_side_encryption=cfg["S3_SERVER_SIDE_ENCRYPTION"] or None,
                s3_client=s3_client
            )
        except Exception as exc:
            msg = f"Failed to initialize S3StorageProvider: {exc}"
            diagnostics["errors"].append(msg)
            if verbose:
                print(f"[ERROR] {msg}")
            return False, msg, diagnostics

    # Safe display header
    if verbose:
        print("=" * 80)
        print("SECURE AUDIT — CLOUDFLARE R2 ISOLATED CONNECTIVITY VERIFICATION")
        print("=" * 80)
        print(f"Timestamp:          {diagnostics['timestamp']}")
        print(f"Target Bucket:      {provider.bucket_name}")
        print(f"Endpoint URL:       {mask_endpoint(provider.endpoint_url)}")
        print(f"Region:             {provider.region_name}")
        print(f"Access Key ID:      {mask_key_id(provider.access_key_id)}")
        print(f"Secret Access Key:  {'[CONFIGURED]' if provider.secret_access_key else '[NOT SET]'}")
        print(f"Local Fallback:     PRESERVED (active runtime remains STORAGE_BACKEND=local)")
        print("=" * 80)

    # 2. Build synthetic diagnostic probe
    probe_id = uuid.uuid4().hex[:12]
    now_ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    diagnostic_key = f"{DIAGNOSTIC_PREFIX}{now_ts}_{probe_id}.txt"
    diagnostics["diagnostic_key"] = diagnostic_key

    payload_text = (
        f"SECURE AUDIT R2 CONNECTIVITY & INTEGRITY DIAGNOSTIC PROBE\n"
        f"Probe ID:         {probe_id}\n"
        f"Timestamp:        {diagnostics['timestamp']}\n"
        f"Target Bucket:    {provider.bucket_name}\n"
        f"Security Level:   Append-Only Diagnostic Verification\n"
        f"Cryptographic:    SHA-256 Stream Verified\n"
    )
    payload_bytes = payload_text.encode("utf-8")
    expected_size = len(payload_bytes)
    expected_sha256 = hashlib.sha256(payload_bytes).hexdigest().lower()
    diagnostics["expected_sha256"] = expected_sha256
    diagnostics["expected_size"] = expected_size

    # Strict key sanity check
    validate_storage_key(diagnostic_key)

    try:
        # Step 1: Put synthetic diagnostic object
        if verbose:
            print(f"[1/6] Uploading synthetic diagnostic probe ({expected_size} bytes)...")
            print(f"      Key: {diagnostic_key}")

        stored = provider.put(diagnostic_key, payload_bytes, content_type="text/plain; charset=utf-8")

        if stored.key != diagnostic_key:
            raise StorageIntegrityError(f"Returned key mismatch: expected '{diagnostic_key}', got '{stored.key}'")
        if stored.size != expected_size:
            raise StorageIntegrityError(f"Returned size mismatch: expected {expected_size}, got {stored.size}")
        if stored.sha256.lower() != expected_sha256:
            raise StorageIntegrityError(f"Returned SHA-256 mismatch: expected {expected_sha256}, got {stored.sha256}")

        diagnostics["steps_completed"].append("PUT_OBJECT")
        if verbose:
            print(f"      -> Upload OK. Streaming SHA-256: {stored.sha256[:16]}...")

        # Step 2: Verify object existence
        if verbose:
            print("[2/6] Verifying object existence in bucket...")
        if not provider.exists(diagnostic_key):
            raise StorageError(f"Object exists() returned False immediately after successful put for key '{diagnostic_key}'")

        diagnostics["steps_completed"].append("EXISTS_CHECK")
        if verbose:
            print("      -> Object presence confirmed in bucket.")

        # Step 3: Read back object and verify byte-for-byte SHA-256 match
        if verbose:
            print("[3/6] Reading back diagnostic stream...")
        stream = provider.get(diagnostic_key)
        downloaded_bytes = stream.read()
        if hasattr(stream, "close"):
            stream.close()

        if downloaded_bytes != payload_bytes:
            raise StorageIntegrityError("Downloaded content does not match uploaded bytes byte-for-byte.")

        downloaded_sha256 = hashlib.sha256(downloaded_bytes).hexdigest().lower()
        if downloaded_sha256 != expected_sha256:
            raise StorageIntegrityError(f"Downloaded SHA-256 mismatch: expected {expected_sha256}, got {downloaded_sha256}")

        diagnostics["steps_completed"].append("GET_VERIFIED")
        if verbose:
            print(f"      -> Download OK. Read-back SHA-256 matched: {downloaded_sha256[:16]}... ({len(downloaded_bytes)} bytes)")

        # Step 4: Verify metadata and stat() retrieval
        if verbose:
            print("[4/6] Verifying object metadata and stat() retrieval...")
        stat_obj = provider.stat(diagnostic_key)

        if stat_obj.size != expected_size:
            raise StorageIntegrityError(f"stat() size mismatch: expected {expected_size}, got {stat_obj.size}")
        if stat_obj.sha256.lower() != expected_sha256:
            raise StorageIntegrityError(f"stat() SHA-256 mismatch: expected {expected_sha256}, got {stat_obj.sha256}")

        diagnostics["steps_completed"].append("STAT_VERIFIED")
        if verbose:
            print(f"      -> stat() OK. Size: {stat_obj.size} bytes, SHA-256: {stat_obj.sha256[:16]}...")

        # Step 5: Verify collision refusal (forensic immutability)
        if verbose:
            print("[5/6] Verifying collision refusal (immutability check)...")
        collision_detected = False
        try:
            provider.put(diagnostic_key, b"ILLEGAL_OVERWRITE_ATTEMPT")
        except KeyAlreadyExistsError:
            collision_detected = True
        except Exception as collision_err:
            raise StorageError(f"Unexpected exception during collision test: {collision_err}") from collision_err

        if not collision_detected:
            raise StorageIntegrityError("CRITICAL: Provider permitted overwrite of an existing key! Immutability violated.")

        diagnostics["steps_completed"].append("COLLISION_REFUSAL_VERIFIED")
        if verbose:
            print("      -> Collision refusal confirmed. Duplicate put() was strictly rejected.")

        # Step 6: Surgical diagnostic cleanup
        if keep_object:
            if verbose:
                print(f"[6/6] Skipped cleanup (--keep-object requested). Object remains at '{diagnostic_key}'.")
            diagnostics["steps_completed"].append("CLEANUP_SKIPPED")
        else:
            if verbose:
                print(f"[6/6] Cleaning up isolated diagnostic probe...")

            # Strict security assertion: Only delete the diagnostic key created by this run
            if not diagnostic_key.startswith(DIAGNOSTIC_PREFIX):
                raise ValueError(f"Safety violation: refused to delete key outside diagnostic prefix: {diagnostic_key}")

            # Low-level deletion on boto3 client (StorageProvider remains append-only without delete methods)
            provider._client.delete_object(Bucket=provider.bucket_name, Key=diagnostic_key)

            if provider.exists(diagnostic_key):
                raise StorageError(f"Diagnostic probe '{diagnostic_key}' still exists after deletion attempt.")

            diagnostics["cleanup_performed"] = True
            diagnostics["steps_completed"].append("CLEANUP_SUCCESS")
            if verbose:
                print("      -> Diagnostic probe removed cleanly. Zero leftover files.")

        if verbose:
            print("=" * 80)
            print("[PASS] Cloudflare R2 connectivity, authentication, and cryptographic integrity verified successfully!")
            print("=" * 80)

        return True, "R2 connectivity and cryptographic integrity verified successfully.", diagnostics

    except StoragePermissionError as e:
        msg = (
            f"Permission Denied (403 Forbidden). Verify that your R2 API Token has 'Object Read & Write' "
            f"permissions for bucket '{provider.bucket_name}'. Error: {e}"
        )
        diagnostics["errors"].append(msg)
        if verbose:
            print(f"\n[FAIL] {msg}\n")
        return False, msg, diagnostics

    except StorageUnavailableError as e:
        msg = (
            f"Cloudflare R2 Endpoint Unreachable. Verify your internet connection and that S3_ENDPOINT_URL "
            f"matches 'https://<ACCOUNT_ID>.r2.cloudflarestorage.com'. Error: {e}"
        )
        diagnostics["errors"].append(msg)
        if verbose:
            print(f"\n[FAIL] {msg}\n")
        return False, msg, diagnostics

    except StorageConfigurationError as e:
        msg = f"Configuration error: {e}"
        diagnostics["errors"].append(msg)
        if verbose:
            print(f"\n[FAIL] {msg}\n")
        return False, msg, diagnostics

    except Exception as e:
        msg = f"Unexpected failure during R2 verification: {e}"
        diagnostics["errors"].append(msg)
        if verbose:
            print(f"\n[FAIL] {msg}\n")
        return False, msg, diagnostics

    finally:
        # Emergency cleanup attempt if test crashed halfway through and object wasn't cleaned up
        if not keep_object and not diagnostics["cleanup_performed"] and "PUT_OBJECT" in diagnostics["steps_completed"]:
            try:
                if diagnostic_key.startswith(DIAGNOSTIC_PREFIX):
                    provider._client.delete_object(Bucket=provider.bucket_name, Key=diagnostic_key)
            except Exception:
                pass


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify Cloudflare R2 connectivity, streaming SHA-256, and immutability."
    )
    parser.add_argument(
        "--env-file",
        type=Path,
        default=None,
        help="Optional custom path to .env file (defaults to backend/.env)"
    )
    parser.add_argument(
        "--keep-object",
        action="store_true",
        help="Do not delete the diagnostic probe after test completes (useful for inspecting in Cloudflare Dashboard)"
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress verbose diagnostic output and print status summary only"
    )

    args = parser.parse_args()

    success, message, _ = run_r2_connectivity_test(
        env_path=args.env_file,
        keep_object=args.keep_object,
        verbose=not args.quiet
    )

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
