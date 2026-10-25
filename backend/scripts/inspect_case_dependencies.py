#!/usr/bin/env python3
"""
Inspect per-case dependencies across all relational tables.
"""

import os
from pathlib import Path
from dotenv import load_dotenv
import psycopg2

SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent
load_dotenv(BACKEND_DIR / ".env")


conn = psycopg2.connect(
    dbname=os.getenv("DB_NAME", "secure_audit"),
    user=os.getenv("DB_USER", "postgres"),
    password=os.getenv("DB_PASSWORD", "postgres"),
    host=os.getenv("DB_HOST", "localhost"),
    port=os.getenv("DB_PORT", "5432")
)
cur = conn.cursor()

cur.execute("SELECT id, case_number, title FROM cases ORDER BY created_at;")
cases = cur.fetchall()

header = f"{'Case Number':<12} | {'Evidence':<8} | {'Custody':<8} | {'BC Logs':<8} | {'OCR':<6} | {'YOLO':<6} | {'3D':<6} | {'BNS':<6} | {'Audit':<6} | Title"
print(header)
print("-" * 115)

totals = {
    "evidence": 0, "custody": 0, "bc_logs": 0, "ocr": 0,
    "detections": 0, "models": 0, "bns": 0, "audit": 0
}

for cid, cnum, title in cases:
    cur.execute("SELECT count(*) FROM evidence WHERE case_id = %s;", (cid,))
    ev_cnt = cur.fetchone()[0]
    totals["evidence"] += ev_cnt

    cur.execute("SELECT count(*) FROM evidence_custody_records WHERE evidence_id IN (SELECT id FROM evidence WHERE case_id = %s);", (cid,))
    cust_cnt = cur.fetchone()[0]
    totals["custody"] += cust_cnt

    cur.execute("SELECT count(*) FROM blockchain_logs WHERE evidence_id IN (SELECT id FROM evidence WHERE case_id = %s);", (cid,))
    bc_cnt = cur.fetchone()[0]
    totals["bc_logs"] += bc_cnt

    cur.execute("SELECT count(*) FROM ocr_results WHERE evidence_id IN (SELECT id FROM evidence WHERE case_id = %s);", (cid,))
    ocr_cnt = cur.fetchone()[0]
    totals["ocr"] += ocr_cnt

    cur.execute("SELECT count(*) FROM detections WHERE case_id = %s;", (cid,))
    yolo_cnt = cur.fetchone()[0]
    totals["detections"] += yolo_cnt

    cur.execute("SELECT count(*) FROM photogrammetry_models WHERE case_id = %s;", (cid,))
    model_cnt = cur.fetchone()[0]
    totals["models"] += model_cnt

    cur.execute("SELECT count(*) FROM bns_predictions WHERE case_id = %s;", (cid,))
    bns_cnt = cur.fetchone()[0]
    totals["bns"] += bns_cnt

    cur.execute("SELECT count(*) FROM audit_logs WHERE case_id = %s;", (cid,))
    audit_cnt = cur.fetchone()[0]
    totals["audit"] += audit_cnt

    line = f"{cnum:<12} | {ev_cnt:<8} | {cust_cnt:<8} | {bc_cnt:<8} | {ocr_cnt:<6} | {yolo_cnt:<6} | {model_cnt:<6} | {bns_cnt:<6} | {audit_cnt:<6} | {title}"
    print(line)

print("-" * 115)
summary_line = f"{'TOTALS':<12} | {totals['evidence']:<8} | {totals['custody']:<8} | {totals['bc_logs']:<8} | {totals['ocr']:<6} | {totals['detections']:<6} | {totals['models']:<6} | {totals['bns']:<6} | {totals['audit']:<6} |"
print(summary_line)

# Also check orphans not tied to any case
cur.execute("SELECT count(*) FROM blockchain_logs WHERE evidence_id IS NULL;")
orphan_bc = cur.fetchone()[0]
cur.execute("SELECT count(*) FROM ocr_results WHERE evidence_id IS NULL;")
orphan_ocr = cur.fetchone()[0]
cur.execute("SELECT count(*) FROM audit_logs WHERE case_id IS NULL;")
orphan_audit = cur.fetchone()[0]
print("\nRecords not tied to any case:")
print(f"  blockchain_logs (evidence_id IS NULL): {orphan_bc}")
print(f"  ocr_results (evidence_id IS NULL)    : {orphan_ocr}")
print(f"  audit_logs (case_id IS NULL)         : {orphan_audit}")

conn.close()
