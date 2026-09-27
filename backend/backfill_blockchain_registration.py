"""Register legacy evidence on the blockchain (idempotent, dry-run by default).

Evidence uploaded before the blockchain integration (or registered on a
contract that no longer exists after a chain reset) has no valid on-chain
record. For each such item this script:

* re-hashes the stored file;
* registers it when the file still matches the hash recorded at upload;
* adopts an existing on-chain registration when its hash matches the file;
* otherwise marks the evidence ``Unregistered`` (never ``Verified``) and
  records why: file missing, file changed since upload, on-chain hash
  conflict, or blockchain unavailable.

Every outcome writes an audit log entry. Run from the backend directory:

    python backfill_blockchain_registration.py            # dry run: report only
    python backfill_blockchain_registration.py --apply    # perform registrations
"""
import argparse
import hashlib
import os
import sys
import uuid

import requests
from dotenv import load_dotenv

load_dotenv()

from db import SessionLocal  # noqa: E402
from models import AuditLog, BlockchainLog, Evidence, EvidenceCustodyRecord  # noqa: E402
from services.blockchain_service import (BlockchainTransactionError, BlockchainUnavailable,  # noqa: E402
                                         blockchain_service)

UPLOADS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads")
SYSTEM_OFFICER = "system-backfill"


class FileMissing(Exception):
    pass


def file_hash(file_url: str) -> str:
    """SHA-256 of the stored file (same lookup rules as the verify endpoint)."""
    if file_url.startswith(("http://", "https://")) and "/uploads/" not in file_url:
        response = requests.get(file_url, timeout=60)
        if response.status_code == 404 or (response.status_code == 400 and "not_found" in response.text.lower()):
            raise FileMissing("file not found in storage")
        response.raise_for_status()
        return hashlib.sha256(response.content).hexdigest()
    path = (os.path.join(UPLOADS_DIR, file_url.split("/uploads/")[-1].replace("/", os.sep))
            if "/uploads/" in file_url else file_url)
    if not os.path.isfile(path):
        raise FileMissing(f"file not found on disk: {path}")
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(1 << 20):
            digest.update(chunk)
    return digest.hexdigest()


def audit(db, action: str, evidence: Evidence, metadata: dict) -> None:
    db.add(AuditLog(user_id=SYSTEM_OFFICER, action=action, case_id=evidence.case_id, file_hash=evidence.file_hash,
                    metadata_={"evidence_id": str(evidence.id), "source": "backfill_blockchain_registration", **metadata}))


def store_registration(db, evidence: Evidence, receipt: dict, adopted: bool) -> None:
    evidence.blockchain_tx_hash = receipt["transactionHash"]
    evidence.blockchain_block_number = receipt["blockNumber"]
    evidence.blockchain_contract_address = receipt["contractAddress"]
    evidence.blockchain_gas_used = receipt["gasUsed"]
    evidence.blockchain_registered_at = receipt["timestamp"]
    if not adopted:
        db.add(EvidenceCustodyRecord(evidence_id=evidence.id, officer_id=SYSTEM_OFFICER, action="REGISTERED",
                                     occurred_at=receipt["timestamp"], transaction_hash=receipt["transactionHash"],
                                     block_number=receipt["blockNumber"]))
    if not db.query(BlockchainLog.id).filter(BlockchainLog.transaction_hash == receipt["transactionHash"],
                                             BlockchainLog.event_name == "EvidenceRegistered").first():
        db.add(BlockchainLog(evidence_id=evidence.id, event_name="EvidenceRegistered",
                             transaction_hash=receipt["transactionHash"], block_number=receipt["blockNumber"],
                             payload={"contractAddress": receipt["contractAddress"], "gasUsed": receipt["gasUsed"],
                                      "source": "backfill", "adopted": adopted}))


def process(db, evidence: Evidence, apply: bool) -> str:
    """Returns the outcome label for one evidence item."""
    evidence_id = str(evidence.id)

    def unregistered(reason: str, **details) -> str:
        if apply:
            evidence.status = "Unregistered"
            audit(db, "Blockchain Registration Failed", evidence, {"reason": reason, **details})
        return f"UNREGISTERED ({reason})"

    try:
        current_hash = file_hash(evidence.file_url or "")
    except FileMissing as e:
        return unregistered("file missing", detail=str(e))
    except requests.RequestException as e:
        return unregistered("storage unreachable", detail=str(e))

    if evidence.file_hash and evidence.file_hash != current_hash:
        # Registering now would certify a file that changed after upload.
        return unregistered("file changed since upload", database_hash=evidence.file_hash, current_hash=current_hash)

    try:
        existing = blockchain_service.get_registration(evidence_id)
        if existing is not None:
            if existing["sha256Hash"] != current_hash:
                return unregistered("on-chain hash conflicts with file", blockchain_hash=existing["sha256Hash"],
                                    current_hash=current_hash)
            receipt = blockchain_service.find_registration_receipt(evidence_id)
            if receipt is None:
                return unregistered("registration transaction not found")
            if apply:
                store_registration(db, evidence, receipt, adopted=True)
                audit(db, "Blockchain Registration Adopted", evidence, {"transaction_hash": receipt["transactionHash"]})
            return "ADOPTED existing on-chain registration"
        if not apply:
            return "WOULD REGISTER"
        receipt = blockchain_service.register_evidence(evidence_id, str(evidence.case_id or "unassigned"),
                                                       evidence.file_name or evidence_id, current_hash,
                                                       str(evidence.uploaded_by or SYSTEM_OFFICER))
        if not evidence.file_hash:
            evidence.file_hash = current_hash
        store_registration(db, evidence, receipt, adopted=False)
        audit(db, "Blockchain Registration (Backfill)", evidence,
              {"transaction_hash": receipt["transactionHash"], "block_number": receipt["blockNumber"]})
        return f"REGISTERED tx={receipt['transactionHash'][:16]}… block={receipt['blockNumber']}"
    except (BlockchainUnavailable, BlockchainTransactionError) as e:
        return unregistered("blockchain unavailable", detail=str(e)[:300])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--apply", action="store_true", help="perform registrations and status updates")
    args = parser.parse_args()

    try:
        current_contract = blockchain_service.contract_address
    except BlockchainUnavailable as e:
        current_contract = None
        print(f"Blockchain unavailable: {e}")

    db = SessionLocal()
    try:
        candidates = [ev for ev in db.query(Evidence).order_by(Evidence.created_at.asc()).all()
                      if not ev.blockchain_tx_hash
                      or (current_contract and (ev.blockchain_contract_address or "").lower() != current_contract.lower())]
        print(f"{'APPLY' if args.apply else 'DRY RUN'}: {len(candidates)} evidence item(s) without a valid "
              f"registration on contract {current_contract}")
        outcomes = {}
        for evidence in candidates:
            outcome = process(db, evidence, args.apply)
            if args.apply:
                db.commit()  # per item, so one failure never undoes completed on-chain registrations
            key = outcome.split(" (")[0].split(" tx=")[0]
            outcomes[key] = outcomes.get(key, 0) + 1
            print(f"  {evidence.id}  {(evidence.file_name or '')[:40]:40}  {outcome}")
        print("Summary:", ", ".join(f"{k}: {v}" for k, v in outcomes.items()) or "nothing to do")
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
