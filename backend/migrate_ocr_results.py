"""OCR results migration helper.

Brings ``ocr_results`` up to the page-wise schema:

* ``detected_languages`` / ``ocr_metadata`` JSONB columns
* removes duplicate rows per (evidence_id, page_number), keeping the newest
  (older OCR versions appended a new row on every run)
* a unique index so one evidence item can only hold one row per page

Every statement is idempotent. This file intentionally contains no database
credentials and must only be run by an operator who supplies DATABASE_URL.
"""
import os
import sys

from sqlalchemy import create_engine, text


DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    try:
        from db import DATABASE_URL
    except Exception:
        DATABASE_URL = None


SQL_COMMANDS = [
    """
    CREATE TABLE IF NOT EXISTS ocr_results (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        evidence_id UUID REFERENCES evidence(id) ON DELETE CASCADE,
        extracted_text TEXT NOT NULL,
        language TEXT NOT NULL,
        confidence DOUBLE PRECISION,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
    );
    """,
    "ALTER TABLE ocr_results ADD COLUMN IF NOT EXISTS page_number INTEGER DEFAULT 1 NOT NULL;",
    "ALTER TABLE ocr_results ADD COLUMN IF NOT EXISTS detected_languages JSONB;",
    "ALTER TABLE ocr_results ADD COLUMN IF NOT EXISTS ocr_metadata JSONB;",
    """
    DELETE FROM ocr_results AS older
    USING ocr_results AS newer
    WHERE older.evidence_id = newer.evidence_id
      AND older.page_number = newer.page_number
      AND (older.created_at, older.id) < (newer.created_at, newer.id);
    """,
    """
    CREATE UNIQUE INDEX IF NOT EXISTS uq_ocr_results_evidence_page
        ON ocr_results (evidence_id, page_number);
    """,
]


def run() -> None:
    engine = create_engine(DATABASE_URL)
    with engine.begin() as connection:
        for command in SQL_COMMANDS:
            connection.execute(text(command))
    print("OCR results migration completed successfully.")


if __name__ == "__main__":
    run()
