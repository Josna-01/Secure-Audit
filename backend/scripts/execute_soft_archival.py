#!/usr/bin/env python3
"""
Strategy B: Operational Soft-Archival & Disposable Output Cleanup Script
Secure Audit Platform

Safeguards:
1. Exports all disposable rows to JSON before deletion.
2. Executes inside a single atomic transaction.
3. Asserts exact row counts at every step; rolls back on any deviation.
4. Preserves all 8 cases, 35 evidence, 101 custody, 113 blockchain logs, 245 audit logs, 9 users, and 2 standalone OCR results.
5. Deletes only confirmed expired OTP tokens.
6. Does NOT touch filesystem evidence or Ganache state.
"""

import os
import sys
import json
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv
import psycopg2
from psycopg2.extras import RealDictCursor

SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent
PROJECT_ROOT = BACKEND_DIR.parent
BACKUPS_DIR = PROJECT_ROOT / "backups"
BACKUPS_DIR.mkdir(parents=True, exist_ok=True)

load_dotenv(BACKEND_DIR / ".env")

DB_USER = os.getenv("DB_USER", "postgres")
DB_PASS = os.getenv("DB_PASSWORD", "postgres")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "secure_audit")


def serialize_for_json(obj):
    if hasattr(obj, "isoformat"):
        return obj.isoformat()
    return str(obj)


def export_disposable_records(cur) -> Path:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    backup_file = BACKUPS_DIR / f"disposable_ai_outputs_backup_{ts}.json"
    print(f"Exporting disposable rows to {backup_file.name}...")

    cur.execute("SELECT * FROM detections WHERE case_id IS NOT NULL;")
    detections = cur.fetchall()

    cur.execute("SELECT * FROM photogrammetry_models WHERE case_id IS NOT NULL;")
    models = cur.fetchall()

    cur.execute("SELECT * FROM bns_predictions WHERE case_id IS NOT NULL;")
    bns = cur.fetchall()

    cur.execute("SELECT * FROM ocr_results WHERE evidence_id IS NOT NULL;")
    ocr = cur.fetchall()

    cur.execute("SELECT * FROM otp_tokens WHERE expires_at < NOW();")
    otp = cur.fetchall()

    data = {
        "export_timestamp_utc": ts,
        "counts": {
            "detections": len(detections),
            "photogrammetry_models": len(models),
            "bns_predictions": len(bns),
            "ocr_results_case_linked": len(ocr),
            "otp_tokens_expired": len(otp),
        },
        "records": {
            "detections": detections,
            "photogrammetry_models": models,
            "bns_predictions": bns,
            "ocr_results_case_linked": ocr,
            "otp_tokens_expired": otp,
        }
    }

    with open(backup_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=serialize_for_json)

    # Verification: check file exists, size > 0, and parseable
    if not backup_file.is_file() or backup_file.stat().st_size == 0:
        raise RuntimeError("Backup file was not written correctly!")
    
    with open(backup_file, "r", encoding="utf-8") as f:
        verified = json.load(f)
        assert len(verified["records"]["detections"]) == len(detections)
        assert len(verified["records"]["photogrammetry_models"]) == len(models)
        assert len(verified["records"]["bns_predictions"]) == len(bns)
        assert len(verified["records"]["ocr_results_case_linked"]) == len(ocr)
        assert len(verified["records"]["otp_tokens_expired"]) == len(otp)

    print(f"Backup verified: {backup_file.stat().st_size} bytes. All rows securely backed up.")
    return backup_file


def execute_soft_archival():
    print("=" * 80)
    print("EXECUTING STRATEGY B: OPERATIONAL SOFT-ARCHIVAL & OUTPUT CLEANUP")
    print("=" * 80)

    conn = psycopg2.connect(
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASS,
        host=DB_HOST,
        port=DB_PORT
    )
    conn.autocommit = False  # Strict transactional mode

    try:
        cur_dict = conn.cursor(cursor_factory=RealDictCursor)
        backup_path = export_disposable_records(cur_dict)
        cur_dict.close()

        cur = conn.cursor()

        # 1. Soft-archive the 8 demo cases
        print("\nStep 1: Marking 8 demo cases as archived...")
        cur.execute("UPDATE cases SET is_archived = TRUE WHERE is_archived = FALSE OR is_archived IS NULL;")
        updated_cases = cur.rowcount
        print(f"  cases updated: {updated_cases}")
        if updated_cases != 8:
            raise ValueError(f"Expected 8 cases updated, got {updated_cases}!")

        # 2. Delete disposable detections (YOLO bounding box records)
        print("\nStep 2: Deleting case-linked detections...")
        cur.execute("DELETE FROM detections WHERE case_id IS NOT NULL;")
        deleted_detections = cur.rowcount
        print(f"  detections deleted: {deleted_detections}")
        if deleted_detections != 25:
            raise ValueError(f"Expected 25 detections deleted, got {deleted_detections}!")

        # 3. Delete disposable photogrammetry_models
        print("\nStep 3: Deleting case-linked photogrammetry_models...")
        cur.execute("DELETE FROM photogrammetry_models WHERE case_id IS NOT NULL;")
        deleted_models = cur.rowcount
        print(f"  photogrammetry_models deleted: {deleted_models}")
        if deleted_models != 69:
            raise ValueError(f"Expected 69 photogrammetry_models deleted, got {deleted_models}!")

        # 4. Delete disposable bns_predictions
        print("\nStep 4: Deleting case-linked bns_predictions...")
        cur.execute("DELETE FROM bns_predictions WHERE case_id IS NOT NULL;")
        deleted_bns = cur.rowcount
        print(f"  bns_predictions deleted: {deleted_bns}")
        if deleted_bns != 2:
            raise ValueError(f"Expected 2 bns_predictions deleted, got {deleted_bns}!")

        # 5. Delete case-linked ocr_results (preserving the 2 standalone benchmark records)
        print("\nStep 5: Deleting case-linked ocr_results...")
        cur.execute("DELETE FROM ocr_results WHERE evidence_id IS NOT NULL;")
        deleted_ocr = cur.rowcount
        print(f"  ocr_results deleted: {deleted_ocr}")
        if deleted_ocr != 4:
            raise ValueError(f"Expected 4 ocr_results deleted, got {deleted_ocr}!")

        # Confirm 2 standalone benchmark OCR records remain
        cur.execute("SELECT count(*) FROM ocr_results WHERE evidence_id IS NULL;")
        standalone_ocr = cur.fetchone()[0]
        print(f"  standalone OCR results preserved: {standalone_ocr}")
        if standalone_ocr != 2:
            raise ValueError(f"Expected 2 standalone OCR results preserved, got {standalone_ocr}!")

        # 6. Delete only confirmed expired OTP tokens
        print("\nStep 6: Deleting confirmed expired OTP tokens...")
        cur.execute("DELETE FROM otp_tokens WHERE expires_at < NOW();")
        deleted_otp = cur.rowcount
        print(f"  expired otp_tokens deleted: {deleted_otp}")
        if deleted_otp != 68:
            raise ValueError(f"Expected 68 expired otp_tokens deleted, got {deleted_otp}!")

        # Confirm zero active tokens were touched
        cur.execute("SELECT count(*) FROM otp_tokens WHERE expires_at >= NOW();")
        active_otp = cur.fetchone()[0]
        if active_otp != 0:
            raise ValueError(f"Unexpected active OTP tokens found: {active_otp}!")

        # 7. Comprehensive Post-Execution Parity Verification BEFORE COMMIT
        print("\nStep 7: Verifying all preserved tables before committing transaction...")

        cur.execute("SELECT count(*) FROM cases;")
        total_cases = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM cases WHERE is_archived = TRUE;")
        archived_cases = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM cases WHERE is_archived = FALSE OR is_archived IS NULL;")
        active_cases = cur.fetchone()[0]

        cur.execute("SELECT count(*) FROM evidence;")
        total_evidence = cur.fetchone()[0]

        cur.execute("SELECT count(*) FROM evidence_custody_records;")
        total_custody = cur.fetchone()[0]

        cur.execute("SELECT count(*) FROM blockchain_logs;")
        total_bc_logs = cur.fetchone()[0]

        cur.execute("SELECT count(*) FROM audit_logs;")
        total_audit_logs = cur.fetchone()[0]

        cur.execute("SELECT count(*) FROM users;")
        total_users = cur.fetchone()[0]

        print(f"  cases: {total_cases} total ({archived_cases} archived, {active_cases} active)")
        print(f"  evidence: {total_evidence} (100% preserved)")
        print(f"  evidence_custody_records: {total_custody} (100% preserved)")
        print(f"  blockchain_logs: {total_bc_logs} (100% preserved)")
        print(f"  audit_logs: {total_audit_logs} (100% preserved)")
        print(f"  users: {total_users} (100% preserved)")
        print(f"  ocr_results remaining: {standalone_ocr} (100% preserved)")

        assert total_cases == 8 and archived_cases == 8 and active_cases == 0
        assert total_evidence == 35
        assert total_custody == 101
        assert total_bc_logs == 113
        assert total_audit_logs == 245
        assert total_users == 9

        # All checks passed: COMMIT
        conn.commit()
        print("\n" + "=" * 80)
        print("TRANSACTION COMMITTED SUCCESSFULLY!")
        print(f"All safeguards satisfied. Backup saved to: {backup_path.name}")
        print("=" * 80)

    except Exception as e:
        conn.rollback()
        print("\n" + "!" * 80)
        print(f"TRANSACTION ROLLED BACK DUE TO ERROR: {e}")
        print("Zero modifications were persisted to the database.")
        print("!" * 80)
        conn.close()
        sys.exit(1)

    conn.close()


if __name__ == "__main__":
    execute_soft_archival()
