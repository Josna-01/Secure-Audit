"""Idempotent database migration for in-app notifications.

Run from the backend directory: ``python migrate_notifications.py``. The API also
applies these statements at startup (like migrate_blockchain.py), so an older database
keeps working. Every statement is CREATE ... IF NOT EXISTS; no existing data is changed.

Each row belongs to exactly one recipient. The partial unique index allows at most one
unread notification per recipient and event fingerprint, which prevents duplicate alerts
even when two requests detect the same event at the same time.
"""
from sqlalchemy import text

STATEMENTS = [
    """CREATE TABLE IF NOT EXISTS notifications (
        id UUID NOT NULL,
        recipient_id UUID NOT NULL,
        case_id UUID,
        evidence_id UUID,
        type VARCHAR NOT NULL,
        title VARCHAR NOT NULL,
        description VARCHAR NOT NULL,
        severity VARCHAR NOT NULL DEFAULT 'info',
        fingerprint VARCHAR,
        is_read BOOLEAN NOT NULL DEFAULT FALSE,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        read_at TIMESTAMPTZ,
        CONSTRAINT pk_notifications PRIMARY KEY (id),
        CONSTRAINT fk_notifications_recipient_id FOREIGN KEY (recipient_id) REFERENCES users(id) ON DELETE CASCADE,
        CONSTRAINT fk_notifications_case_id FOREIGN KEY (case_id) REFERENCES cases(id) ON DELETE RESTRICT,
        CONSTRAINT fk_notifications_evidence_id FOREIGN KEY (evidence_id) REFERENCES evidence(id) ON DELETE RESTRICT,
        CONSTRAINT chk_notifications_severity CHECK (severity IN ('info', 'warning', 'critical')))""",
    "CREATE INDEX IF NOT EXISTS idx_notifications_recipient_created ON notifications(recipient_id, created_at)",
    """CREATE UNIQUE INDEX IF NOT EXISTS uq_notifications_unread_fingerprint
        ON notifications(recipient_id, fingerprint) WHERE is_read = false AND fingerprint IS NOT NULL""",
]


def apply(engine) -> None:
    with engine.begin() as connection:
        for statement in STATEMENTS:
            connection.execute(text(statement))


if __name__ == "__main__":
    from db import engine
    apply(engine)
    print("Notifications schema migration complete.")
