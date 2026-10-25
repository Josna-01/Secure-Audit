"""Idempotent database migration for blockchain evidence metadata.

Run from the backend directory: ``python migrate_blockchain.py``. The API also
applies these statements at startup, so an older database keeps working, but
running the script explicitly is recommended after pulling schema changes.
Every statement is additive (ADD COLUMN / CREATE ... IF NOT EXISTS); no data is changed.
"""
from sqlalchemy import text

STATEMENTS = [
    "ALTER TABLE evidence ADD COLUMN IF NOT EXISTS blockchain_tx_hash VARCHAR UNIQUE",
    "ALTER TABLE evidence ADD COLUMN IF NOT EXISTS blockchain_block_number BIGINT",
    "ALTER TABLE evidence ADD COLUMN IF NOT EXISTS blockchain_contract_address VARCHAR",
    "ALTER TABLE evidence ADD COLUMN IF NOT EXISTS blockchain_gas_used BIGINT",
    "ALTER TABLE evidence ADD COLUMN IF NOT EXISTS blockchain_registered_at TIMESTAMPTZ",
    "ALTER TABLE evidence ADD COLUMN IF NOT EXISTS latest_verification_at TIMESTAMPTZ",
    # Receipt metadata and last verification outcome.
    "ALTER TABLE evidence ADD COLUMN IF NOT EXISTS blockchain_block_hash VARCHAR",
    "ALTER TABLE evidence ADD COLUMN IF NOT EXISTS blockchain_wallet_address VARCHAR",
    "ALTER TABLE evidence ADD COLUMN IF NOT EXISTS blockchain_chain_id BIGINT",
    "ALTER TABLE evidence ADD COLUMN IF NOT EXISTS blockchain_tx_status VARCHAR",
    "ALTER TABLE evidence ADD COLUMN IF NOT EXISTS last_verification_result VARCHAR",
    "ALTER TABLE evidence ADD COLUMN IF NOT EXISTS last_verification_reason VARCHAR",
    "CREATE INDEX IF NOT EXISTS ix_evidence_file_hash ON evidence(file_hash)",
    """CREATE TABLE IF NOT EXISTS evidence_custody_records (
        id UUID PRIMARY KEY, evidence_id UUID NOT NULL REFERENCES evidence(id) ON DELETE CASCADE,
        officer_id VARCHAR NOT NULL, action VARCHAR NOT NULL, occurred_at TIMESTAMPTZ NOT NULL,
        transaction_hash VARCHAR, block_number BIGINT, created_at TIMESTAMPTZ DEFAULT now())""",
    "ALTER TABLE evidence_custody_records DROP CONSTRAINT IF EXISTS evidence_custody_records_transaction_hash_key",
    "CREATE INDEX IF NOT EXISTS ix_evidence_custody_records_evidence_id ON evidence_custody_records(evidence_id)",
    "CREATE INDEX IF NOT EXISTS ix_evidence_custody_records_transaction_hash ON evidence_custody_records(transaction_hash)",
    "ALTER TABLE evidence_custody_records ADD COLUMN IF NOT EXISTS source VARCHAR DEFAULT 'blockchain'",
    "ALTER TABLE evidence_custody_records ADD COLUMN IF NOT EXISTS details JSONB",
    # One transaction can emit several events (EvidenceVerified + EvidenceTampered),
    # so the transaction hash is indexed but not unique.
    """CREATE TABLE IF NOT EXISTS blockchain_logs (
        id UUID PRIMARY KEY, evidence_id UUID REFERENCES evidence(id) ON DELETE CASCADE,
        event_name VARCHAR NOT NULL, transaction_hash VARCHAR, block_number BIGINT,
        payload JSONB, created_at TIMESTAMPTZ DEFAULT now())""",
    "ALTER TABLE blockchain_logs DROP CONSTRAINT IF EXISTS blockchain_logs_transaction_hash_key",
    "CREATE INDEX IF NOT EXISTS ix_blockchain_logs_transaction_hash ON blockchain_logs(transaction_hash)",
    "CREATE INDEX IF NOT EXISTS ix_blockchain_logs_evidence_id ON blockchain_logs(evidence_id)",
]


def apply(engine) -> None:
    with engine.begin() as connection:
        for statement in STATEMENTS:
            connection.execute(text(statement))


if __name__ == "__main__":
    from db import engine
    apply(engine)
    print("Blockchain schema migration complete.")
