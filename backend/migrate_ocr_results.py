"""Legacy one-time OCR migration helper.

The OCR table is already migrated. This file intentionally contains no database
credentials and must only be run by an operator who supplies DATABASE_URL.
"""
import os
import sys

from sqlalchemy import create_engine, text


DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    sys.exit("DATABASE_URL is required; no migration was run.")


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
]


def run() -> None:
    engine = create_engine(DATABASE_URL)
    with engine.begin() as connection:
        for command in SQL_COMMANDS:
            connection.execute(text(command))
    print("OCR results migration completed successfully.")


if __name__ == "__main__":
    run()
