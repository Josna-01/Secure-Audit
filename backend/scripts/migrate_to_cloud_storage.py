#!/usr/bin/env python3
"""
Secure Audit — Phase 2C: Reversible Cloud Storage Migration Tool
Location: backend/scripts/migrate_to_cloud_storage.py

MANDATORY FORENSIC SAFEGUARDS:
1. Strict Allowlist: Only the 30 verified records enter the initial migration allowlist.
2. Immediate Pre-Upload Check: Every local file is re-hashed immediately before upload.
3. Quarantine: The 2 mismatched records and 1 missing record are strictly excluded.
4. Remote Verification: The 2 Supabase objects are verified in-memory before staging.
5. Post-Upload Readback: Every uploaded object is read back and independently verified.
6. Reversible Mapping: Generates JSON mapping and SQL rollback artifacts in backups/.
7. Zero Database Mutations: Database evidence rows and file_url values remain 100% UNCHANGED.
8. Zero Local File Deletions: Local upload files remain 100% UNCHANGED.
"""

import os
import sys
import json
import argparse
import hashlib
import uuid
import requests
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse
from typing import Dict, Any, List, Optional, Tuple

# Ensure backend root is on sys.path
SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent
PROJECT_ROOT = BACKEND_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from db import SessionLocal
from models import Evidence
from services.storage_gateway import (
    get_storage_provider,
    S3StorageProvider,
    LocalStorageProvider,
    validate_storage_key,
    sanitize_filename,
    StoredObject,
    KeyAlreadyExistsError,
    KeyNotFoundError,
    StorageError,
    StorageIntegrityError,
    StorageUnavailableError,
    StoragePermissionError
)

UPLOADS_DIR = BACKEND_DIR / "uploads"
BACKUPS_DIR = PROJECT_ROOT / "backups"
BACKUPS_DIR.mkdir(parents=True, exist_ok=True)

# Known quarantined record IDs from Phase 2A & 2B audits
KNOWN_QUARANTINED_IDS = {
    "222971f3-be43-4a5c-b43b-96dabeae9724": "MISSING_SOURCE_FILE",
    "e1d6f8da-c959-4e63-b8bf-58be7436edbf": "INTEGRITY_MISMATCH",
    "1bb766d2-d9d6-426d-aa51-a30aa9d295c1": "INTEGRITY_MISMATCH",
}

KNOWN_REMOTE_SUPABASE_IDS = {
    "1dad65d2-0fa0-45f9-943b-de1ec8c114a0": "SUPABASE_REMOTE",
    "74da8cd4-347a-48e4-9628-94727977a599": "SUPABASE_REMOTE",
}


def compute_sha256(path: Path) -> str:
    """Compute cryptographic SHA-256 of file in 1MB chunks."""
    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(1024 * 1024):
            hasher.update(chunk)
    return hasher.hexdigest().lower()


def resolve_local_path(file_url: str, uploads_root: Path) -> Tuple[Optional[Path], Optional[str]]:
    """Safely resolve localhost/uploads file_url to local Path with traversal defense."""
    try:
        parsed = urlparse(file_url)
        path_part = parsed.path.replace("\\", "/")
        if "/uploads/" not in path_part:
            return None, "URL does not contain /uploads/ path component"
        rel_subpath = path_part.split("/uploads/", 1)[-1]
        parts = [p for p in rel_subpath.split("/") if p and p != "."]
        
        resolved = (uploads_root / Path(*parts)).resolve()
        uploads_root_resolved = uploads_root.resolve()
        if uploads_root_resolved not in resolved.parents and resolved != uploads_root_resolved:
            return None, "Path traversal attempted outside uploads root"
        return resolved, None
    except Exception as e:
        return None, f"Resolution error: {e}"


def generate_canonical_s3_key(case_id: str, evidence_id: str, filename: str) -> str:
    """Canonical S3 Key: cases/{case_id}/{evidence_id}_{sanitized_filename}"""
    clean_case = str(uuid.UUID(str(case_id)))
    clean_ev_id = str(uuid.UUID(str(evidence_id)))
    clean_filename = sanitize_filename(filename)
    return f"cases/{clean_case}/{clean_ev_id}_{clean_filename}"


class CloudMigrationRunner:
    def __init__(
        self,
        provider: S3StorageProvider,
        include_remote: bool = False,
        dry_run: bool = True
    ):
        self.provider = provider
        self.include_remote = include_remote
        self.dry_run = dry_run
        self.timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        self.results: List[Dict[str, Any]] = []
        self.quarantined: List[Dict[str, Any]] = []
        self.stats = {
            "total_evaluated": 0,
            "allowlist_initial_count": 0,
            "pre_upload_verified": 0,
            "uploaded_success": 0,
            "readback_verified": 0,
            "already_existed_verified": 0,
            "remote_verified": 0,
            "quarantined_count": 0,
            "upload_failures": 0,
            "readback_failures": 0,
        }

    def run(self) -> Dict[str, Any]:
        print("=" * 80)
        print(f"SECURE AUDIT — PHASE 2C: CLOUD STORAGE MIGRATION PIPELINE")
        print(f"Timestamp: {self.timestamp} UTC")
        print(f"Mode: {'DRY RUN (Preview Only)' if self.dry_run else 'EXECUTE (Upload & Read-Back Verification)'}")
        print(f"Include Remote Supabase Exhibits: {'YES' if self.include_remote else 'NO (Local 30 Only)'}")
        print(f"Target Bucket: {self.provider.bucket_name}")
        print("Forensic Safeguards: ZERO Database Writes, ZERO Local File Deletions")
        print("=" * 80)

        db = SessionLocal()
        try:
            evidence_rows = db.query(Evidence).order_by(Evidence.created_at.asc()).all()
            print(f"[VERIFIED] Successfully loaded {len(evidence_rows)} evidence records from database.\n")
        finally:
            db.close()

        self.stats["total_evaluated"] = len(evidence_rows)

        # Step 1: Segregate into Allowlist, Remote, and Quarantined
        allowlist_rows = []
        remote_rows = []

        for ev in evidence_rows:
            ev_id = str(ev.id)
            db_hash = (ev.file_hash or "").strip().lower()

            # Check known quarantined
            if ev_id in KNOWN_QUARANTINED_IDS:
                reason = KNOWN_QUARANTINED_IDS[ev_id]
                self.quarantined.append({
                    "evidence_id": ev_id,
                    "case_id": str(ev.case_id) if ev.case_id else None,
                    "file_name": ev.file_name,
                    "db_file_hash": db_hash,
                    "file_url": ev.file_url,
                    "quarantine_reason": reason,
                    "status": "QUARANTINED_EXCLUDED_FROM_ALLOWLIST"
                })
                print(f"[QUARANTINE EXCLUSION] Evidence {ev_id} ({ev.file_name}): {reason}")
                continue

            # Check remote Supabase
            if "supabase.co" in (ev.file_url or "") or ev_id in KNOWN_REMOTE_SUPABASE_IDS:
                remote_rows.append(ev)
                continue

            # Local candidate
            allowlist_rows.append(ev)

        self.stats["allowlist_initial_count"] = len(allowlist_rows)
        self.stats["quarantined_count"] = len(self.quarantined)

        print(f"\n[PIPELINE SUMMARY] Candidates Segregated:")
        print(f" - Local Allowlist Candidates: {len(allowlist_rows)}")
        print(f" - Remote Supabase Candidates: {len(remote_rows)}")
        print(f" - Quarantined Records:        {len(self.quarantined)}")
        print("-" * 80)

        # Step 2: Process Local Allowlist Candidates
        print("\n[PHASE 2C.1] Processing Local Allowlist Exhibits:")
        for ev in allowlist_rows:
            self._process_local_candidate(ev)

        # Step 3: Process Remote Supabase Exhibits if requested
        if self.include_remote:
            print("\n[PHASE 2C.2] Processing Remote Supabase Exhibits (Source Verification & Staging):")
            for ev in remote_rows:
                self._process_remote_candidate(ev)
        else:
            print("\n[PHASE 2C.2] Remote Supabase exhibits skipped (Pass --include-remote to verify & stage).")

        # Step 4: Write Reversible Mapping & Audit Artifacts
        return self._generate_artifacts()

    def _process_local_candidate(self, ev: Evidence):
        ev_id = str(ev.id)
        case_id = str(ev.case_id)
        filename = ev.file_name or "unnamed_evidence"
        db_hash = (ev.file_hash or "").strip().lower()
        file_url = ev.file_url or ""
        mime_type = ev.mime_type or "application/octet-stream"

        canonical_key = generate_canonical_s3_key(case_id, ev_id, filename)
        validate_storage_key(canonical_key)

        record_res = {
            "evidence_id": ev_id,
            "case_id": case_id,
            "file_name": filename,
            "old_file_url": file_url,
            "new_storage_key": canonical_key,
            "db_file_hash": db_hash,
            "pre_upload_sha256": None,
            "pre_upload_match": False,
            "source_type": "localhost",
            "file_size": None,
            "upload_status": "PENDING",
            "readback_verified": False,
            "readback_sha256": None,
            "error": None,
            "reversal_sql": f"UPDATE evidence SET file_url = '{file_url}' WHERE id = '{ev_id}';"
        }

        # 1. Resolve local path
        local_path, err = resolve_local_path(file_url, UPLOADS_DIR)
        if err or not local_path or not local_path.is_file():
            record_res["upload_status"] = "ABORTED_SOURCE_MISSING"
            record_res["error"] = err or f"File not found on disk: {local_path}"
            self.results.append(record_res)
            print(f"  [ABORT] {ev_id} ({filename}): Local file missing")
            return

        # 2. Immediate Pre-Upload Check: Calculate and verify SHA-256
        f_size = local_path.stat().st_size
        pre_sha = compute_sha256(local_path)
        record_res["file_size"] = f_size
        record_res["pre_upload_sha256"] = pre_sha

        if pre_sha != db_hash:
            record_res["upload_status"] = "ABORTED_PRE_UPLOAD_INTEGRITY_MISMATCH"
            record_res["error"] = f"Pre-upload hash mismatch: Disk ({pre_sha}) != DB ({db_hash})"
            self.results.append(record_res)
            print(f"  [ABORT] {ev_id} ({filename}): Hash mismatch on disk!")
            return

        record_res["pre_upload_match"] = True
        self.stats["pre_upload_verified"] += 1

        if self.dry_run:
            record_res["upload_status"] = "DRY_RUN_READY"
            self.results.append(record_res)
            print(f"  [DRY RUN READY] {ev_id} -> {canonical_key} ({round(f_size/1024, 1)} KB, SHA-256 Match)")
            return

        # 3. Execution Mode: Check if already exists in target S3
        try:
            if self.provider.exists(canonical_key):
                # Verify existing object in S3
                obj_meta = self.provider.stat(canonical_key)
                if obj_meta.sha256 == db_hash:
                    record_res["upload_status"] = "ALREADY_MIGRATED_VALID"
                    record_res["readback_verified"] = True
                    record_res["readback_sha256"] = obj_meta.sha256
                    self.stats["already_existed_verified"] += 1
                    self.results.append(record_res)
                    print(f"  [IDEMPOTENT SKIP] {ev_id}: Already exists in S3 with verified SHA-256")
                    return
                else:
                    raise StorageIntegrityError(f"Existing S3 object hash mismatch for key: {canonical_key}")

            # 4. Upload to Target Bucket
            with open(local_path, "rb") as f:
                stored_obj = self.provider.put(
                    key=canonical_key,
                    data_or_stream=f,
                    content_type=mime_type
                )
            self.stats["uploaded_success"] += 1
            record_res["upload_status"] = "UPLOADED"

            # 5. Read-Back Verification (Step 4 Requirement)
            stream = self.provider.get(canonical_key)
            rb_hasher = hashlib.sha256()
            while chunk := stream.read(1024 * 1024):
                rb_hasher.update(chunk)
            stream.close()

            rb_sha = rb_hasher.hexdigest().lower()
            record_res["readback_sha256"] = rb_sha

            if rb_sha == db_hash:
                record_res["readback_verified"] = True
                record_res["upload_status"] = "MIGRATED_AND_VERIFIED"
                self.stats["readback_verified"] += 1
                print(f"  [VERIFIED UPLOAD] {ev_id} -> {canonical_key} (SHA-256 Confirmed)")
            else:
                record_res["readback_verified"] = False
                record_res["upload_status"] = "READBACK_INTEGRITY_FAILURE"
                self.stats["readback_failures"] += 1
                print(f"  [CRITICAL ERROR] {ev_id}: Readback hash ({rb_sha}) != DB ({db_hash})")

        except Exception as e:
            record_res["upload_status"] = "UPLOAD_FAILED"
            record_res["error"] = str(e)
            self.stats["upload_failures"] += 1
            print(f"  [FAILURE] {ev_id} upload failed: {e}")

        self.results.append(record_res)

    def _process_remote_candidate(self, ev: Evidence):
        ev_id = str(ev.id)
        case_id = str(ev.case_id)
        filename = ev.file_name or "unnamed_evidence"
        db_hash = (ev.file_hash or "").strip().lower()
        file_url = ev.file_url or ""
        mime_type = ev.mime_type or "application/octet-stream"

        canonical_key = generate_canonical_s3_key(case_id, ev_id, filename)
        validate_storage_key(canonical_key)

        record_res = {
            "evidence_id": ev_id,
            "case_id": case_id,
            "file_name": filename,
            "old_file_url": file_url,
            "new_storage_key": canonical_key,
            "db_file_hash": db_hash,
            "pre_upload_sha256": None,
            "pre_upload_match": False,
            "source_type": "supabase",
            "file_size": None,
            "upload_status": "PENDING",
            "readback_verified": False,
            "readback_sha256": None,
            "error": None,
            "reversal_sql": f"UPDATE evidence SET file_url = '{file_url}' WHERE id = '{ev_id}';"
        }

        # 1. Fetch bytes from remote Supabase source with timeout
        try:
            resp = requests.get(file_url, timeout=(5, 60))
            if resp.status_code != 200:
                record_res["upload_status"] = "REMOTE_FETCH_FAILED"
                record_res["error"] = f"HTTP {resp.status_code} fetching from Supabase"
                self.results.append(record_res)
                print(f"  [ABORT REMOTE] {ev_id}: Supabase returned HTTP {resp.status_code}")
                return

            body = resp.content
            remote_sha = hashlib.sha256(body).hexdigest().lower()
            record_res["file_size"] = len(body)
            record_res["pre_upload_sha256"] = remote_sha

            # 2. Strict Pre-Upload Verification
            if remote_sha != db_hash:
                record_res["upload_status"] = "ABORTED_REMOTE_HASH_MISMATCH"
                record_res["error"] = f"Remote hash ({remote_sha}) != DB ({db_hash})"
                self.results.append(record_res)
                print(f"  [ABORT REMOTE] {ev_id}: Remote SHA-256 does not match database!")
                return

            record_res["pre_upload_match"] = True
            self.stats["remote_verified"] += 1

            if self.dry_run:
                record_res["upload_status"] = "DRY_RUN_READY"
                self.results.append(record_res)
                print(f"  [REMOTE READY] {ev_id} -> {canonical_key} ({len(body)} bytes, SHA-256 Match)")
                return

            # 3. Upload to Target S3
            if self.provider.exists(canonical_key):
                obj_meta = self.provider.stat(canonical_key)
                if obj_meta.sha256 == db_hash:
                    record_res["upload_status"] = "ALREADY_MIGRATED_VALID"
                    record_res["readback_verified"] = True
                    record_res["readback_sha256"] = obj_meta.sha256
                    self.stats["already_existed_verified"] += 1
                    self.results.append(record_res)
                    print(f"  [IDEMPOTENT SKIP REMOTE] {ev_id}: Already staged in S3 with verified SHA-256")
                    return

            stored_obj = self.provider.put(
                key=canonical_key,
                data_or_stream=body,
                content_type=mime_type
            )
            self.stats["uploaded_success"] += 1

            # 4. Read-Back Verification
            stream = self.provider.get(canonical_key)
            rb_hasher = hashlib.sha256()
            while chunk := stream.read(1024 * 1024):
                rb_hasher.update(chunk)
            stream.close()

            rb_sha = rb_hasher.hexdigest().lower()
            record_res["readback_sha256"] = rb_sha

            if rb_sha == db_hash:
                record_res["readback_verified"] = True
                record_res["upload_status"] = "MIGRATED_AND_VERIFIED"
                self.stats["readback_verified"] += 1
                print(f"  [VERIFIED REMOTE UPLOAD] {ev_id} -> {canonical_key} (SHA-256 Confirmed)")
            else:
                record_res["readback_verified"] = False
                record_res["upload_status"] = "READBACK_INTEGRITY_FAILURE"
                self.stats["readback_failures"] += 1

        except Exception as e:
            record_res["upload_status"] = "REMOTE_UPLOAD_FAILED"
            record_res["error"] = str(e)
            self.stats["upload_failures"] += 1
            print(f"  [REMOTE FAILURE] {ev_id}: {e}")

        self.results.append(record_res)

    def _generate_artifacts(self) -> Dict[str, Any]:
        mapping_file = BACKUPS_DIR / f"cloud_migration_mapping_{self.timestamp}.json"
        rollback_sql_file = BACKUPS_DIR / f"rollback_storage_mapping_{self.timestamp}.sql"

        # Generate SQL rollback script
        sql_lines = [
            f"-- SECURE AUDIT — ROLLBACK MAPPING SCRIPT ({self.timestamp} UTC)",
            "-- In Phase 2C, database records were NOT updated.",
            "-- If database references are updated in future Phase 2D cutover, this script reverts every file_url.",
            "BEGIN;\n"
        ]
        for item in self.results:
            sql_lines.append(f"-- Evidence {item['evidence_id']} ({item['file_name']})")
            sql_lines.append(item["reversal_sql"])
        sql_lines.append("\nCOMMIT;\n")

        with open(rollback_sql_file, "w", encoding="utf-8") as f:
            f.write("\n".join(sql_lines))

        output_payload = {
            "pipeline": "Phase 2C Reversible Cloud Storage Migration",
            "timestamp_utc": self.timestamp,
            "mode": "DRY_RUN" if self.dry_run else "EXECUTE",
            "target_bucket": self.provider.bucket_name,
            "database_mutations_performed": 0,
            "local_files_deleted": 0,
            "statistics": self.stats,
            "quarantined_exhibits": self.quarantined,
            "migration_results": self.results,
            "rollback_sql_path": str(rollback_sql_file),
            "mapping_json_path": str(mapping_file)
        }

        with open(mapping_file, "w", encoding="utf-8") as f:
            json.dump(output_payload, f, indent=2)

        print("\n" + "=" * 80)
        print("PHASE 2C MIGRATION PIPELINE EXECUTION REPORT")
        print("=" * 80)
        print(f"Total Evidence Records Evaluated:     {self.stats['total_evaluated']}")
        print(f" - Local Allowlist Candidates:         {self.stats['allowlist_initial_count']}")
        print(f" - Pre-Upload Integrity Verified:      {self.stats['pre_upload_verified']}")
        print(f" - Uploaded & Read-Back Verified:      {self.stats['readback_verified']}")
        print(f" - Idempotent Staged Skips:            {self.stats['already_existed_verified']}")
        print(f" - Remote Supabase Staged:             {self.stats['remote_verified']}")
        print(f" - Quarantined (Excluded):             {self.stats['quarantined_count']}")
        print(f" - Failures:                           {self.stats['upload_failures'] + self.stats['readback_failures']}")
        print("-" * 80)
        print(f"Database Evidence Rows Modified:       0 (Strict Forensics Guarantee)")
        print(f"Local Disk Files Modified / Deleted:   0 (Strict Forensics Guarantee)")
        print(f"Rollback Script Generated:             {rollback_sql_file}")
        print(f"Reversible Mapping Generated:          {mapping_file}")
        print("=" * 80)

        return output_payload


def main():
    parser = argparse.ArgumentParser(description="Secure Audit Phase 2C Reversible Cloud Migration")
    parser.add_argument("--dry-run", action="store_true", default=False, help="Dry run without uploading")
    parser.add_argument("--execute", action="store_true", default=False, help="Execute upload to target S3 provider")
    parser.add_argument("--include-remote", action="store_true", default=False, help="Verify and migrate 2 Supabase remote exhibits")
    parser.add_argument("--use-mock-s3", action="store_true", default=False, help="Use in-process Moto S3 backend for offline end-to-end verification")
    parser.add_argument("--bucket", default="secure-audit-forensic-evidence", help="Target S3 bucket name")

    args = parser.parse_args()

    # Default to dry-run if neither --execute nor --dry-run explicitly provided
    is_dry_run = True
    if args.execute and not args.dry_run:
        is_dry_run = False

    # Initialize Provider
    if args.use_mock_s3:
        import moto
        import boto3
        mock = moto.mock_aws()
        mock.start()
        client = boto3.client("s3", region_name="us-east-1")
        client.create_bucket(Bucket=args.bucket)
        provider = S3StorageProvider(
            bucket_name=args.bucket,
            region_name="us-east-1",
            s3_client=client,
            server_side_encryption="AES256"
        )
        print("[MOTO S3] In-memory encrypted S3 mock backend initialized successfully.")
    else:
        # Live provider via environment
        provider = S3StorageProvider(bucket_name=args.bucket)

    runner = CloudMigrationRunner(
        provider=provider,
        include_remote=args.include_remote,
        dry_run=is_dry_run
    )
    runner.run()


if __name__ == "__main__":
    main()
