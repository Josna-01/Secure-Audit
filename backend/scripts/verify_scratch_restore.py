#!/usr/bin/env python3
"""
Test Scratch Restoration and Row-Count Verification (Phase 2A Task 1)
"""

import os
import sys
import json
import subprocess
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from pathlib import Path
from dotenv import load_dotenv

SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent
PROJECT_ROOT = BACKEND_DIR.parent
load_dotenv(BACKEND_DIR / ".env")

DB_USER = os.getenv("DB_USER", "postgres")
DB_PASS = os.getenv("DB_PASSWORD", "postgres")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
LIVE_DB = os.getenv("DB_NAME", "secure_audit")
SCRATCH_DB = "secure_audit_scratch_restore"

BACKUP_SQL = PROJECT_ROOT / "backups" / "secure_audit_backup_20261015_154152.sql"
SNAPSHOT_JSON = PROJECT_ROOT / "backups" / "evidence_blockchain_snapshot_20261015.json"


def main():
    print("=" * 80)
    print("TASK 1: POSTGRESQL SCRATCH RESTORE & VERIFICATION")
    print("=" * 80)

    # 1. Connect to maintenance db 'postgres'
    conn = psycopg2.connect(
        dbname="postgres",
        user=DB_USER,
        password=DB_PASS,
        host=DB_HOST,
        port=DB_PORT
    )
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cur = conn.cursor()

    # Drop scratch database if exists
    print(f"Ensuring scratch database '{SCRATCH_DB}' is clean...")
    cur.execute(f"DROP DATABASE IF EXISTS {SCRATCH_DB};")
    cur.execute(f"CREATE DATABASE {SCRATCH_DB};")
    print(f"Scratch database '{SCRATCH_DB}' created successfully.")
    cur.close()
    conn.close()

    # 2. Restore backup SQL into scratch database
    print(f"Restoring backup SQL '{BACKUP_SQL.name}' into '{SCRATCH_DB}'...")
    env = os.environ.copy()
    env["PGPASSWORD"] = DB_PASS
    cmd = [
        "psql",
        "-h", DB_HOST,
        "-p", DB_PORT,
        "-U", DB_USER,
        "-d", SCRATCH_DB,
        "-f", str(BACKUP_SQL)
    ]
    res = subprocess.run(cmd, env=env, capture_output=True, text=True)
    if res.returncode != 0:
        print(f"Restore stderr: {res.stderr[:500]}")
    else:
        print("psql restore execution completed successfully.")

    # 3. Query table row counts from Live DB and Scratch DB
    tables = [
        "audit_logs",
        "blockchain_logs",
        "bns_predictions",
        "cases",
        "detections",
        "evidence",
        "evidence_custody_records",
        "ocr_results",
        "otp_tokens",
        "photogrammetry_models",
        "users"
    ]

    live_conn = psycopg2.connect(dbname=LIVE_DB, user=DB_USER, password=DB_PASS, host=DB_HOST, port=DB_PORT)
    live_cur = live_conn.cursor()

    scratch_conn = psycopg2.connect(dbname=SCRATCH_DB, user=DB_USER, password=DB_PASS, host=DB_HOST, port=DB_PORT)
    scratch_cur = scratch_conn.cursor()

    print("\n" + "=" * 80)
    print(f"{'Table Name':<30} | {'Live DB':<10} | {'Restored Scratch DB':<20} | {'Status':<10}")
    print("-" * 80)

    discrepancies = False
    live_counts = {}
    scratch_counts = {}

    for t in tables:
        live_cur.execute(f"SELECT count(*) FROM {t};")
        l_cnt = live_cur.fetchone()[0]
        live_counts[t] = l_cnt

        scratch_cur.execute(f"SELECT count(*) FROM {t};")
        s_cnt = scratch_cur.fetchone()[0]
        scratch_counts[t] = s_cnt

        st = "MATCH" if l_cnt == s_cnt else "MISMATCH"
        if l_cnt != s_cnt:
            discrepancies = True
        print(f"{t:<30} | {l_cnt:<10} | {s_cnt:<20} | {st:<10}")

    print("=" * 80)

    # 4. Compare with evidence_blockchain_snapshot_20261015.json
    snapshot = json.load(open(SNAPSHOT_JSON, encoding="utf-8"))
    print("\nComparison against snapshot JSON:")
    for k in ["evidence", "evidence_custody_records", "blockchain_logs"]:
        snap_cnt = len(snapshot.get(k, []))
        print(f"  {k}: Live={live_counts.get(k)}, Scratch={scratch_counts.get(k)}, Snapshot={snap_cnt}")

    # Verify ID match for evidence
    live_cur.execute("SELECT id FROM evidence ORDER BY id;")
    live_ids = set(str(r[0]) for r in live_cur.fetchall())

    scratch_cur.execute("SELECT id FROM evidence ORDER BY id;")
    scratch_ids = set(str(r[0]) for r in scratch_cur.fetchall())

    snap_ids = set(r["id"] for r in snapshot.get("evidence", []))

    print(f"\nEvidence ID Sets match (Live vs Scratch): {live_ids == scratch_ids}")
    print(f"Evidence ID Sets match (Live vs Snapshot): {live_ids == snap_ids}")

    live_conn.close()
    scratch_conn.close()

if __name__ == "__main__":
    main()
