"""
Secure Audit — Storage Gateway Architecture (services/storage_gateway.py)
Provides a hardened, provider-agnostic storage abstraction for evidence exhibits.

Core Architectural Guarantees:
1. Append-Only Immutability: There is NO delete or overwrite method on any provider.
2. Collision & Overwrite Prevention: put() strictly refuses existing keys.
3. Strict Path Traversal Defenses: All relative keys are validated to stay within the canonical namespace.
4. Stream-Hashed Acquisition: SHA-256 is computed directly over the stored bytes upon storage.
5. Zero Public Static Exposure: The gateway provides streams/descriptors only; no static mounts.
6. Enterprise S3 Compatibility: Supports AWS S3, MinIO, Cloudflare R2, Ceph with private ACLs and SSE.
"""

import os
import re
import uuid
import hashlib
from urllib.parse import urlparse
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, BinaryIO, Optional, Union


# RegEx for filename sanitization (strict alphanumeric plus dot, underscore, parens, space, hyphen)
_UNSAFE_FILENAME_CHARS = re.compile(r"[^A-Za-z0-9._() \-]")
_CLOUD_BACKENDS = ("s3", "cloud")
_R2_HOST_SUFFIX = ".r2.cloudflarestorage.com"


class StorageError(Exception):
    """Base exception for all storage gateway operations."""
    pass


class KeyAlreadyExistsError(StorageError):
    """Raised when attempting to put() an object with an existing storage key."""
    pass


class KeyNotFoundError(StorageError):
    """Raised when requesting an object that does not exist."""
    pass


ObjectNotFoundError = KeyNotFoundError


class PathTraversalError(StorageError):
    """Raised when a storage key attempts directory traversal outside the root/namespace."""
    pass


class StorageConfigurationError(StorageError):
    """Raised when storage provider configuration or required dependency is missing."""
    pass


class StoragePermissionError(StorageError):
    """Raised when access to storage is denied (e.g. 403 Forbidden)."""
    pass


class StorageUnavailableError(StorageError):
    """Raised when storage provider is unreachable due to network outage or downtime."""
    pass


class StorageIntegrityError(StorageError):
    """Raised when cryptographic verification detects a hash or byte mismatch."""
    pass


def _configured(value: Optional[str]) -> bool:
    """Return whether an environment value is present without ever returning it."""
    return bool((value or "").strip())


def _is_r2_endpoint(endpoint: Optional[str]) -> bool:
    """Identify a Cloudflare R2 endpoint without exposing its account identifier."""
    try:
        return (urlparse((endpoint or "").strip()).hostname or "").lower().endswith(_R2_HOST_SUFFIX)
    except ValueError:
        return False


def storage_diagnostics(backend: Optional[str] = None, environ: Optional[dict] = None) -> dict[str, Any]:
    """Return non-secret storage configuration state suitable for an admin diagnostic.

    Values, URLs, bucket names and credentials are deliberately omitted. This is
    configuration inspection only; it never contacts a storage provider.
    """
    source = environ if environ is not None else os.environ
    selected = (backend or source.get("STORAGE_BACKEND") or "local").strip().lower()
    cloud = selected in _CLOUD_BACKENDS
    endpoint = source.get("S3_ENDPOINT_URL") or ""
    return {
        "active_backend": selected,
        "storage_mode": "cloud" if cloud else ("local" if selected == "local" else "unsupported"),
        "r2_endpoint_detected": _is_r2_endpoint(endpoint),
        "local_storage_enabled": (source.get("USE_LOCAL_STORAGE") or "false").strip().lower() in ("true", "1", "yes"),
        "required_settings": {
            "S3_BUCKET_NAME": _configured(source.get("S3_BUCKET_NAME")),
            "S3_ENDPOINT_URL": _configured(endpoint),
            "S3_REGION": _configured(source.get("S3_REGION")) or _is_r2_endpoint(endpoint),
            "S3_ACCESS_KEY_ID": _configured(source.get("S3_ACCESS_KEY_ID")),
            "S3_SECRET_ACCESS_KEY": _configured(source.get("S3_SECRET_ACCESS_KEY")),
        },
    }


def validate_storage_configuration(backend: Optional[str] = None, environ: Optional[dict] = None) -> dict[str, Any]:
    """Validate the selected provider without logging or returning secret values.

    Local storage intentionally remains valid with no cloud configuration. Cloud
    configuration is validated before a boto client is created so deployment
    mistakes fail with an actionable error rather than falling back to ambient
    credentials or an unexpected endpoint.
    """
    source = environ if environ is not None else os.environ
    info = storage_diagnostics(backend=backend, environ=source)
    selected = info["active_backend"]
    if selected == "local":
        return info
    if selected not in _CLOUD_BACKENDS:
        raise StorageConfigurationError(
            f"Unsupported storage backend '{selected}'. Supported backends are 'local', 's3', and 'cloud'."
        )

    missing = [name for name, present in info["required_settings"].items() if not present]
    if missing:
        raise StorageConfigurationError(
            "Cloud storage configuration is incomplete. Set: " + ", ".join(missing) + "."
        )

    endpoint = (source.get("S3_ENDPOINT_URL") or "").strip()
    try:
        parsed = urlparse(endpoint)
    except ValueError as exc:
        raise StorageConfigurationError("S3_ENDPOINT_URL must be a valid HTTPS URL.") from exc
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise StorageConfigurationError("S3_ENDPOINT_URL must be an HTTPS endpoint URL without embedded credentials.")
    if any(marker in endpoint for marker in ("<", ">", "your_", "example")):
        raise StorageConfigurationError("S3_ENDPOINT_URL contains a placeholder; configure the Cloudflare R2 S3 endpoint.")
    return info


@dataclass(frozen=True)
class StoredObject:
    """Immutable metadata descriptor of a stored evidence exhibit."""
    key: str
    size: int
    sha256: str
    content_type: Optional[str] = None
    created_at: Optional[datetime] = None
    metadata_sha256: Optional[str] = None


def validate_storage_key(key: str) -> list[str]:
    """
    Validate that key is safe, canonical, and non-traversing.
    Returns the normalized subpath parts or raises PathTraversalError.
    """
    if not key or not isinstance(key, str):
        raise PathTraversalError("Storage key must be a non-empty string.")

    normalized = key.replace("\\", "/").strip()
    if normalized.startswith("/") or os.path.isabs(key) or (len(key) > 1 and key[1] == ":"):
        raise PathTraversalError(f"Absolute paths or drive letters are forbidden in storage keys: {key}")

    parts = normalized.split("/")
    if any(part in ("..", ".", "") for part in parts):
        raise PathTraversalError(f"Invalid traversal token in storage key: {key}")

    return parts


class StorageProvider(ABC):
    """
    Abstract storage provider interface.
    Deliberately omits delete() and overwrite operations to maintain forensic immutability.
    """

    @abstractmethod
    def put(
        self,
        key: str,
        data_or_stream: Union[bytes, BinaryIO],
        content_type: Optional[str] = None
    ) -> StoredObject:
        """
        Store data under the specified key.
        Refuses to overwrite if key already exists.
        Returns StoredObject with key, size, and sha256.
        """
        pass

    @abstractmethod
    def get(self, key: str) -> BinaryIO:
        """
        Retrieve a readable binary stream for the specified key.
        Raises KeyNotFoundError if key does not exist.
        """
        pass

    @abstractmethod
    def exists(self, key: str) -> bool:
        """Check whether the specified key exists."""
        pass

    @abstractmethod
    def stat(self, key: str) -> StoredObject:
        """
        Retrieve metadata and verify SHA-256 for the stored object.
        Raises KeyNotFoundError if key does not exist.
        """
        pass

    @abstractmethod
    def read_bytes_sha256(self, key: str) -> tuple[str, int]:
        """
        Stream actual object bytes and calculate SHA-256 digest independently
        of stored metadata. Returns (sha256_hex, total_bytes).
        Raises KeyNotFoundError if key does not exist.
        """
        pass


class LocalStorageProvider(StorageProvider):
    """
    Storage provider implementation writing to local filesystem under root_dir.
    Guarantees strict path traversal checks and atomic creation.
    """

    def __init__(self, root_dir: str):
        self.root_dir = os.path.abspath(root_dir)
        os.makedirs(self.root_dir, exist_ok=True)

    def _resolve_path(self, key: str) -> str:
        """
        Safely resolve a storage key to an absolute path within root_dir.
        Rejects directory traversal (e.g. '../', absolute paths, Windows drive letters).
        """
        parts = validate_storage_key(key)
        candidate = os.path.abspath(os.path.join(self.root_dir, *parts))
        if os.path.commonpath([self.root_dir, candidate]) != self.root_dir:
            raise PathTraversalError(f"Key resolves outside storage root: {key}")
        return candidate

    def exists(self, key: str) -> bool:
        path = self._resolve_path(key)
        return os.path.isfile(path)

    def put(
        self,
        key: str,
        data_or_stream: Union[bytes, BinaryIO],
        content_type: Optional[str] = None
    ) -> StoredObject:
        path = self._resolve_path(key)

        if os.path.exists(path):
            raise KeyAlreadyExistsError(f"Storage key already exists: {key}")

        os.makedirs(os.path.dirname(path), exist_ok=True)

        hasher = hashlib.sha256()
        total_size = 0

        # Atomic exclusive write: 'xb' mode raises FileExistsError if created concurrently
        try:
            with open(path, "xb") as f:
                if isinstance(data_or_stream, bytes):
                    hasher.update(data_or_stream)
                    total_size = len(data_or_stream)
                    f.write(data_or_stream)
                else:
                    while chunk := data_or_stream.read(1024 * 1024):
                        hasher.update(chunk)
                        total_size += len(chunk)
                        f.write(chunk)
        except FileExistsError:
            raise KeyAlreadyExistsError(f"Storage key already exists (concurrent conflict): {key}")
        except Exception as e:
            # Clean up partial write on failure
            if os.path.exists(path):
                try:
                    os.remove(path)
                except OSError:
                    pass
            raise StorageError(f"Failed to write evidence to local storage: {e}") from e

        return StoredObject(
            key=key,
            size=total_size,
            sha256=hasher.hexdigest(),
            content_type=content_type,
            created_at=datetime.now(timezone.utc)
        )

    def get(self, key: str) -> BinaryIO:
        path = self._resolve_path(key)
        if not os.path.isfile(path):
            raise KeyNotFoundError(f"Evidence key not found: {key}")
        try:
            return open(path, "rb")
        except OSError as e:
            raise StorageError(f"Failed opening evidence stream: {e}") from e

    def stat(self, key: str) -> StoredObject:
        path = self._resolve_path(key)
        if not os.path.isfile(path):
            raise KeyNotFoundError(f"Evidence key not found: {key}")

        hasher = hashlib.sha256()
        size = os.path.getsize(path)
        mtime = os.path.getmtime(path)

        with open(path, "rb") as f:
            while chunk := f.read(1024 * 1024):
                hasher.update(chunk)

        return StoredObject(
            key=key,
            size=size,
            sha256=hasher.hexdigest(),
            created_at=datetime.fromtimestamp(mtime, tz=timezone.utc),
            metadata_sha256=None
        )

    def read_bytes_sha256(self, key: str) -> tuple[str, int]:
        """
        Read actual local file bytes in chunks and calculate SHA-256 digest
        independently of metadata.
        """
        path = self._resolve_path(key)
        if not os.path.isfile(path):
            raise KeyNotFoundError(f"Evidence key not found: {key}")
        hasher = hashlib.sha256()
        total_size = 0
        try:
            with open(path, "rb") as f:
                while chunk := f.read(1024 * 1024):
                    hasher.update(chunk)
                    total_size += len(chunk)
            return hasher.hexdigest(), total_size
        except OSError as e:
            raise StorageError(f"Failed streaming bytes from local storage: {e}") from e


class S3StorageProvider(StorageProvider):
    """
    Enterprise S3-compatible Object Storage Provider.
    Supports AWS S3, MinIO, Cloudflare R2, Google Cloud Storage, and Ceph.
    Enforces private object ACLs, server-side encryption, append-only immutability,
    and streaming cryptographic SHA-256 calculation.
    """

    def __init__(
        self,
        bucket_name: Optional[str] = None,
        region_name: Optional[str] = None,
        endpoint_url: Optional[str] = None,
        access_key_id: Optional[str] = None,
        secret_access_key: Optional[str] = None,
        server_side_encryption: Optional[str] = None,
        s3_client: Optional[Any] = None,
    ):
        self.bucket_name = bucket_name or os.getenv("S3_BUCKET_NAME")
        if not self.bucket_name:
            raise StorageConfigurationError(
                "S3_BUCKET_NAME is required for S3StorageProvider. Configure it in environment or pass to constructor."
            )

        self.region_name = region_name or os.getenv("S3_REGION", "us-east-1")
        self.endpoint_url = endpoint_url or os.getenv("S3_ENDPOINT_URL") or None
        self.access_key_id = access_key_id or os.getenv("S3_ACCESS_KEY_ID") or None
        self.secret_access_key = secret_access_key or os.getenv("S3_SECRET_ACCESS_KEY") or None
        self.server_side_encryption = server_side_encryption or os.getenv("S3_SERVER_SIDE_ENCRYPTION") or None

        if s3_client is not None:
            self._client = s3_client
        else:
            self._client = self._init_client()

    def _init_client(self):
        try:
            import boto3
            from botocore.config import Config
        except ImportError as e:
            raise StorageConfigurationError(
                "The 'boto3' package is required for STORAGE_BACKEND='s3'. "
                "Install it using: pip install boto3"
            ) from e

        client_kwargs = {
            "region_name": self.region_name,
            "config": Config(
                retries={"max_attempts": 3, "mode": "standard"},
                connect_timeout=5,
                read_timeout=60,
            ),
        }
        if self.endpoint_url:
            client_kwargs["endpoint_url"] = self.endpoint_url
        if self.access_key_id and self.secret_access_key:
            client_kwargs["aws_access_key_id"] = self.access_key_id
            client_kwargs["aws_secret_access_key"] = self.secret_access_key

        return boto3.client("s3", **client_kwargs)

    def exists(self, key: str) -> bool:
        validate_storage_key(key)
        try:
            self._client.head_object(Bucket=self.bucket_name, Key=key)
            return True
        except Exception as e:
            resp = getattr(e, "response", {})
            status_code = resp.get("ResponseMetadata", {}).get("HTTPStatusCode")
            error_code = resp.get("Error", {}).get("Code", "")
            if status_code == 404 or error_code in ("404", "NoSuchKey", "NotFound"):
                return False
            if status_code == 403 or error_code in ("403", "AccessDenied"):
                raise StoragePermissionError(
                    f"Access denied checking key '{key}' in bucket '{self.bucket_name}': {e}"
                ) from e
            err_msg = str(e).lower()
            if "endpoint" in err_msg or "connect" in err_msg or "timeout" in err_msg:
                raise StorageUnavailableError(f"Cloud storage unavailable: {e}") from e
            return False

    def put(
        self,
        key: str,
        data_or_stream: Union[bytes, BinaryIO],
        content_type: Optional[str] = None
    ) -> StoredObject:
        validate_storage_key(key)

        # This preflight gives a useful collision error, but is not the
        # concurrency guarantee. The conditional request below rejects a key
        # created after this check.
        if self.exists(key):
            raise KeyAlreadyExistsError(f"Storage key already exists in bucket '{self.bucket_name}': {key}")

        hasher = hashlib.sha256()
        if isinstance(data_or_stream, bytes):
            body_bytes = data_or_stream
            hasher.update(body_bytes)
            total_size = len(body_bytes)
        else:
            chunks = []
            total_size = 0
            while chunk := data_or_stream.read(1024 * 1024):
                hasher.update(chunk)
                total_size += len(chunk)
                chunks.append(chunk)
            body_bytes = b"".join(chunks)

        computed_sha256 = hasher.hexdigest()

        put_kwargs = {
            "Bucket": self.bucket_name,
            "Key": key,
            "Body": body_bytes,
            "ContentType": content_type or "application/octet-stream",
            "Metadata": {
                "sha256": computed_sha256,
                "verified_size": str(total_size),
            },
            # S3-compatible providers that support conditional puts (including
            # Cloudflare R2) reject a concurrent write instead of overwriting
            # an evidence object. Do not rely on the preceding exists() call.
            "IfNoneMatch": "*",
        }
        if self.server_side_encryption:
            put_kwargs["ServerSideEncryption"] = self.server_side_encryption

        try:
            self._client.put_object(**put_kwargs)
        except Exception as e:
            resp = getattr(e, "response", {})
            status_code = resp.get("ResponseMetadata", {}).get("HTTPStatusCode")
            error_code = resp.get("Error", {}).get("Code", "")
            if status_code == 412 or error_code in ("PreconditionFailed", "412"):
                raise KeyAlreadyExistsError(f"Storage key already exists (concurrent conflict): {key}") from e
            if status_code == 403 or error_code in ("AccessDenied", "403"):
                raise StoragePermissionError(f"Access denied writing to bucket '{self.bucket_name}': {e}") from e
            if status_code == 404 or error_code in ("NoSuchBucket", "404"):
                raise StorageConfigurationError(f"Bucket '{self.bucket_name}' not found: {e}") from e
            err_msg = str(e).lower()
            if "endpoint" in err_msg or "connect" in err_msg or "timeout" in err_msg:
                raise StorageUnavailableError(f"Cloud storage provider unreachable during upload: {e}") from e
            raise StorageError(f"Cloud storage put failed: {e}") from e

        return StoredObject(
            key=key,
            size=total_size,
            sha256=computed_sha256,
            content_type=content_type,
            created_at=datetime.now(timezone.utc)
        )

    def get(self, key: str) -> BinaryIO:
        validate_storage_key(key)
        try:
            response = self._client.get_object(Bucket=self.bucket_name, Key=key)
            return response["Body"]
        except Exception as e:
            resp = getattr(e, "response", {})
            status_code = resp.get("ResponseMetadata", {}).get("HTTPStatusCode")
            error_code = resp.get("Error", {}).get("Code", "")
            if status_code == 404 or error_code in ("NoSuchKey", "404", "NotFound"):
                raise KeyNotFoundError(f"Evidence key not found: {key}") from e
            if status_code == 403 or error_code in ("AccessDenied", "403"):
                raise StoragePermissionError(f"Access denied reading evidence key '{key}': {e}") from e
            err_msg = str(e).lower()
            if "endpoint" in err_msg or "connect" in err_msg or "timeout" in err_msg:
                raise StorageUnavailableError(f"Cloud storage provider unreachable: {e}") from e
            raise StorageError(f"Cloud storage get failed: {e}") from e

    def stat(self, key: str) -> StoredObject:
        validate_storage_key(key)
        try:
            head = self._client.head_object(Bucket=self.bucket_name, Key=key)
            size = head.get("ContentLength", 0)
            content_type = head.get("ContentType")
            mtime = head.get("LastModified")
            metadata = head.get("Metadata", {})
            raw_metadata_sha256 = metadata.get("sha256")
            sha256_hash = raw_metadata_sha256

            if not sha256_hash:
                # If object was uploaded without metadata, stream it to compute verified SHA-256
                stream = self.get(key)
                hasher = hashlib.sha256()
                while chunk := stream.read(1024 * 1024):
                    hasher.update(chunk)
                sha256_hash = hasher.hexdigest()

            return StoredObject(
                key=key,
                size=size,
                sha256=sha256_hash,
                content_type=content_type,
                created_at=mtime,
                metadata_sha256=raw_metadata_sha256
            )
        except Exception as e:
            if isinstance(e, (KeyNotFoundError, StoragePermissionError, StorageUnavailableError)):
                raise
            resp = getattr(e, "response", {})
            status_code = resp.get("ResponseMetadata", {}).get("HTTPStatusCode")
            error_code = resp.get("Error", {}).get("Code", "")
            if status_code == 404 or error_code in ("NoSuchKey", "404", "NotFound"):
                raise KeyNotFoundError(f"Evidence key not found: {key}") from e
            if status_code == 403 or error_code in ("AccessDenied", "403"):
                raise StoragePermissionError(f"Access denied stat on key '{key}': {e}") from e
            err_msg = str(e).lower()
            if "endpoint" in err_msg or "connect" in err_msg or "timeout" in err_msg:
                raise StorageUnavailableError(f"Cloud storage provider unreachable: {e}") from e
            raise StorageError(f"Cloud storage stat failed: {e}") from e

    def read_bytes_sha256(self, key: str) -> tuple[str, int]:
        """
        Deep cryptographic verification: stream actual bytes directly from cloud
        object storage body, calculating SHA-256 chunk-by-chunk independently of
        stored user metadata headers (x-amz-meta-sha256).
        """
        validate_storage_key(key)
        stream = self.get(key)
        hasher = hashlib.sha256()
        total_size = 0
        try:
            while chunk := stream.read(1024 * 1024):
                hasher.update(chunk)
                total_size += len(chunk)
            return hasher.hexdigest(), total_size
        except (KeyNotFoundError, StoragePermissionError, StorageUnavailableError):
            raise
        except Exception as e:
            err_msg = str(e).lower()
            if "endpoint" in err_msg or "connect" in err_msg or "timeout" in err_msg:
                raise StorageUnavailableError(f"Cloud storage stream interrupted: {e}") from e
            raise StorageError(f"Failed streaming cloud object bytes: {e}") from e
        finally:
            if hasattr(stream, "close"):
                try:
                    stream.close()
                except Exception:
                    pass


def sanitize_filename(name: Optional[str]) -> str:
    """Strip directory markers and unsafe characters from filenames."""
    base = os.path.basename((name or "").replace("\\", "/")).strip().lstrip(".")
    cleaned = _UNSAFE_FILENAME_CHARS.sub("_", base)[:200]
    return cleaned or "unnamed_evidence"


def build_storage_key(case_id: Union[str, uuid.UUID], filename: str, file_uuid: Optional[Union[str, uuid.UUID]] = None) -> str:
    """
    Format standard evidence storage key:
    cases/{case_id}/{uuid}_{sanitized_filename}
    """
    clean_case = str(uuid.UUID(str(case_id)))
    clean_uuid = str(uuid.UUID(str(file_uuid))) if file_uuid else str(uuid.uuid4())
    clean_filename = sanitize_filename(filename)
    return f"cases/{clean_case}/{clean_uuid}_{clean_filename}"


def build_model_storage_key(case_id: Union[str, uuid.UUID], job_id: Union[str, uuid.UUID], extension: str) -> str:
    """
    Format canonical 3D model storage key:
    models/{case_id}/{job_id}_model.{extension}
    """
    clean_case = str(uuid.UUID(str(case_id)))
    clean_job = str(uuid.UUID(str(job_id)))
    ext = extension.strip().lstrip(".").lower()
    if ext not in ("glb", "ply"):
        raise StorageError(f"Invalid model extension: {extension}. Expected 'glb' or 'ply'.")
    return f"models/{clean_case}/{clean_job}_model.{ext}"


def get_storage_provider(backend: Optional[str] = None) -> StorageProvider:
    """
    Storage provider factory. Reads STORAGE_BACKEND from environment.
    Defaults to LocalStorageProvider rooted at backend/uploads.
    """
    provider_name = (backend or os.getenv("STORAGE_BACKEND", "local")).strip().lower()
    validate_storage_configuration(provider_name)
    if provider_name == "local":
        backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        uploads_dir = os.getenv("UPLOADS_DIR", "uploads")
        # A relative UPLOADS_DIR must not depend on the caller's working
        # directory: the photogrammetry worker imports this same gateway.
        if not os.path.isabs(uploads_dir):
            uploads_dir = os.path.join(backend_dir, uploads_dir)
        return LocalStorageProvider(uploads_dir)
    elif provider_name in _CLOUD_BACKENDS:
        return S3StorageProvider()
    else:
        raise StorageConfigurationError(
            f"Unsupported storage backend: '{provider_name}'. Supported backends: 'local', 's3'"
        )
