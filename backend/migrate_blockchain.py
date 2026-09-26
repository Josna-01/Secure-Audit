"""Idempotent database migration for blockchain evidence metadata."""
from sqlalchemy import text
from db import engine

STATEMENTS = [
    "ALTER TABLE evidence ADD COLUMN IF NOT EXISTS blockchain_tx_hash VARCHAR UNIQUE",
    "ALTER TABLE evidence ADD COLUMN IF NOT EXISTS blockchain_block_number BIGINT",
    "ALTER TABLE evidence ADD COLUMN IF NOT EXISTS blockchain_contract_address VARCHAR",
    "ALTER TABLE evidence ADD COLUMN IF NOT EXISTS blockchain_gas_used BIGINT",
    "ALTER TABLE evidence ADD COLUMN IF NOT EXISTS blockchain_registered_at TIMESTAMPTZ",
    "ALTER TABLE evidence ADD COLUMN IF NOT EXISTS latest_verification_at TIMESTAMPTZ",
    """CREATE TABLE IF NOT EXISTS evidence_custody_records (
        id UUID PRIMARY KEY, evidence_id UUID NOT NULL REFERENCES evidence(id) ON DELETE CASCADE,
        officer_id VARCHAR NOT NULL, action VARCHAR NOT NULL, occurred_at TIMESTAMPTZ NOT NULL,
        transaction_hash VARCHAR UNIQUE, block_number BIGINT, created_at TIMESTAMPTZ DEFAULT now())""",
    "CREATE INDEX IF NOT EXISTS ix_evidence_custody_records_evidence_id ON evidence_custody_records(evidence_id)",
    """CREATE TABLE IF NOT EXISTS blockchain_logs (
        id UUID PRIMARY KEY, evidence_id UUID REFERENCES evidence(id) ON DELETE CASCADE,
        event_name VARCHAR NOT NULL, transaction_hash VARCHAR UNIQUE, block_number BIGINT,
        payload JSONB, created_at TIMESTAMPTZ DEFAULT now())""",
]

with engine.begin() as connection:
    for statement in STATEMENTS:
        connection.execute(text(statement))
print("Blockchain schema migration complete.")
