#!/usr/bin/env python3
"""
Turnkey Rollback / Restore Script for Strategy B
Restores the 8 demo cases from archived state and re-inserts all 100 deleted AI outputs from the backup JSON.
"""

import os
import sys
import json
from pathlib import Path
from dotenv import load_dotenv
import psycopg2

SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent
PROJECT_ROOT = BACKEND_DIR.parent
BACKUPS_DIR = PROJECT_ROOT / "backups"

load_dotenv(BACKEND_DIR / ".env")

BACKUP_FILE = BACKUPS_DIR / "disposable_ai_outputs_backup_20261015_124929.json"

def restore():
    print("=" * 80)
    print("ROLLBACK: RESTORING DEMO CASES AND AI OUTPUTS")
    print("=" * 80)

    if not BACKUP_FILE.is_file():
        print(f"ERROR: Backup file not found at {BACKUP_FILE}")
        sys.exit(1)

    with open(BACKUP_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)["records"]

    conn = psycopg2.connect(
        dbname=os.getenv("DB_NAME", "secure_audit"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", "postgres"),
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", "5432")
    )
    conn.autocommit = False
    cur = conn.cursor()

    try:
        # 1. Un-archive cases
        print("Step 1: Setting cases.is_archived = FALSE...")
        cur.execute("UPDATE cases SET is_archived = FALSE;")
        print(f"  Cases un-archived: {cur.rowcount}")

        # 2. Restore detections
        print("Step 2: Restoring detections...")
        for d in data["detections"]:
            cur.execute("""
                INSERT INTO detections (id, case_id, evidence_id, object_type, confidence, bounding_box, detected_at, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s) ON CONFLICT (id) DO NOTHING;
            """, (d["id"], d["case_id"], d["evidence_id"], d["object_type"], d["confidence"], json.dumps(d["bounding_box"]), d["detected_at"], d["created_at"]))
        print(f"  Restored {len(data['detections'])} detections.")

        # 3. Restore photogrammetry models
        print("Step 3: Restoring photogrammetry_models...")
        for m in data["photogrammetry_models"]:
            cur.execute("""
                INSERT INTO photogrammetry_models (id, case_id, evidence_id, model_name, model_file_url, point_cloud_file_url, texture_file_url, camera_poses_file_url, processing_time_seconds, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) ON CONFLICT (id) DO NOTHING;
            """, (m["id"], m["case_id"], m["evidence_id"], m["model_name"], m["model_file_url"], m["point_cloud_file_url"], m["texture_file_url"], m["camera_poses_file_url"], m["processing_time_seconds"], m["created_at"]))
        print(f"  Restored {len(data['photogrammetry_models'])} photogrammetry_models.")

        # 4. Restore bns predictions
        print("Step 4: Restoring bns_predictions...")
        for b in data["bns_predictions"]:
            cur.execute("""
                INSERT INTO bns_predictions (id, case_id, predicted_sections, confidence_scores, explanation, created_at)
                VALUES (%s, %s, %s, %s, %s, %s) ON CONFLICT (id) DO NOTHING;
            """, (b["id"], b["case_id"], json.dumps(b["predicted_sections"]), json.dumps(b["confidence_scores"]), b["explanation"], b["created_at"]))
        print(f"  Restored {len(data['bns_predictions'])} bns_predictions.")

        # 5. Restore case-linked ocr results
        print("Step 5: Restoring case-linked ocr_results...")
        for o in data["ocr_results_case_linked"]:
            cur.execute("""
                INSERT INTO ocr_results (id, evidence_id, extracted_text, language, confidence, page_number, created_at, detected_languages, ocr_metadata)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) ON CONFLICT (id) DO NOTHING;
            """, (o["id"], o["evidence_id"], o["extracted_text"], o["language"], o["confidence"], o["page_number"], o["created_at"], json.dumps(o.get("detected_languages")), json.dumps(o.get("ocr_metadata"))))
        print(f"  Restored {len(data['ocr_results_case_linked'])} ocr_results.")

        conn.commit()
        print("\n" + "=" * 80)
        print("ROLLBACK COMPLETE: All 8 demo cases and AI outputs restored successfully.")
        print("=" * 80)

    except Exception as e:
        conn.rollback()
        print(f"ERROR: Rollback failed and was rolled back: {e}")
        conn.close()
        sys.exit(1)

    conn.close()

if __name__ == "__main__":
    restore()
