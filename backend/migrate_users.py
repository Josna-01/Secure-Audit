"""Idempotent additive migration for legacy users tables.

Older databases were created before ``last_login`` was added to the ORM model.
SQLAlchemy selects every mapped column when loading a user, so that missing column
also prevented notification recipient resolution.  These statements are safe to
run repeatedly and never remove or rewrite existing user data.
"""
from sqlalchemy import text


STATEMENTS = [
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS can_create_case BOOLEAN DEFAULT TRUE",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS last_login TIMESTAMPTZ",
]


def apply(engine) -> None:
    with engine.begin() as connection:
        for statement in STATEMENTS:
            connection.execute(text(statement))


if __name__ == "__main__":
    from db import engine

    apply(engine)
    print("Users schema migration complete.")
