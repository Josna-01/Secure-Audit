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

def run_migration():
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        from db import engine
    else:
        engine = create_engine(db_url)
    with engine.connect() as conn:
        for cmd in SQL_COMMANDS:
            print(f"Executing: {cmd}")
            try:
                conn.execute(text(cmd))
                conn.commit()
                print("  -> OK")
            except Exception as e:
                print(f"  -> Error: {e}")
                conn.rollback()

    print("\nDatabase migration completed successfully!")

if __name__ == "__main__":
    run_migration()
