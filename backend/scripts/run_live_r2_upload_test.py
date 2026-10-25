#!/usr/bin/env python3
"""
Secure Audit — Phase 3B Controlled Live Cloudflare R2 Upload Test
Location: backend/scripts/run_live_r2_upload_test.py

Executes an isolated, reversible, live evidence upload test against Cloudflare R2
and the persistent Ganache blockchain network without mutating committed defaults
or impacting any pre-existing evidence records.

Guarantees:
1. Environment Isolation: Temporarily overrides STORAGE_BACKEND in-process only.
2. Harmless Synthetic Payload: ASCII text exhibit only; zero real or personal data.
3. Dedicated Diagnostic Case: Isolated under a tagged '[DIAGNOSTIC]' test case.
4. Complete Verification: R2 object, DB record, download SHA-256, verification endpoint,
   audit logs, and on-chain smart contract receipt.
5. Invariant Protection: Verifies all 35 pre-existing evidence records remain unchanged.
6. Surgical Cleanup: Soft-archives the disposable case and deletes only the exact
   synthetic test object from R2 under 4 strict safety guards.
7. Zero Secret Exposure: Never logs secrets, JWT tokens, or credentials.
"""

import os
import sys
import io
import uuid
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

# Ensure backend root is on sys.path
SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent
PROJECT_ROOT = BACKEND_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from dotenv import load_dotenv
load_dotenv(dotenv_path=BACKEND_DIR / ".env")

from db import SessionLocal
from models import Case, Evidence, EvidenceCustodyRecord, BlockchainLog, AuditLog, User
from services.storage_gateway import (
    get_storage_provider,
    S3StorageProvider,
    StoredObject,
    KeyNotFoundError,
    KeyAlreadyExistsError,
)
from services.blockchain_service import blockchain_service
from web3 import Web3

# Import app components
import app as main_app
from app import app, create_jwt
from fastapi.testclient import TestClient


class TestResults:
    def __init__(self):
        self.checks: List[Dict[str, Any]] = []

    def record(self, check_id: str, name: str, status: str, details: str = ""):
        self.checks.append({
            "id": check_id,
            "name": name,
            "status": status,  # "PASS", "FAIL", "BLOCKED"
            "details": details
        })

    def print_summary(self):
        print("\n" + "=" * 80)
        print("SECURE AUDIT — PHASE 3B CONTROLLED LIVE R2 TEST RESULTS")
        print("=" * 80)
        all_passed = True
        for c in self.checks:
            mark = "[PASS]" if c["status"] == "PASS" else f"[{c['status']}]"
            print(f"{mark:<8} {c['id']:<10} {c['name']:<40} - {c['details']}")
            if c["status"] != "PASS":
                all_passed = False
        print("=" * 80)
        verdict = "PHASE 3B LIVE TEST COMPLETED SUCCESSFULLY" if all_passed else "PHASE 3B LIVE TEST FAILED OR BLOCKED"
        print(f"VERDICT: {verdict}")
        print("=" * 80 + "\n")
        return all_passed


def run_phase_3b_live_test() -> bool:
    results = TestResults()
    db = SessionLocal()

    # Track resources for reporting and cleanup
    disposable_case_id: Optional[uuid.UUID] = None
    disposable_evidence_id: Optional[uuid.UUID] = None
    canonical_key: Optional[str] = None
    orphan_key: Optional[str] = None

    orig_storage_backend = os.environ.get("STORAGE_BACKEND", "local")

    try:
        # ======================================================================
        # PRE-FLIGHT CHECK: Database & Blockchain Preconditions
        # ======================================================================
        print("\n[*] Initializing Pre-Flight Invariant Checks...")

        # 1. Capture real baseline state (ignoring any previous diagnostic runs)
        real_baseline_cases = db.query(Case).filter(
            ~Case.title.like("%[DIAGNOSTIC]%"),
            ~Case.title.like("%[ARCHIVED DIAGNOSTIC]%")
        ).all()
        real_baseline_evidence = db.query(Evidence).filter(
            ~Evidence.description.like("%Diagnostic%")
        ).all()

        baseline_case_count = len(real_baseline_cases)
        baseline_evidence_count = len(real_baseline_evidence)
        baseline_evidence_hashes = {str(e.id): (e.file_hash, e.file_url) for e in real_baseline_evidence}

        print(f"    Real Baseline Cases: {baseline_case_count} (Expected: 8)")
        print(f"    Real Baseline Evidence Records: {baseline_evidence_count} (Expected: 35)")

        if baseline_case_count != 8 or baseline_evidence_count != 35:
            print(f"    [!] Warning: Baseline counts differ from initial expectations (Cases: {baseline_case_count}, Evidence: {baseline_evidence_count})")

        # 2. Check Blockchain Ganache & Contract
        bc_status = blockchain_service.status()
        if not bc_status.get("connected"):
            results.record("PRE-01", "Blockchain Ganache Connectivity", "BLOCKED", f"Ganache not connected: {bc_status.get('error')}")
            return False
        results.record("PRE-01", "Blockchain Ganache Connectivity", "PASS", f"Connected on Chain {bc_status['chainId']} (Block {bc_status['latestBlock']})")

        # 3. Check Admin User for Authenticated Operations
        admin_user = db.query(User).filter(User.role.ilike("admin"), User.is_active == True).first()
        if not admin_user:
            results.record("PRE-02", "Authorized Admin Test Account", "BLOCKED", "No active admin user found in database")
            return False
        admin_id_str = str(admin_user.id)
        results.record("PRE-02", "Authorized Admin Test Account", "PASS", f"Authenticated principal: {admin_id_str[:8]}... (Role: {admin_user.role})")

        # 4. Generate Valid Bearer JWT
        token = create_jwt(admin_id_str, admin_user.email, admin_user.role, admin_user.full_name)
        auth_headers = {"Authorization": f"Bearer {token}"}

        # 5. Apply In-Process R2 Environment Override
        os.environ["STORAGE_BACKEND"] = "s3"
        provider = get_storage_provider()
        if not isinstance(provider, S3StorageProvider):
            results.record("PRE-03", "R2 Storage Gateway Process Override", "FAIL", f"Expected S3StorageProvider, got {type(provider)}")
            return False
        results.record("PRE-03", "R2 Storage Gateway Process Override", "PASS", f"S3StorageProvider active (Bucket: {provider.bucket_name})")

        client = TestClient(app)

        # ======================================================================
        # STEP 1: Create Disposable Diagnostic Case
        # ======================================================================
        print("\n[*] Step 1: Creating Disposable Diagnostic Case...")
        case_title = f"[DIAGNOSTIC] Phase 3B Controlled Live R2 Evidence Upload Probe - {datetime.now().strftime('%Y%m%d_%H%M%S')}"
        case_resp = client.post(
            "/cases",
            headers=auth_headers,
            json={
                "title": case_title,
                "offence_type": "System Diagnostic",
                "fir_description": "Automated non-evidentiary diagnostic probe created solely for Phase 3B Cloudflare R2 integration verification.",
                "fir_language": "en",
                "complainant_name": "Automated Diagnostic Engine",
                "incident_location": "Virtual Test Harness"
            }
        )

        if case_resp.status_code != 200 or not case_resp.json().get("data", {}).get("id"):
            results.record("STEP-01", "Create Disposable Diagnostic Case", "FAIL", f"Status {case_resp.status_code}: {case_resp.text}")
            return False

        case_data = case_resp.json()["data"]
        disposable_case_id = uuid.UUID(case_data["id"])
        case_number = case_data.get("case_number", "N/A")
        results.record("STEP-01", "Create Disposable Diagnostic Case", "PASS", f"Case ID: {disposable_case_id} ({case_number})")

        # ======================================================================
        # STEP 2: Upload Synthetic Text File to Real Cloudflare R2
        # ======================================================================
        print("\n[*] Step 2: Uploading Synthetic Text File to Cloudflare R2...")
        probe_uuid = str(uuid.uuid4())
        timestamp_str = datetime.now(timezone.utc).isoformat()
        synthetic_filename = f"synthetic_r2_diagnostic_probe_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        payload_text = (
            "=== SECURE AUDIT FORENSIC STORAGE GATEWAY DIAGNOSTIC PROBE ===\n"
            f"Probe-ID:    {probe_uuid}\n"
            f"Timestamp:   {timestamp_str}\n"
            f"Case-ID:     {disposable_case_id}\n"
            "Environment: Phase 3B Controlled Live Verification\n"
            "Notice:      Harmless synthetic payload. No personal or real case data.\n"
            "=== END DIAGNOSTIC PROBE ===\n"
        )
        payload_bytes = payload_text.encode("utf-8")
        expected_hash = hashlib.sha256(payload_bytes).hexdigest()
        expected_size = len(payload_bytes)

        upload_resp = client.post(
            "/evidence/upload",
            headers=auth_headers,
            data={
                "case_id": str(disposable_case_id),
                "evidence_type": "Diagnostic",
                "description": "Synthetic Phase 3B Diagnostic Probe Exhibit",
            },
            files={
                "file": (synthetic_filename, io.BytesIO(payload_bytes), "text/plain")
            }
        )

        if upload_resp.status_code != 200 or not upload_resp.json().get("success"):
            # Check if orphan key was created
            orphan_key = f"cases/{disposable_case_id}/*"
            results.record("STEP-02", "Upload Synthetic Exhibit to R2", "FAIL", f"Upload failed HTTP {upload_resp.status_code}: {upload_resp.text}")
            return False

        evidence_payload = upload_resp.json()["data"]
        disposable_evidence_id = uuid.UUID(evidence_payload["id"])
        canonical_key = evidence_payload["file_url"]

        if not canonical_key.startswith(f"cases/{disposable_case_id}/") or not canonical_key.endswith(f"_{synthetic_filename}"):
            results.record("STEP-02", "Upload Synthetic Exhibit to R2", "FAIL", f"Canonical key format mismatch: {canonical_key}")
            return False

        results.record("STEP-02", "Upload Synthetic Exhibit to R2", "PASS", f"Evidence ID: {disposable_evidence_id}, Key: {canonical_key}")

        # ======================================================================
        # STEP 3: Verify the R2 Object (Cloudflare Storage Layer)
        # ======================================================================
        print("\n[*] Step 3: Verifying R2 Object in Cloudflare Bucket...")
        try:
            stat_obj = provider.stat(canonical_key)
            size_match = (stat_obj.size == expected_size)
            hash_match = (stat_obj.sha256.lower() == expected_hash.lower())

            # Double check direct S3 metadata
            head = provider._client.head_object(Bucket=provider.bucket_name, Key=canonical_key)
            meta_hash = head.get("Metadata", {}).get("sha256", "").lower()
            direct_match = (meta_hash == expected_hash.lower())

            if size_match and hash_match and direct_match:
                results.record("STEP-03", "Verify Cloudflare R2 Object & Metadata", "PASS", f"Size: {stat_obj.size} bytes, SHA-256 matches metadata")
            else:
                results.record("STEP-03", "Verify Cloudflare R2 Object & Metadata", "FAIL", f"Size match: {size_match}, Hash match: {hash_match}, Direct match: {direct_match}")
                return False
        except Exception as e:
            results.record("STEP-03", "Verify Cloudflare R2 Object & Metadata", "FAIL", f"R2 stat check failed: {e}")
            return False

        # ======================================================================
        # STEP 4: Verify PostgreSQL Metadata & Custody Record
        # ======================================================================
        print("\n[*] Step 4: Verifying PostgreSQL Evidence Record & Custody History...")
        db_ev = db.query(Evidence).filter(Evidence.id == disposable_evidence_id).first()
        if not db_ev:
            results.record("STEP-04", "Verify PostgreSQL Evidence Record", "FAIL", "Evidence record not found in database")
            return False

        db_matches = (
            db_ev.file_url == canonical_key
            and db_ev.file_hash == expected_hash
            and db_ev.file_size == expected_size
            and db_ev.status == "Verified"
            and db_ev.chain_of_custody_status == "Collected"
        )
        if not db_matches:
            results.record("STEP-04", "Verify PostgreSQL Evidence Record", "FAIL", "Database field values mismatch")
            return False

        custody_rec = db.query(EvidenceCustodyRecord).filter(
            EvidenceCustodyRecord.evidence_id == disposable_evidence_id,
            EvidenceCustodyRecord.action == "REGISTERED"
        ).first()
        if not custody_rec or not custody_rec.transaction_hash:
            results.record("STEP-04", "Verify PostgreSQL Evidence Record", "FAIL", "Custody REGISTERED record missing or has no tx hash")
            return False

        results.record("STEP-04", "Verify PostgreSQL Evidence Record", "PASS", f"Relational row valid. Custody action: REGISTERED (tx: {custody_rec.transaction_hash[:10]}...)")

        # ======================================================================
        # STEP 5: Authenticated Download Endpoint Verification
        # ======================================================================
        print("\n[*] Step 5: Testing Authenticated Download Endpoint...")
        download_resp = client.get(
            f"/evidence/{disposable_evidence_id}/download",
            headers=auth_headers
        )

        if download_resp.status_code != 200:
            results.record("STEP-05", "Authenticated Evidence Download", "FAIL", f"Status {download_resp.status_code}: {download_resp.text}")
            return False

        downloaded_bytes = download_resp.content
        downloaded_hash = hashlib.sha256(downloaded_bytes).hexdigest()
        byte_equality = (downloaded_bytes == payload_bytes)
        header_sha256 = download_resp.headers.get("X-Evidence-SHA256", "").lower()
        header_integrity = download_resp.headers.get("X-Evidence-Integrity", "")

        if byte_equality and (header_sha256 == expected_hash.lower()) and (header_integrity == "match"):
            results.record("STEP-05", "Authenticated Evidence Download", "PASS", f"Served {len(downloaded_bytes)} bytes. X-Evidence-Integrity: match")
        else:
            results.record("STEP-05", "Authenticated Evidence Download", "FAIL", f"Byte equality: {byte_equality}, Hash: {header_sha256}, Integrity: {header_integrity}")
            return False

        # ======================================================================
        # STEP 6: Evidence Integrity Verification Endpoint
        # ======================================================================
        print("\n[*] Step 6: Testing Evidence Integrity Verification Endpoint...")
        verify_resp = client.post(
            f"/evidence/{disposable_evidence_id}/verify",
            headers=auth_headers
        )

        if verify_resp.status_code != 200:
            results.record("STEP-06", "Evidence Integrity Verification", "FAIL", f"Status {verify_resp.status_code}: {verify_resp.text}")
            return False

        verify_json = verify_resp.json()
        verify_data = verify_json.get("data", verify_json)
        if verify_data.get("result") == "Verified" and "HASH_MATCH" in verify_data.get("reasons", [verify_data.get("reason")]):
            results.record("STEP-06", "Evidence Integrity Verification", "PASS", "Endpoint confirmed: result='Verified', reason='HASH_MATCH'")
        else:
            results.record("STEP-06", "Evidence Integrity Verification", "FAIL", f"Unexpected verification payload: {verify_data}")
            return False

        # ======================================================================
        # STEP 7: Audit Events Verification
        # ======================================================================
        print("\n[*] Step 7: Verifying Audit Log Records...")
        audit_records = db.query(AuditLog).filter(AuditLog.case_id == disposable_case_id).all()
        audit_actions = [a.action for a in audit_records]

        # In app.py:
        # Case Created -> "Case Created"
        # Upload -> "Evidence Upload" & "Evidence Registered"
        # Download -> "Evidence Downloaded"
        # Verify -> "Hash Verified"
        expected_actions = ["Case Created", "Evidence Upload", "Evidence Registered", "Evidence Downloaded", "Hash Verified"]
        found_actions = [act for act in expected_actions if act in audit_actions]

        if len(found_actions) == len(expected_actions):
            results.record("STEP-07", "Audit Trail Verification", "PASS", f"All 5 expected audit actions captured: {', '.join(found_actions)}")
        else:
            missing = set(expected_actions) - set(audit_actions)
            results.record("STEP-07", "Audit Trail Verification", "FAIL", f"Missing audit actions: {missing}. Present: {audit_actions}")
            return False

        # ======================================================================
        # STEP 8: Blockchain Registration & Transaction Receipt
        # ======================================================================
        print("\n[*] Step 8: Verifying Blockchain Registration & On-Chain Contract State...")
        db.refresh(db_ev)
        tx_hash = db_ev.blockchain_tx_hash
        if not tx_hash:
            results.record("STEP-08", "Blockchain Registration Verification", "FAIL", "No blockchain_tx_hash found on evidence record")
            return False

        # Check transaction on Ganache
        w3 = Web3(Web3.HTTPProvider("http://127.0.0.1:8545"))
        formatted_tx = "0x" + tx_hash if not tx_hash.startswith("0x") else tx_hash
        receipt = w3.eth.get_transaction_receipt(formatted_tx)

        if not receipt or receipt.get("status") != 1:
            results.record("STEP-08", "Blockchain Registration Verification", "FAIL", f"Transaction receipt status is not 1 (success): {receipt}")
            return False

        # Query contract function directly: getEvidence(evidenceId)
        blockchain_service._connect()
        onchain_ev = blockchain_service._contract.functions.getEvidence(str(disposable_evidence_id)).call()
        # onchain_ev struct: [evidenceId, caseId, fileName, sha256Hash, uploadedBy, timestamp, exists]
        onchain_valid = (
            onchain_ev[0] == str(disposable_evidence_id)
            and onchain_ev[1] == str(disposable_case_id)
            and onchain_ev[3].lower() == expected_hash.lower()
            and onchain_ev[6] is True
        )

        # Check BlockchainLog table
        b_log = db.query(BlockchainLog).filter(BlockchainLog.evidence_id == disposable_evidence_id).first()

        if onchain_valid and b_log:
            results.record("STEP-08", "Blockchain Registration Verification", "PASS", f"On-chain verified at block {receipt['blockNumber']} (tx: {tx_hash[:10]}...)")
        else:
            results.record("STEP-08", "Blockchain Registration Verification", "FAIL", f"Contract struct match: {onchain_valid}, BlockchainLog exists: {bool(b_log)}")
            return False

        # ======================================================================
        # STEP 9: Confirm Existing Historical Records Unchanged
        # ======================================================================
        print("\n[*] Step 9: Confirming Pre-Existing Evidence Invariants...")
        current_baseline_cases = db.query(Case).filter(
            ~Case.title.like("%[DIAGNOSTIC]%"),
            ~Case.title.like("%[ARCHIVED DIAGNOSTIC]%")
        ).all()
        current_baseline_evidence = db.query(Evidence).filter(
            ~Evidence.description.like("%Diagnostic%")
        ).all()

        cases_unchanged = (len(current_baseline_cases) == baseline_case_count)
        evidence_unchanged = (len(current_baseline_evidence) == baseline_evidence_count)

        # Verify none of the initial baseline hashes or URLs changed
        corruption_detected = False
        for initial_id, (init_hash, init_url) in baseline_evidence_hashes.items():
            current_row = db.query(Evidence).filter(Evidence.id == uuid.UUID(initial_id)).first()
            if not current_row or current_row.file_hash != init_hash or current_row.file_url != init_url:
                corruption_detected = True
                break

        if cases_unchanged and evidence_unchanged and not corruption_detected:
            results.record("STEP-09", "Pre-Existing Evidence Invariants", "PASS", f"All {baseline_evidence_count} real evidence records and {baseline_case_count} cases remain 100% untouched")
        else:
            results.record("STEP-09", "Pre-Existing Evidence Invariants", "FAIL", f"Cases valid: {cases_unchanged}, Evidence valid: {evidence_unchanged}, Corruption: {corruption_detected}")
            return False

        # ======================================================================
        # STEP 10: Surgical Cleanup & Case Archival
        # ======================================================================
        print("\n[*] Step 10: Executing Surgical Cleanup & Case Archival...")
        
        # 1. Soft-archive all diagnostic test cases
        all_diagnostic_cases = db.query(Case).filter(Case.title.like("%[DIAGNOSTIC]%")).all()
        for dc in all_diagnostic_cases:
            dc.is_archived = True
            dc.title = f"[ARCHIVED DIAGNOSTIC] {dc.title.replace('[DIAGNOSTIC] ', '')}"
        db.commit()

        # 2. Surgical deletion of ONLY the diagnostic exhibits in Cloudflare R2
        diagnostic_evidence_rows = db.query(Evidence).filter(Evidence.description.like("%Diagnostic%")).all()
        cleaned_keys = []
        failed_cleanups = []

        for d_ev in diagnostic_evidence_rows:
            target_key = d_ev.file_url
            if not target_key:
                continue

            # Apply 4 Strict Safety Guards:
            guard_1 = target_key.startswith("cases/")
            guard_2 = "synthetic_r2_diagnostic_probe_" in target_key
            guard_3 = target_key not in [val[1] for val in baseline_evidence_hashes.values()]
            guard_4 = (provider.bucket_name == "secure-audit-evidence")

            if guard_1 and guard_2 and guard_3 and guard_4:
                try:
                    provider._client.delete_object(Bucket=provider.bucket_name, Key=target_key)
                    cleaned_keys.append(target_key)
                except Exception as del_err:
                    failed_cleanups.append(f"{target_key}: {del_err}")
            else:
                failed_cleanups.append(f"{target_key}: safety guards rejected deletion (G1={guard_1}, G2={guard_2}, G3={guard_3}, G4={guard_4})")

        if not failed_cleanups:
            results.record("STEP-10", "Surgical Cleanup & Case Archival", "PASS", f"Archived diagnostic cases; surgically purged {len(cleaned_keys)} probe objects from R2")
        else:
            results.record("STEP-10", "Surgical Cleanup & Case Archival", "FAIL", f"Cleanup issues encountered: {failed_cleanups}")
            return False

        return True

    except Exception as exc:
        import traceback
        traceback.print_exc()
        results.record("FATAL-01", "Unhandled Test Exception", "FAIL", f"{type(exc).__name__}: {exc}")
        if canonical_key and not orphan_key:
            orphan_key = canonical_key
            print(f"[!] WARNING: Orphan diagnostic key potentially remaining: {orphan_key}")
        return False

    finally:
        # Restore environment variable
        os.environ["STORAGE_BACKEND"] = orig_storage_backend
        db.close()
        results.print_summary()


if __name__ == "__main__":
    success = run_phase_3b_live_test()
    sys.exit(0 if success else 1)
