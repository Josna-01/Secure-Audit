"""
Secure Audit — Phase 1 Security Migration:
1. Adds is_archived to cases table (enables soft-archival over destructive deletion).
2. Updates foreign key constraints on forensic evidence, custody, blockchain, detection,
   OCR, and audit log tables from ON DELETE CASCADE to ON DELETE RESTRICT.
"""
import os
import sys
from dotenv import load_dotenv

# Ensure backend directory is in path
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

load_dotenv(os.path.join(CURRENT_DIR, ".env"))

from db import SessionLocal, text

STATEMENTS = [
    # 1. Soft-archival support for cases
    "ALTER TABLE cases ADD COLUMN IF NOT EXISTS is_archived BOOLEAN NOT NULL DEFAULT FALSE;",
    "CREATE INDEX IF NOT EXISTS idx_cases_is_archived ON cases(is_archived);",

    # 2. Evidence foreign key to cases: ON DELETE RESTRICT
    "ALTER TABLE evidence DROP CONSTRAINT IF EXISTS fk_evidence_case_id;",
    "ALTER TABLE evidence ADD CONSTRAINT fk_evidence_case_id FOREIGN KEY (case_id) REFERENCES cases(id) ON DELETE RESTRICT;",

    # 3. Audit logs foreign key to cases: ON DELETE RESTRICT
    "ALTER TABLE audit_logs DROP CONSTRAINT IF EXISTS fk_audit_logs_case_id;",
    "ALTER TABLE audit_logs ADD CONSTRAINT fk_audit_logs_case_id FOREIGN KEY (case_id) REFERENCES cases(id) ON DELETE RESTRICT;",

    # 4. Custody records foreign key to evidence: ON DELETE RESTRICT
    "ALTER TABLE evidence_custody_records DROP CONSTRAINT IF EXISTS evidence_custody_records_evidence_id_fkey;",
    "ALTER TABLE evidence_custody_records ADD CONSTRAINT evidence_custody_records_evidence_id_fkey FOREIGN KEY (evidence_id) REFERENCES evidence(id) ON DELETE RESTRICT;",

    # 5. Blockchain logs foreign key to evidence: ON DELETE RESTRICT
    "ALTER TABLE blockchain_logs DROP CONSTRAINT IF EXISTS blockchain_logs_evidence_id_fkey;",
    "ALTER TABLE blockchain_logs ADD CONSTRAINT blockchain_logs_evidence_id_fkey FOREIGN KEY (evidence_id) REFERENCES evidence(id) ON DELETE RESTRICT;",

    # 6. Detections foreign keys: ON DELETE RESTRICT
    "ALTER TABLE detections DROP CONSTRAINT IF EXISTS fk_detections_case_id;",
    "ALTER TABLE detections ADD CONSTRAINT fk_detections_case_id FOREIGN KEY (case_id) REFERENCES cases(id) ON DELETE RESTRICT;",
    "ALTER TABLE detections DROP CONSTRAINT IF EXISTS fk_detections_evidence_id;",
    "ALTER TABLE detections ADD CONSTRAINT fk_detections_evidence_id FOREIGN KEY (evidence_id) REFERENCES evidence(id) ON DELETE RESTRICT;",

    # 7. OCR Results foreign key: ON DELETE RESTRICT
    "ALTER TABLE ocr_results DROP CONSTRAINT IF EXISTS fk_ocr_results_evidence_id;",
    "ALTER TABLE ocr_results ADD CONSTRAINT fk_ocr_results_evidence_id FOREIGN KEY (evidence_id) REFERENCES evidence(id) ON DELETE RESTRICT;",

    # 8. BNS Predictions foreign key: ON DELETE RESTRICT
    "ALTER TABLE bns_predictions DROP CONSTRAINT IF EXISTS fk_bns_predictions_case_id;",
    "ALTER TABLE bns_predictions ADD CONSTRAINT fk_bns_predictions_case_id FOREIGN KEY (case_id) REFERENCES cases(id) ON DELETE RESTRICT;",

    # 9. Photogrammetry models foreign keys: ON DELETE RESTRICT
    "ALTER TABLE photogrammetry_models DROP CONSTRAINT IF EXISTS fk_photogrammetry_models_case_id;",
    "ALTER TABLE photogrammetry_models ADD CONSTRAINT fk_photogrammetry_models_case_id FOREIGN KEY (case_id) REFERENCES cases(id) ON DELETE RESTRICT;",
    "ALTER TABLE photogrammetry_models DROP CONSTRAINT IF EXISTS fk_photogrammetry_models_evidence_id;",
    "ALTER TABLE photogrammetry_models ADD CONSTRAINT fk_photogrammetry_models_evidence_id FOREIGN KEY (evidence_id) REFERENCES evidence(id) ON DELETE RESTRICT;"
]

def run_migration():
    print("[MIGRATION] Starting Phase 1 Security Schema Hardening...")
    session = SessionLocal()
    try:
        for stmt in STATEMENTS:
            session.execute(text(stmt))
        session.commit()
        print("[MIGRATION SUCCESS] Successfully updated schema with ON DELETE RESTRICT and is_archived.")
    except Exception as e:
        session.rollback()
        print(f"[MIGRATION FAILED] Error applying statements: {e}")
        sys.exit(1)
    finally:
        session.close()

if __name__ == "__main__":
    run_migration()
