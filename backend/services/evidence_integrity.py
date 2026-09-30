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
