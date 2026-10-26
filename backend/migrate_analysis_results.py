"""Idempotent schema migration for durable analysis-result records.

Run from ``backend`` with ``python migrate_analysis_results.py``.  The API
applies the same additive statements on startup, so existing installations are
updated without deleting or rewriting any evidence or prior result data.
"""
from sqlalchemy import text


STATEMENTS = [
    """CREATE TABLE IF NOT EXISTS audio_forensics_results (
        id UUID NOT NULL,
        case_id UUID,
        evidence_id UUID,
        analysed_by UUID,
        filename VARCHAR,
        content_type VARCHAR,
        source_sha256 VARCHAR NOT NULL,
        result JSONB NOT NULL,
        overall_status VARCHAR,
        duration_seconds DOUBLE PRECISION,
        sample_rate INTEGER,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        CONSTRAINT pk_audio_forensics_results PRIMARY KEY (id),
        CONSTRAINT fk_audio_forensics_results_case_id FOREIGN KEY (case_id) REFERENCES cases(id) ON DELETE RESTRICT,
        CONSTRAINT fk_audio_forensics_results_evidence_id FOREIGN KEY (evidence_id) REFERENCES evidence(id) ON DELETE RESTRICT,
        CONSTRAINT fk_audio_forensics_results_analysed_by FOREIGN KEY (analysed_by) REFERENCES users(id) ON DELETE SET NULL
    )""",
    "CREATE INDEX IF NOT EXISTS idx_audio_results_case_created ON audio_forensics_results(case_id, created_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_audio_results_evidence_created ON audio_forensics_results(evidence_id, created_at DESC)",
]


def apply(engine) -> None:
    with engine.begin() as connection:
        for statement in STATEMENTS:
            connection.execute(text(statement))


if __name__ == "__main__":
    from db import engine
    apply(engine)
    print("Analysis-results schema migration complete.")
