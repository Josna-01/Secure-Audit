#!/usr/bin/env python3
"""
Storage Migration Dry-Run & Inventory Script (Phase 2A)
READ-ONLY execution:
- Inspects all rows in `evidence` table.
- Classifies URLs (localhost, supabase, other, null).
- Resolves local paths, verifies file existence, computes SHA-256, compares with DB hash.
- Reads on-chain registration from smart contract (read-only call); if unreachable, marks CHAIN_UNREACHABLE.
- Discovers orphan files in backend/uploads and duplicate hashes.
- Writes backups/migration_dryrun_<timestamp>.json and .csv.
- NEVER writes to the DB. NEVER modifies or deletes any evidence file.
"""

import os
import sys
import json
import csv
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

# Ensure backend root is on sys.path
SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent
PROJECT_ROOT = BACKEND_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from db import SessionLocal
from models import Evidence
try:
    from services.blockchain_service import blockchain_service, BlockchainUnavailable
except ImportError:
    blockchain_service = None
    BlockchainUnavailable = Exception

UPLOADS_DIR = BACKEND_DIR / "uploads"
BACKUPS_DIR = PROJECT_ROOT / "backups"
BACKUPS_DIR.mkdir(parents=True, exist_ok=True)


def compute_sha256(path: Path) -> str:
    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(1024 * 1024):
            hasher.update(chunk)
    return hasher.hexdigest().lower()


def classify_url(file_url: str | None) -> str:
    if not file_url or not str(file_url).strip():
        return "null"
    url_str = str(file_url).strip()
    if "supabase.co" in url_str:
        return "supabase"
    if "localhost" in url_str or "127.0.0.1" in url_str or url_str.startswith("/uploads/"):
        return "localhost"
    return "other"


def resolve_local_path(file_url: str, uploads_root: Path) -> tuple[Path | None, str | None]:
    """
    Safely resolves a localhost/uploads file_url to a Path under uploads_root.
    Returns (Path, None) or (None, error_reason).
    """
    try:
        parsed = urlparse(file_url)
        path_part = parsed.path.replace("\\", "/")
        if "/uploads/" not in path_part:
            return None, "URL does not contain /uploads/ path component"
        rel_subpath = path_part.split("/uploads/", 1)[-1]
        parts = [p for p in rel_subpath.split("/") if p and p != "."]
        
        # Prevent traversal
        resolved = (uploads_root / Path(*parts)).resolve()
        uploads_root_resolved = uploads_root.resolve()
        if uploads_root_resolved not in resolved.parents and resolved != uploads_root_resolved:
            return None, "Path traversal attempted outside uploads directory"
        return resolved, None
    except Exception as e:
        return None, f"Resolution error: {e}"


def check_chain_registration(evidence_id_str: str, rpc_alive: bool) -> tuple[str, str | None, str | None]:
    """
    Performs a read-only query against the smart contract.
    Returns (chain_status, on_chain_hash, error_msg).
    chain_status can be: 'REACHABLE', 'CHAIN_UNREACHABLE', 'NOT_REGISTERED'
    """
    if blockchain_service is None or not rpc_alive:
        return "CHAIN_UNREACHABLE", None, "Blockchain node is offline / RPC unreachable at http://127.0.0.1:8545"
    try:
        registration = blockchain_service.get_registration(evidence_id_str)
        if registration is None:
            return "NOT_REGISTERED", None, None
        return "REACHABLE", registration.get("sha256Hash", "").lower(), None
    except BlockchainUnavailable as e:
        return "CHAIN_UNREACHABLE", None, str(e)
    except Exception as e:
        return "CHAIN_UNREACHABLE", None, f"Chain read error: {e}"



def run_dryrun():
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    print("=" * 80)
    print(f"SECURE AUDIT - STORAGE MIGRATION DRY-RUN INVENTORY ({ts} UTC)")
    print("=" * 80)
    print("Mode: STRICT READ-ONLY. Live database will NOT be modified.")
    print("Checking database connection...")

    db = SessionLocal()
    try:
        evidence_rows = db.query(Evidence).all()
        print(f"Successfully loaded {len(evidence_rows)} evidence rows from database.")
    except Exception as e:
        print(f"ERROR: Could not query evidence table: {e}")
        db.close()
        sys.exit(1)

    # Check blockchain RPC liveness once upfront to prevent repeated socket timeouts
    rpc_is_alive = False
    if blockchain_service is not None:
        try:
            rpc_is_alive = blockchain_service.is_rpc_alive(timeout=1.0)
        except Exception:
            rpc_is_alive = False
    print(f"Blockchain RPC node liveness check: {'ALIVE' if rpc_is_alive else 'OFFLINE / UNREACHABLE'}")


    # 1. Inspect and classify all DB rows
    inventory = []
    status_counts = {
        "OK": 0,
        "MISSING_FILE": 0,
        "HASH_MISMATCH": 0,
        "CHAIN_MISMATCH": 0,
        "UNRESOLVABLE_URL": 0,
        "CHAIN_UNREACHABLE": 0,
    }
    url_counts = {"localhost": 0, "supabase": 0, "other": 0, "null": 0}

    resolved_disk_paths = set()
    hash_to_rows = {}

    for ev in evidence_rows:
        ev_id = str(ev.id)
        file_url = ev.file_url
        db_hash = (ev.file_hash or "").strip().lower()
        url_type = classify_url(file_url)
        url_counts[url_type] = url_counts.get(url_type, 0) + 1

        # Track hash duplicates in DB
        if db_hash:
            hash_to_rows.setdefault(db_hash, []).append(ev_id)

        rec = {
            "evidence_id": ev_id,
            "case_id": str(ev.case_id) if ev.case_id else None,
            "file_name": ev.file_name,
            "file_url": file_url,
            "url_type": url_type,
            "resolved_local_path": None,
            "file_exists": False,
            "file_size": None,
            "db_file_hash": db_hash,
            "computed_sha256": None,
            "disk_hash_match": False,
            "chain_status": None,
            "on_chain_hash": None,
            "chain_hash_match": False,
            "final_status": "UNKNOWN",
            "notes": ""
        }

        # Local resolution
        if url_type == "localhost":
            resolved_path, err = resolve_local_path(file_url, UPLOADS_DIR)
            if err or not resolved_path:
                rec["final_status"] = "UNRESOLVABLE_URL"
                rec["notes"] = err or "Could not parse URL"
            else:
                rec["resolved_local_path"] = str(resolved_path)
                if not resolved_path.is_file():
                    rec["final_status"] = "MISSING_FILE"
                    rec["notes"] = f"File missing on disk: {resolved_path}"
                else:
                    rec["file_exists"] = True
                    resolved_disk_paths.add(resolved_path.resolve())
                    try:
                        size = resolved_path.stat().st_size
                        comp_hash = compute_sha256(resolved_path)
                        rec["file_size"] = size
                        rec["computed_sha256"] = comp_hash
                        rec["disk_hash_match"] = (comp_hash == db_hash)
                        if not rec["disk_hash_match"]:
                            rec["final_status"] = "HASH_MISMATCH"
                            rec["notes"] = f"Disk SHA-256 ({comp_hash}) != DB hash ({db_hash})"
                    except Exception as e:
                        rec["final_status"] = "UNRESOLVABLE_URL"
                        rec["notes"] = f"Error reading local file: {e}"
        elif url_type == "supabase":
            rec["final_status"] = "UNRESOLVABLE_URL"
            rec["notes"] = "Supabase remote URL (not resolvable to local disk in Phase 2A)"
        else:
            rec["final_status"] = "UNRESOLVABLE_URL"
            rec["notes"] = f"Unresolvable file_url classification: {url_type}"

        # On-chain read-only check
        chain_st, on_chain_h, chain_err = check_chain_registration(ev_id, rpc_is_alive)
        rec["chain_status"] = chain_st
        rec["on_chain_hash"] = on_chain_h

        if chain_st == "CHAIN_UNREACHABLE":
            # If the file had no prior critical failure (MISSING_FILE, HASH_MISMATCH, UNRESOLVABLE_URL),
            # mark final_status as CHAIN_UNREACHABLE
            if rec["final_status"] in ("UNKNOWN", "OK"):
                rec["final_status"] = "CHAIN_UNREACHABLE"
            rec["notes"] = (rec["notes"] + " | " if rec["notes"] else "") + f"Chain unreachable: {chain_err}"
        elif chain_st == "NOT_REGISTERED":
            if rec["final_status"] in ("UNKNOWN", "OK"):
                rec["final_status"] = "CHAIN_MISMATCH"
            rec["notes"] = (rec["notes"] + " | " if rec["notes"] else "") + "Not registered on smart contract"
        elif chain_st == "REACHABLE":
            matches = (on_chain_h == db_hash)
            rec["chain_hash_match"] = matches
            if not matches:
                if rec["final_status"] in ("UNKNOWN", "OK"):
                    rec["final_status"] = "CHAIN_MISMATCH"
                rec["notes"] = (rec["notes"] + " | " if rec["notes"] else "") + f"On-chain hash ({on_chain_h}) != DB hash ({db_hash})"
            else:
                if rec["final_status"] == "UNKNOWN":
                    rec["final_status"] = "OK"

        status_counts[rec["final_status"]] = status_counts.get(rec["final_status"], 0) + 1
        inventory.append(rec)

    db.close()

    # 2. Discover orphan files in backend/uploads
    disk_files = []
    orphan_files = []
    disk_hash_map = {}

    if UPLOADS_DIR.is_dir():
        for f in UPLOADS_DIR.rglob("*"):
            if f.is_file():
                f_resolved = f.resolve()
                f_size = f.stat().st_size
                f_hash = compute_sha256(f)
                rel_path = str(f.relative_to(UPLOADS_DIR)).replace("\\", "/")
                
                disk_files.append({
                    "relative_path": rel_path,
                    "size": f_size,
                    "sha256": f_hash
                })
                disk_hash_map.setdefault(f_hash, []).append(rel_path)

                if f_resolved not in resolved_disk_paths:
                    orphan_files.append({
                        "relative_path": rel_path,
                        "size": f_size,
                        "sha256": f_hash
                    })

    # 3. Identify duplicate hashes
    duplicate_db_hashes = {h: rows for h, rows in hash_to_rows.items() if len(rows) > 1}
    duplicate_disk_hashes = {h: paths for h, paths in disk_hash_map.items() if len(paths) > 1}

    # 4. Write JSON and CSV reports
    json_path = BACKUPS_DIR / f"migration_dryrun_{ts}.json"
    csv_path = BACKUPS_DIR / f"migration_dryrun_{ts}.csv"

    dryrun_data = {
        "timestamp_utc": ts,
        "total_evidence_rows": len(evidence_rows),
        "url_classification_counts": url_counts,
        "final_status_counts": status_counts,
        "total_disk_files": len(disk_files),
        "total_orphan_files": len(orphan_files),
        "duplicate_db_hash_count": len(duplicate_db_hashes),
        "duplicate_disk_hash_count": len(duplicate_disk_hashes),
        "inventory": inventory,
        "orphan_files": orphan_files,
        "duplicate_db_hashes": duplicate_db_hashes,
        "duplicate_disk_hashes": duplicate_disk_hashes,
    }

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(dryrun_data, f, indent=2)

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        fieldnames = [
            "evidence_id", "case_id", "file_name", "url_type", "final_status",
            "file_exists", "file_size", "disk_hash_match", "chain_status",
            "chain_hash_match", "db_file_hash", "computed_sha256", "on_chain_hash",
            "file_url", "resolved_local_path", "notes"
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in inventory:
            writer.writerow({k: row.get(k) for k in fieldnames})

    # 5. Print summary counts and problem rows
    print("\n" + "=" * 80)
    print("DRY-RUN SUMMARY COUNTS")
    print("=" * 80)
    print(f"Total Evidence Rows in DB: {len(evidence_rows)}")
    print(f"URL Classifications: {json.dumps(url_counts)}")
    print("Status Counts:")
    for status, count in status_counts.items():
        print(f"  {status:20}: {count}")
    print(f"\nTotal Files on Disk in backend/uploads : {len(disk_files)}")
    print(f"Orphan Files (on disk, no DB row)     : {len(orphan_files)}")
    print(f"Duplicate DB Hashes                   : {len(duplicate_db_hashes)}")
    print(f"Duplicate Disk Hashes                 : {len(duplicate_disk_hashes)}")

    if orphan_files:
        print("\n--- ORPHAN FILES ON DISK ---")
        for o in orphan_files:
            print(f"  {o['relative_path']} ({o['size']} bytes, {o['sha256'][:16]}...)")

    if duplicate_db_hashes:
        print("\n--- DUPLICATE HASHES IN DATABASE ---")
        for h, ids in duplicate_db_hashes.items():
            print(f"  SHA-256: {h} -> IDs: {ids}")

    problem_rows = [r for r in inventory if r["final_status"] != "OK"]
    print(f"\nTotal Non-OK Evidence Rows: {len(problem_rows)}")
    if problem_rows:
        print("Problem Rows (IDs and Status only):")
        for p in problem_rows:
            print(f"  ID: {p['evidence_id']} | Status: {p['final_status']} | URL Type: {p['url_type']} | Note: {p['notes']}")

    print("\n" + "=" * 80)
    print(f"Dry-run report saved to:")
    print(f"  JSON: {json_path}")
    print(f"  CSV : {csv_path}")
    print("=" * 80)


if __name__ == "__main__":
    run_dryrun()
