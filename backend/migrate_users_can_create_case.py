"""Legacy user migration helper; credentials are supplied only via DATABASE_URL."""
import os
import sys

from sqlalchemy import create_engine, text


SQL_COMMAND = "ALTER TABLE users ADD COLUMN IF NOT EXISTS can_create_case BOOLEAN DEFAULT true;"


def run() -> None:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        sys.exit("DATABASE_URL is required; no migration was run.")
    with create_engine(database_url).begin() as connection:
        connection.execute(text(SQL_COMMAND))
    print("User migration completed successfully.")


if __name__ == "__main__":
    run()
