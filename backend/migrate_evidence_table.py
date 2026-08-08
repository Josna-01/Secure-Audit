"""Legacy evidence migration helper; credentials are supplied only via DATABASE_URL."""
import os
import sys

from sqlalchemy import create_engine, text


SQL_COMMANDS = [
    "ALTER TABLE evidence ADD COLUMN IF NOT EXISTS file_name text;",
    "ALTER TABLE evidence ADD COLUMN IF NOT EXISTS file_size bigint;",
    "ALTER TABLE evidence ADD COLUMN IF NOT EXISTS mime_type text;",
    "ALTER TABLE evidence ADD COLUMN IF NOT EXISTS uploaded_by uuid;",
    "ALTER TABLE evidence ADD COLUMN IF NOT EXISTS uploaded_by_name text;",
    "ALTER TABLE evidence ADD COLUMN IF NOT EXISTS verified_at timestamp with time zone;",
    "ALTER TABLE evidence ADD COLUMN IF NOT EXISTS verified_by uuid;",
    "ALTER TABLE evidence ADD COLUMN IF NOT EXISTS chain_of_custody_status text DEFAULT 'Collected';",
    "ALTER TABLE evidence ADD COLUMN IF NOT EXISTS status text DEFAULT 'Verified';",
]


def run() -> None:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        sys.exit("DATABASE_URL is required; no migration was run.")
    with create_engine(database_url).begin() as connection:
        for command in SQL_COMMANDS:
            connection.execute(text(command))
    print("Evidence migration completed successfully.")


if __name__ == "__main__":
    run()
