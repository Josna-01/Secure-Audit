"""Unit tests for the evidence integrity rules (no database or blockchain needed).

Run from the backend directory:  python -m unittest tests.test_evidence_integrity
"""
import os
import sys
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services import evidence_integrity as integrity  # noqa: E402
from services.blockchain_service import hex_variants, is_sha256_hex, normalize_hex  # noqa: E402

HASH_A = "a" * 64
HASH_B = "b" * 64


def evidence(**overrides):
    base = dict(file_hash=HASH_A, file_name="knife.jpg", case_id="case-1", blockchain_tx_hash="ab" * 32,
                blockchain_block_number=7, blockchain_contract_address="0xAbC0000000000000000000000000000000000001",
                blockchain_registered_at=datetime(2026, 9, 30, tzinfo=timezone.utc))
    base.update(overrides)
    return SimpleNamespace(**base)


def registration(**overrides):
    base = dict(sha256Hash=HASH_A, fileName="knife.jpg", caseId="case-1")
    base.update(overrides)
    return base


RECEIPT = {"blockNumber": 7, "contractAddress": "0xabc0000000000000000000000000000000000001"}


def by_code(checks):
    return {check["code"]: check for check in checks}


class HexHelpersTest(unittest.TestCase):
    def test_sha256_format(self):
        self.assertTrue(is_sha256_hex(HASH_A))
        self.assertFalse(is_sha256_hex(HASH_A.upper()))
        self.assertFalse(is_sha256_hex(HASH_A[:-1]))
        self.assertFalse(is_sha256_hex(None))

    def test_normalize_and_variants(self):
        self.assertEqual(normalize_hex("0xABcd"), "abcd")
        self.assertEqual(normalize_hex(b"\x01\x02"), "0102")
        self.assertEqual(hex_variants("0xAB"), ["ab", "0xab"])


class IntegrityChecksTest(unittest.TestCase):
    def test_consistent_record(self):
        checks = integrity.integrity_checks(evidence(), registration(), RECEIPT, [], file_hash=HASH_A)
        self.assertEqual(integrity.integrity_summary(checks), "Consistent")

    def test_database_hash_altered(self):
        checks = by_code(integrity.integrity_checks(evidence(file_hash=HASH_B), registration(), RECEIPT, []))
        self.assertFalse(checks["DB_MATCHES_CHAIN"]["ok"])

    def test_file_tampered(self):
        checks = by_code(integrity.integrity_checks(evidence(), registration(), RECEIPT, [], file_hash=HASH_B))
        self.assertFalse(checks["FILE_MATCHES_CHAIN"]["ok"])

    def test_record_fields_modified(self):
        checks = by_code(integrity.integrity_checks(evidence(file_name="renamed.jpg"), registration(), RECEIPT, []))
        self.assertFalse(checks["DB_RECORD_UNCHANGED"]["ok"])

    def test_transaction_missing_on_chain(self):
        checks = by_code(integrity.integrity_checks(evidence(), registration(), None, []))
        self.assertFalse(checks["TRANSACTION_ON_CHAIN"]["ok"])

    def test_unknown_receipt_skips_transaction_checks(self):
        checks = by_code(integrity.integrity_checks(evidence(), registration(), None, [], receipt_known=False))
        self.assertNotIn("TRANSACTION_ON_CHAIN", checks)

    def test_missing_metadata_and_duplicates(self):
        checks = by_code(integrity.integrity_checks(evidence(blockchain_block_number=None), registration(), RECEIPT, ["x"]))
        self.assertFalse(checks["METADATA_COMPLETE"]["ok"])
        self.assertFalse(checks["UNIQUE_HASH"]["ok"])
        self.assertEqual(integrity.integrity_summary(list(checks.values())), "Warning")

    def test_unregistered(self):
        checks = integrity.integrity_checks(evidence(blockchain_tx_hash=None), None, None, [])
        self.assertEqual(integrity.integrity_summary(checks), "Inconsistent")


class AuditStatusTest(unittest.TestCase):
    def test_labels(self):
        self.assertEqual(integrity.audit_status(integrity.AUDIT_EVIDENCE_TAMPERED), "Warning")
        self.assertEqual(integrity.audit_status(integrity.AUDIT_VERIFICATION_FAILED), "Failed")
        self.assertEqual(integrity.audit_status("Login Successful"), "Success")


if __name__ == "__main__":
    unittest.main()
