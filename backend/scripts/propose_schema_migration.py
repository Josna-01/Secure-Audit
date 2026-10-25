#!/usr/bin/env python3
"""
Storage Schema Migration Proposal (Additive, Idempotent, Reversible)
Phase 2A - Storage Gateway & Migration Preparation

RULES:
- This script is PRINT-ONLY. It will NEVER execute against the database.
- It adds nullable columns only.
- It NEVER touches, alters, or drops file_url or file_hash.
"""

import sys

UPGRADE_SQL = """-- ==============================================================================
-- PHASE 2A: ADDITIVE EVIDENCE STORAGE METADATA MIGRATION (UPGRADE)
-- Idempotent, safe, additive. Does NOT alter or drop existing file_url or file_hash.
-- ==============================================================================

DO $$
BEGIN
    -- 1. storage_backend: string indicating provider ('local', 's3', 'supabase')
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'evidence' AND column_name = 'storage_backend'
    ) THEN
        ALTER TABLE evidence ADD COLUMN storage_backend VARCHAR(50) DEFAULT NULL;
        COMMENT ON COLUMN evidence.storage_backend IS 'Underlying storage gateway provider type (local, s3, etc.)';
    END IF;

    -- 2. storage_key: relative canonical object key (e.g. cases/{case_id}/{uuid}_{filename})
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'evidence' AND column_name = 'storage_key'
    ) THEN
        ALTER TABLE evidence ADD COLUMN storage_key TEXT DEFAULT NULL;
        COMMENT ON COLUMN evidence.storage_key IS 'Canonical object storage gateway key without protocol/domain';
    END IF;

    -- 3. stored_sha256: SHA-256 computed and verified directly from the stored object bytes
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'evidence' AND column_name = 'stored_sha256'
    ) THEN
        ALTER TABLE evidence ADD COLUMN stored_sha256 VARCHAR(64) DEFAULT NULL;
        COMMENT ON COLUMN evidence.stored_sha256 IS 'Cryptographic SHA-256 hash verified directly on stored bytes';
    END IF;

    -- 4. stored_size: actual byte size of the object in storage
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'evidence' AND column_name = 'stored_size'
    ) THEN
        ALTER TABLE evidence ADD COLUMN stored_size BIGINT DEFAULT NULL;
        COMMENT ON COLUMN evidence.stored_size IS 'Exact byte size verified at storage gateway ingestion';
    END IF;

    -- 5. storage_verified_at: timestamp when the stored object was last cryptographically verified
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'evidence' AND column_name = 'storage_verified_at'
    ) THEN
        ALTER TABLE evidence ADD COLUMN storage_verified_at TIMESTAMPTZ DEFAULT NULL;
        COMMENT ON COLUMN evidence.storage_verified_at IS 'Timestamp of last SHA-256 verification via storage gateway';
    END IF;

    -- Optional index on storage_key for rapid gateway lookups
    CREATE INDEX IF NOT EXISTS idx_evidence_storage_key ON evidence (storage_key);

END $$;
"""

DOWNGRADE_SQL = """-- ==============================================================================
-- PHASE 2A: REVERSIBLE ROLLBACK SCRIPT (DOWNGRADE)
-- Removes only the additive metadata columns added above.
-- ==============================================================================

DO $$
BEGIN
    DROP INDEX IF EXISTS idx_evidence_storage_key;

    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'evidence' AND column_name = 'storage_verified_at'
    ) THEN
        ALTER TABLE evidence DROP COLUMN storage_verified_at;
    END IF;

    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'evidence' AND column_name = 'stored_size'
    ) THEN
        ALTER TABLE evidence DROP COLUMN stored_size;
    END IF;

    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'evidence' AND column_name = 'stored_sha256'
    ) THEN
        ALTER TABLE evidence DROP COLUMN stored_sha256;
    END IF;

    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'evidence' AND column_name = 'storage_key'
    ) THEN
        ALTER TABLE evidence DROP COLUMN storage_key;
    END IF;

    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'evidence' AND column_name = 'storage_backend'
    ) THEN
        ALTER TABLE evidence DROP COLUMN storage_backend;
    END IF;
END $$;
"""

def main():
    print("=" * 80)
    print("PROPOSED SCHEMA MIGRATION SCRIPT (DRY-RUN / PROPOSAL ONLY)")
    print("WARNING: In accordance with Phase 2A rules, this script DOES NOT execute SQL.")
    print("=" * 80)
    print("\n--- [UPGRADE SQL] ---")
    print(UPGRADE_SQL)
    print("\n--- [DOWNGRADE / ROLLBACK SQL] ---")
    print(DOWNGRADE_SQL)
    print("=" * 80)
    print("STATUS: SQL printed successfully. 0 database changes made.")
    print("=" * 80)

if __name__ == "__main__":
    main()
