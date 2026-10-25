"""
Unit and regression tests for Phase 1 Security Hardening:
- Server-side role derivation and RBAC enforcement
- Audit logging resilience & emergency buffer recovery
- Restriction of public uploads
- Model foreign key ON DELETE RESTRICT definitions and is_archived support
"""
import os
import sys
import json
import unittest
import uuid
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import Case, Evidence, AuditLog, Detection, OCRResult, BNSPrediction, EvidenceCustodyRecord, BlockchainLog
import app as main_app


class ModelSecurityConstraintsTest(unittest.TestCase):
    def test_case_has_is_archived_column(self):
        self.assertTrue(hasattr(Case, "is_archived"))
        col = Case.__table__.columns["is_archived"]
        self.assertFalse(col.nullable)

    def test_evidence_foreign_key_is_restrict(self):
        fks = [fk for fk in Evidence.__table__.foreign_keys if fk.column.table.name == "cases"]
        self.assertTrue(len(fks) > 0)
        self.assertEqual(fks[0].ondelete, "RESTRICT")

    def test_audit_logs_foreign_key_is_restrict(self):
        fks = [fk for fk in AuditLog.__table__.foreign_keys if fk.column.table.name == "cases"]
        self.assertTrue(len(fks) > 0)
        self.assertEqual(fks[0].ondelete, "RESTRICT")

    def test_forensic_results_foreign_keys_are_restrict(self):
        # Detections
        det_case_fks = [fk for fk in Detection.__table__.foreign_keys if fk.column.table.name == "cases"]
        self.assertEqual(det_case_fks[0].ondelete, "RESTRICT")
        det_ev_fks = [fk for fk in Detection.__table__.foreign_keys if fk.column.table.name == "evidence"]
        self.assertEqual(det_ev_fks[0].ondelete, "RESTRICT")

        # OCR
        ocr_fks = [fk for fk in OCRResult.__table__.foreign_keys if fk.column.table.name == "evidence"]
        self.assertEqual(ocr_fks[0].ondelete, "RESTRICT")

        # BNS
        bns_fks = [fk for fk in BNSPrediction.__table__.foreign_keys if fk.column.table.name == "cases"]
        self.assertEqual(bns_fks[0].ondelete, "RESTRICT")

        # Custody & Blockchain logs
        custody_fks = [fk for fk in EvidenceCustodyRecord.__table__.foreign_keys if fk.column.table.name == "evidence"]
        self.assertEqual(custody_fks[0].ondelete, "RESTRICT")
        chain_fks = [fk for fk in BlockchainLog.__table__.foreign_keys if fk.column.table.name == "evidence"]
        self.assertEqual(chain_fks[0].ondelete, "RESTRICT")


class AuditResilienceTest(unittest.TestCase):
    def setUp(self):
        self.test_buffer_file = os.path.join(main_app.BACKEND_DIR, "test_audit_buffer.jsonl")
        self.orig_buffer_file = main_app.AUDIT_BUFFER_FILE
        main_app.AUDIT_BUFFER_FILE = self.test_buffer_file
        if os.path.exists(self.test_buffer_file):
            os.remove(self.test_buffer_file)

    def tearDown(self):
        if os.path.exists(self.test_buffer_file):
            os.remove(self.test_buffer_file)
        main_app.AUDIT_BUFFER_FILE = self.orig_buffer_file

    def test_buffer_failed_audit_log_persists_to_disk(self):
        entry = {
            "user_id": "test-user-123",
            "action": "Evidence Integrity Check",
            "case_id": str(uuid.uuid4()),
            "file_hash": "a" * 64,
            "metadata": {"test": True}
        }
        main_app.buffer_failed_audit_log(entry)
        self.assertTrue(os.path.isfile(self.test_buffer_file))
        with open(self.test_buffer_file, "r", encoding="utf-8") as f:
            lines = f.readlines()
        self.assertEqual(len(lines), 1)
        record = json.loads(lines[0])
        self.assertEqual(record["action"], "Evidence Integrity Check")
        self.assertEqual(record["user_id"], "test-user-123")

    def test_write_audit_log_buffers_on_db_exception(self):
        mock_db = MagicMock()
        mock_db.commit.side_effect = Exception("Simulated DB connection failure")

        main_app.write_audit_log(
            user_id="officer-42",
            action="Tamper Alert Triggered",
            case_id=str(uuid.uuid4()),
            file_hash="b" * 64,
            metadata={"alert": "hash_mismatch"},
            db=mock_db
        )

        self.assertTrue(os.path.isfile(self.test_buffer_file))
        with open(self.test_buffer_file, "r", encoding="utf-8") as f:
            lines = f.readlines()
        self.assertEqual(len(lines), 1)
        record = json.loads(lines[0])
        self.assertEqual(record["action"], "Tamper Alert Triggered")
        self.assertEqual(record["user_id"], "officer-42")


class PublicUploadsForbiddenTest(unittest.TestCase):
    def test_uploads_direct_path_returns_403(self):
        from fastapi import HTTPException
        with self.assertRaises(HTTPException) as ctx:
            main_app.forbidden_uploads_access("cases/123/evidence.jpg")
        self.assertEqual(ctx.exception.status_code, 403)
        self.assertIn("Direct public access", ctx.exception.detail)


class ServerSideRoleEnforcementTest(unittest.TestCase):
    def test_investigator_cannot_create_user(self):
        user_info = {"id": str(uuid.uuid4()), "role": "Investigator"}
        self.assertFalse(main_app.has_permission(user_info, "manage_users"))
        self.assertFalse(main_app.is_admin(user_info))

    def test_admin_has_full_permissions(self):
        admin_info = {"id": str(uuid.uuid4()), "role": "Admin"}
        self.assertTrue(main_app.has_permission(admin_info, "manage_users"))
        self.assertTrue(main_app.has_permission(admin_info, "upload_evidence"))
        self.assertTrue(main_app.is_admin(admin_info))


if __name__ == "__main__":
    unittest.main()
