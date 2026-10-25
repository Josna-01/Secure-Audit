#!/usr/bin/env python3
"""
Task 2 Evidence Inventory Analyzer
"""

import os
import sys
import json
import hashlib
from pathlib import Path
from dotenv import load_dotenv

SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent
PROJECT_ROOT = BACKEND_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

load_dotenv(BACKEND_DIR / ".env")

from db import SessionLocal
from models import Evidence, EvidenceCustodyRecord, BlockchainLog
from scripts.storage_migration_dryrun import classify_url, resolve_local_path, compute_sha256

UPLOADS_DIR = BACKEND_DIR / "uploads"

def main():
    db = SessionLocal()
    rows = db.query(Evidence).all()

    classifications = {
        "FILE_FOUND_AND_HASH_VERIFIED": [],
        "FILE_FOUND_BUT_HASH_MISMATCHED": [],
        "FILE_MISSING": [],
        "HASH_UNAVAILABLE": [],
        "STORAGE_REFERENCE_UNRESOLVED": [],
        "BLOCKCHAIN_REFERENCE_REQUIRES_FURTHER_VERIFICATION": []
    }

    detailed_records = []

    for ev in rows:
        ev_id = str(ev.id)
        case_id = str(ev.case_id) if ev.case_id else None
        file_url = ev.file_url
        file_hash = (ev.file_hash or "").strip().lower()
        url_type = classify_url(file_url)

        # Count custody and blockchain logs
        custody_count = db.query(EvidenceCustodyRecord).filter(EvidenceCustodyRecord.evidence_id == ev.id).count()
        b_logs_count = db.query(BlockchainLog).filter(BlockchainLog.evidence_id == ev.id).count()

        rec = {
            "evidence_id": ev_id,
            "case_id": case_id,
            "file_name": ev.file_name,
            "file_url": file_url,
            "url_type": url_type,
            "db_hash": file_hash,
            "custody_records_count": custody_count,
            "blockchain_logs_count": b_logs_count,
            "blockchain_tx_hash": ev.blockchain_tx_hash,
            "blockchain_block_number": ev.blockchain_block_number,
            "blockchain_contract_address": ev.blockchain_contract_address,
            "blockchain_registered_at": str(ev.blockchain_registered_at) if ev.blockchain_registered_at else None,
            "chain_of_custody_status": ev.chain_of_custody_status,
            "evidence_status": ev.status,
            "classification": None,
            "detail": ""
        }

        # Check hash availability
        if not file_hash:
            rec["classification"] = "HASH_UNAVAILABLE"
            rec["detail"] = "Evidence record has NULL or empty file_hash in DB"
            classifications["HASH_UNAVAILABLE"].append(rec)
            detailed_records.append(rec)
            continue

        # Storage resolution
        if url_type == "supabase":
            rec["classification"] = "STORAGE_REFERENCE_UNRESOLVED"
            rec["detail"] = "Supabase remote URL cannot be resolved in private/local storage"
            classifications["STORAGE_REFERENCE_UNRESOLVED"].append(rec)
        elif url_type != "localhost":
            rec["classification"] = "STORAGE_REFERENCE_UNRESOLVED"
            rec["detail"] = f"Unresolvable URL scheme/target: {file_url}"
            classifications["STORAGE_REFERENCE_UNRESOLVED"].append(rec)
        else:
            local_path, err = resolve_local_path(file_url, UPLOADS_DIR)
            if err or not local_path:
                rec["classification"] = "STORAGE_REFERENCE_UNRESOLVED"
                rec["detail"] = err or "Could not parse path"
                classifications["STORAGE_REFERENCE_UNRESOLVED"].append(rec)
            elif not local_path.is_file():
                rec["classification"] = "FILE_MISSING"
                rec["detail"] = f"File missing at path: {local_path}"
                classifications["FILE_MISSING"].append(rec)
            else:
                comp_hash = compute_sha256(local_path)
                rec["computed_hash"] = comp_hash
                if comp_hash != file_hash:
                    rec["classification"] = "FILE_FOUND_BUT_HASH_MISMATCHED"
                    rec["detail"] = f"Computed SHA-256 ({comp_hash}) != DB hash ({file_hash})"
                    classifications["FILE_FOUND_BUT_HASH_MISMATCHED"].append(rec)
                else:
                    rec["classification"] = "FILE_FOUND_AND_HASH_VERIFIED"
                    rec["detail"] = f"File exists ({local_path.stat().st_size} bytes), hash matches DB"
                    classifications["FILE_FOUND_AND_HASH_VERIFIED"].append(rec)

        # Check blockchain anchoring status
        # If tx_hash is missing, or node is unreachable, it requires further verification
        rec["blockchain_anchored"] = bool(ev.blockchain_tx_hash)
        if not ev.blockchain_tx_hash or not ev.blockchain_block_number:
            rec["blockchain_status"] = "UNREGISTERED_OR_MISSING_TX"
            classifications["BLOCKCHAIN_REFERENCE_REQUIRES_FURTHER_VERIFICATION"].append(rec)
        else:
            rec["blockchain_status"] = f"TX_RECORDED (Block {ev.blockchain_block_number})"

        detailed_records.append(rec)

    db.close()

    print("=" * 80)
    print("TASK 2 EVIDENCE CLASSIFICATION SUMMARY")
    print("=" * 80)
    for k, v in classifications.items():
        print(f"{k:<50}: {len(v)}")

    print("\nDetailed breakdown of non-verified / non-standard records:")
    for k in ["FILE_FOUND_BUT_HASH_MISMATCHED", "FILE_MISSING", "STORAGE_REFERENCE_UNRESOLVED", "HASH_UNAVAILABLE"]:
        if classifications[k]:
            print(f"\n--- {k} ({len(classifications[k])} rows) ---")
            for r in classifications[k]:
                print(f"  ID: {r['evidence_id']} | Case: {r['case_id']} | File: {r['file_name']}")
                print(f"     URL: {r['file_url']}")
                print(f"     Detail: {r['detail']}")

    # Save to JSON
    out_file = PROJECT_ROOT / "backups" / "task2_evidence_inventory_detailed.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump({
            "classifications_count": {k: len(v) for k, v in classifications.items()},
            "records": detailed_records
        }, f, indent=2)
    print(f"\nSaved detailed analysis to {out_file}")

if __name__ == "__main__":
    main()
