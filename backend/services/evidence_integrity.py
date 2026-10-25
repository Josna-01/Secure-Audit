"""Evidence integrity vocabulary and database-vs-blockchain consistency checks.

Kept free of FastAPI and SQLAlchemy so the rules can be unit-tested directly.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from services.blockchain_service import is_sha256_hex, normalize_hex


# ── Verification outcomes ──────────────────────────────────────────────────────
# Verified / Tampered / Missing / Unregistered describe the evidence and are stored
# in ``evidence.status``. "Verification Failed" describes the attempt (an outage);
# it is stored only in ``evidence.last_verification_result`` so an outage can never
# overwrite a real integrity state.
VERIFIED = "Verified"
TAMPERED = "Tampered"
MISSING = "Missing"
UNREGISTERED = "Unregistered"
VERIFICATION_FAILED = "Verification Failed"
EVIDENCE_STATES = (VERIFIED, TAMPERED, MISSING, UNREGISTERED)

# Machine-readable reasons returned by the verification API.
REASONS = {
    "HASH_MATCH": "The stored file matches the hash registered on the blockchain.",
    "HASH_MISMATCH": "The stored file's SHA-256 differs from the hash registered on the blockchain.",
    "EVIDENCE_MISSING": "The evidence file no longer exists in storage.",
    "NOT_REGISTERED": "The evidence has no registration on the blockchain.",
    "TRANSACTION_MISSING": "The registration transaction recorded in the database was not found on the blockchain.",
    "DATABASE_MISMATCH": "The hash in the database differs from the hash registered on the blockchain.",
    "BLOCKCHAIN_UNAVAILABLE": "The blockchain node could not be reached; integrity was not checked.",
    "STORAGE_UNAVAILABLE": "Evidence storage could not be read; integrity was not checked.",
    "TRANSACTION_FAILED": "The verification transaction could not be completed.",
    "BYTE_HASH_MISMATCH": "The calculated SHA-256 of the actual evidence bytes differs from the expected hash.",
    "METADATA_MISMATCH": "The hash reported by storage metadata differs from the calculated byte hash.",
    "OBJECT_UNREADABLE": "The evidence object in storage could not be read or streamed.",
}

# ── Audit actions ──────────────────────────────────────────────────────────────
# "Evidence Upload", "Hash Verified" and "Tamper Detected" predate this module and the
# frontend (dashboard, profile, audit page) filters on those exact strings, so they
# stay; the rest follow the blockchain action names.
AUDIT_EVIDENCE_UPLOADED = "Evidence Upload"
AUDIT_EVIDENCE_REGISTERED = "Evidence Registered"
AUDIT_EVIDENCE_VERIFIED = "Hash Verified"
AUDIT_EVIDENCE_TAMPERED = "Tamper Detected"
AUDIT_EVIDENCE_MISSING = "Evidence Missing"
AUDIT_EVIDENCE_UNREGISTERED = "Evidence Not Registered On-Chain"
AUDIT_VERIFICATION_FAILED = "Verification Failed"
AUDIT_REGISTRATION_FAILED = "Blockchain Registration Failed"
AUDIT_DB_HASH_MISMATCH = "Database Hash Mismatch"
AUDIT_INTEGRITY_INCONSISTENCY = "Integrity Inconsistency Detected"
AUDIT_DUPLICATE_HASH = "Duplicate Evidence Hash Detected"
AUDIT_EVIDENCE_VIEWED = "Evidence Viewed"
AUDIT_EVIDENCE_DOWNLOADED = "Evidence Downloaded"
AUDIT_EVIDENCE_MODIFIED = "Evidence Metadata Modified"
AUDIT_EVIDENCE_DELETED = "Evidence Deleted"
AUDIT_CUSTODY_TRANSFERRED = "Evidence Custody Transferred"
AUDIT_METADATA_BACKFILLED = "Blockchain Metadata Backfilled"
AUDIT_UNAUTHORISED = "Unauthorised Blockchain Action"

ALERT_ACTIONS = {AUDIT_EVIDENCE_TAMPERED, AUDIT_EVIDENCE_MISSING, AUDIT_DB_HASH_MISMATCH,
                 AUDIT_INTEGRITY_INCONSISTENCY, AUDIT_UNAUTHORISED}
FAILURE_ACTIONS = {AUDIT_VERIFICATION_FAILED, AUDIT_REGISTRATION_FAILED, AUDIT_EVIDENCE_UNREGISTERED}

# ── Custody actions ────────────────────────────────────────────────────────────
# On-chain (contract-enforced): REGISTERED, VERIFIED, TRANSFERRED.
# Off-chain (database only, source="database"): the rest.
CUSTODY_CREATED = "CREATED"
CUSTODY_VIEWED = "VIEWED"
CUSTODY_DOWNLOADED = "DOWNLOADED"
CUSTODY_MODIFIED = "METADATA_MODIFIED"
CUSTODY_DELETED = "DELETED"


def audit_status(action: str) -> str:
    """Status label shown on the audit log page."""
    if action in ALERT_ACTIONS:
        return "Warning"
    if action in FAILURE_ACTIONS:
        return "Failed"
    return "Success"


@dataclass
class IntegrityCheck:
    code: str
    ok: bool
    severity: str  # "info" | "warning" | "critical"
    message: str


def integrity_checks(evidence: Any, registration: dict | None, receipt: dict | None,
                     duplicate_ids: list[str], file_hash: str | None = None, receipt_known: bool = True) -> list[dict]:
    """Compare the database record with the on-chain registration.

    ``registration`` is the contract's getEvidence record (None if unregistered),
    ``receipt`` the metadata of the stored registration transaction (None if the chain
    does not know it), and ``file_hash`` the freshly computed file hash when available.
    Pass ``receipt_known=False`` when the receipt lookup itself failed, so the
    transaction checks are skipped rather than reported as missing.
    """
    checks: list[IntegrityCheck] = []
    db_hash = (evidence.file_hash or "").lower()

    checks.append(IntegrityCheck("DB_HASH_FORMAT", is_sha256_hex(db_hash), "critical",
                                 "Database hash is a valid SHA-256 digest" if is_sha256_hex(db_hash)
                                 else "Database hash is missing or not a valid SHA-256 digest"))

    missing = [name for name, value in (("transaction hash", evidence.blockchain_tx_hash),
                                         ("block number", evidence.blockchain_block_number),
                                         ("contract address", evidence.blockchain_contract_address),
                                         ("registration time", evidence.blockchain_registered_at))
               if value in (None, "")]
    checks.append(IntegrityCheck("METADATA_COMPLETE", not missing, "warning",
                                 "Blockchain metadata is complete" if not missing
                                 else "Missing blockchain metadata: " + ", ".join(missing)))

    if registration is None:
        checks.append(IntegrityCheck("REGISTERED", False, "critical", "No registration exists on the blockchain"))
    else:
        chain_hash = registration["sha256Hash"].lower()
        checks.append(IntegrityCheck("REGISTERED", True, "info", "Evidence is registered on the blockchain"))
        checks.append(IntegrityCheck("DB_MATCHES_CHAIN", db_hash == chain_hash, "critical",
                                     "Database hash matches the blockchain hash" if db_hash == chain_hash
                                     else "Database hash differs from the blockchain hash (record may have been altered)"))
        same_name = (evidence.file_name or "") == registration["fileName"]
        same_case = str(evidence.case_id or "") == registration["caseId"]
        checks.append(IntegrityCheck("DB_RECORD_UNCHANGED", same_name and same_case, "critical",
                                     "File name and case match the on-chain registration" if same_name and same_case
                                     else "File name or case in the database differ from the on-chain registration"))
        if file_hash is not None:
            checks.append(IntegrityCheck("FILE_MATCHES_CHAIN", file_hash == chain_hash, "critical",
                                         "Stored file matches the blockchain hash" if file_hash == chain_hash
                                         else "Stored file differs from the blockchain hash"))

    if evidence.blockchain_tx_hash and receipt_known:
        found = receipt is not None
        checks.append(IntegrityCheck("TRANSACTION_ON_CHAIN", found, "critical",
                                     "Registration transaction exists on the blockchain" if found
                                     else "Registration transaction recorded in the database is not on the blockchain"))
        if found and evidence.blockchain_block_number is not None:
            same_block = int(evidence.blockchain_block_number) == int(receipt["blockNumber"])
            checks.append(IntegrityCheck("BLOCK_MATCHES", same_block, "warning",
                                         "Stored block number matches the transaction receipt" if same_block
                                         else "Stored block number differs from the transaction receipt"))
        if found and evidence.blockchain_contract_address:
            same_contract = normalize_hex(evidence.blockchain_contract_address) == normalize_hex(receipt["contractAddress"])
            checks.append(IntegrityCheck("CONTRACT_MATCHES", same_contract, "warning",
                                         "Registration belongs to the active contract" if same_contract
                                         else "Registration was made on a different contract"))

    checks.append(IntegrityCheck("UNIQUE_HASH", not duplicate_ids, "warning",
                                 "No other evidence item has the same SHA-256" if not duplicate_ids
                                 else f"{len(duplicate_ids)} other evidence item(s) share this SHA-256"))
    return [asdict(check) for check in checks]


def integrity_summary(checks: list[dict]) -> str:
    """"Consistent", "Warning" or "Inconsistent" for a list from integrity_checks()."""
    failed = [c for c in checks if not c["ok"]]
    if any(c["severity"] == "critical" for c in failed):
        return "Inconsistent"
    return "Warning" if failed else "Consistent"


def deep_integrity_verification(
    evidence: Any,
    calculated_byte_hash: str | None,
    total_bytes: int | None = None,
    storage_metadata_hash: str | None = None,
    registration: dict | None = None,
    receipt: dict | None = None,
    duplicate_ids: list[str] | None = None,
    blockchain_available: bool = True,
    is_missing: bool = False,
    is_unreadable: bool = False,
    receipt_known: bool = True,
    error_detail: str | None = None,
) -> dict:
    """
    Perform deep forensic integrity verification of an evidence exhibit by comparing:
    1. Calculated byte-stream SHA-256 (read directly from object bytes)
    2. Stored database hash (evidence.file_hash)
    3. Storage provider metadata hash (e.g. x-amz-meta-sha256 in R2/S3), where available
    4. Blockchain on-chain registration hash, where available

    Explicitly distinguishes:
    - Missing objects (does not exist in storage)
    - Unreadable objects (I/O, network, or storage stream errors)
    - Hash mismatches (tampered bytes, corrupted files, or DB alterations)
    - Unavailable blockchain verification (node unreachable, status unchanged)
    - Unregistered evidence (intact in storage, but no on-chain anchor)
    - Verified evidence (all cryptographic layers match)
    """
    duplicate_ids = duplicate_ids or []
    checks: list[IntegrityCheck] = []
    warnings: list[str] = []

    db_hash = (getattr(evidence, "file_hash", "") or "").lower() if getattr(evidence, "file_hash", None) else None
    meta_hash = storage_metadata_hash.lower() if storage_metadata_hash else None
    byte_hash = calculated_byte_hash.lower() if calculated_byte_hash else None
    chain_hash = registration.get("sha256Hash", "").lower() if registration and registration.get("sha256Hash") else None

    # Object existence check
    checks.append(IntegrityCheck(
        code="OBJECT_EXISTS",
        ok=not is_missing,
        severity="critical",
        message="Evidence object exists in storage" if not is_missing else "Evidence object is missing from storage"
    ))

    # Object readability check
    checks.append(IntegrityCheck(
        code="OBJECT_READABLE",
        ok=(not is_missing) and (not is_unreadable),
        severity="critical",
        message="Evidence object bytes readable and streamable" if (not is_missing and not is_unreadable)
        else f"Evidence object could not be read: {error_detail or 'Storage stream error'}"
    ))

    # Missing outcome
    if is_missing:
        return {
            "status": MISSING,
            "reason": "EVIDENCE_MISSING",
            "reason_text": REASONS["EVIDENCE_MISSING"],
            "calculated_byte_hash": None,
            "total_bytes": None,
            "database_hash": db_hash,
            "storage_metadata_hash": meta_hash,
            "blockchain_hash": chain_hash,
            "db_matches_bytes": False,
            "metadata_matches_bytes": None,
            "chain_matches_bytes": None,
            "blockchain_available": blockchain_available,
            "is_missing": True,
            "is_unreadable": False,
            "checks": [asdict(c) for c in checks],
            "warnings": ["Evidence file is missing from storage."],
        }

    # Unreadable outcome
    if is_unreadable:
        return {
            "status": VERIFICATION_FAILED,
            "reason": "STORAGE_UNAVAILABLE",
            "reason_text": REASONS["STORAGE_UNAVAILABLE"],
            "calculated_byte_hash": None,
            "total_bytes": None,
            "database_hash": db_hash,
            "storage_metadata_hash": meta_hash,
            "blockchain_hash": chain_hash,
            "db_matches_bytes": False,
            "metadata_matches_bytes": None,
            "chain_matches_bytes": None,
            "blockchain_available": blockchain_available,
            "is_missing": False,
            "is_unreadable": True,
            "checks": [asdict(c) for c in checks],
            "warnings": [f"Storage read error: {error_detail or 'Unreadable'}"],
        }

    # Format verification
    checks.append(IntegrityCheck(
        code="DB_HASH_FORMAT",
        ok=is_sha256_hex(db_hash),
        severity="critical",
        message="Database hash is a valid SHA-256 digest" if is_sha256_hex(db_hash)
        else "Database hash is missing or not a valid SHA-256 digest"
    ))

    # Deep byte comparison against database
    db_matches_bytes = (db_hash is not None and byte_hash is not None and db_hash == byte_hash)
    checks.append(IntegrityCheck(
        code="DB_MATCHES_BYTES",
        ok=db_matches_bytes,
        severity="critical",
        message="Database recorded hash matches freshly computed byte-stream hash" if db_matches_bytes
        else "Database recorded hash does NOT match calculated byte-stream hash (tampering detected)"
    ))

    # Deep byte comparison against storage metadata (if provider metadata exists)
    metadata_matches_bytes: bool | None = None
    if meta_hash is not None:
        metadata_matches_bytes = (meta_hash == byte_hash)
        checks.append(IntegrityCheck(
            code="METADATA_MATCHES_BYTES",
            ok=metadata_matches_bytes,
            severity="warning" if metadata_matches_bytes else "critical",
            message="Storage metadata SHA-256 matches computed byte-stream hash" if metadata_matches_bytes
            else "Storage metadata SHA-256 differs from computed byte-stream hash (bit rot or out-of-band modification)"
        ))
        if not metadata_matches_bytes:
            warnings.append(
                f"Storage metadata hash ({meta_hash[:16]}...) does not match true byte hash ({byte_hash[:16]}...)."
            )

    # Blockchain evaluation
    chain_matches_bytes: bool | None = None
    if not blockchain_available:
        status = VERIFICATION_FAILED
        reason = "BLOCKCHAIN_UNAVAILABLE"
        warnings.append("Blockchain node unavailable; deep integrity checked against storage and DB only.")
    elif registration is None:
        status = UNREGISTERED
        reason = "NOT_REGISTERED"
        checks.append(IntegrityCheck(
            code="REGISTERED",
            ok=False,
            severity="critical",
            message="No registration exists on the blockchain"
        ))
    else:
        checks.append(IntegrityCheck(
            code="REGISTERED",
            ok=True,
            severity="info",
            message="Evidence is registered on the blockchain"
        ))
        chain_matches_bytes = (chain_hash is not None and byte_hash is not None and chain_hash == byte_hash)
        db_matches_chain = (db_hash is not None and chain_hash is not None and db_hash == chain_hash)

        checks.append(IntegrityCheck(
            code="FILE_MATCHES_CHAIN",
            ok=chain_matches_bytes,
            severity="critical",
            message="Calculated byte hash matches on-chain registration" if chain_matches_bytes
            else "Calculated byte hash differs from on-chain registration (evidence tampered)"
        ))

        checks.append(IntegrityCheck(
            code="DB_MATCHES_CHAIN",
            ok=db_matches_chain,
            severity="critical",
            message="Database hash matches on-chain registration" if db_matches_chain
            else "Database hash differs from on-chain registration (database altered)"
        ))

        same_name = (getattr(evidence, "file_name", "") or "") == registration.get("fileName", "")
        same_case = str(getattr(evidence, "case_id", "") or "") == registration.get("caseId", "")
        checks.append(IntegrityCheck(
            code="DB_RECORD_UNCHANGED",
            ok=same_name and same_case,
            severity="critical",
            message="File name and case match the on-chain registration" if same_name and same_case
            else "File name or case in the database differ from the on-chain registration"
        ))

        if chain_matches_bytes and db_matches_bytes and (metadata_matches_bytes is not False):
            status = VERIFIED
            reason = "HASH_MATCH"
        else:
            status = TAMPERED
            reason = "HASH_MISMATCH"
            if not chain_matches_bytes:
                warnings.append("Calculated byte-stream hash differs from on-chain registered digest.")
            if not db_matches_bytes:
                warnings.append("Calculated byte-stream hash differs from database recorded digest.")
            if metadata_matches_bytes is False:
                warnings.append("Storage metadata hash differs from freshly computed byte digest.")

    # Unique hash check
    checks.append(IntegrityCheck(
        code="UNIQUE_HASH",
        ok=not duplicate_ids,
        severity="warning",
        message="No other evidence item shares this SHA-256" if not duplicate_ids
        else f"{len(duplicate_ids)} other evidence item(s) share this SHA-256"
    ))

    # Transaction metadata check
    if getattr(evidence, "blockchain_tx_hash", None) and receipt_known:
        found = receipt is not None
        checks.append(IntegrityCheck(
            code="TRANSACTION_ON_CHAIN",
            ok=found,
            severity="critical",
            message="Registration transaction exists on the blockchain" if found
            else "Registration transaction recorded in the database is not on the blockchain"
        ))

    return {
        "status": status,
        "reason": reason,
        "reason_text": REASONS.get(reason, reason),
        "calculated_byte_hash": byte_hash,
        "total_bytes": total_bytes,
        "database_hash": db_hash,
        "storage_metadata_hash": meta_hash,
        "blockchain_hash": chain_hash,
        "db_matches_bytes": db_matches_bytes,
        "metadata_matches_bytes": metadata_matches_bytes,
        "chain_matches_bytes": chain_matches_bytes,
        "blockchain_available": blockchain_available,
        "is_missing": False,
        "is_unreadable": False,
        "checks": [asdict(c) for c in checks],
        "warnings": warnings,
    }
