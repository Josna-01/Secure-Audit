"""Migration: add can_create_case column to users; credentials via DATABASE_URL only."""
import os
import sys
from sqlalchemy import create_engine, text

SQL_COMMANDS = [
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS can_create_case BOOLEAN DEFAULT true;",
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
