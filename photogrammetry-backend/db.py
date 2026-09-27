import os
import logging
from typing import Generator
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker

# Set up logging
logger = logging.getLogger("photogrammetry.db")

# Load this service's configuration before creating the engine.  Importing this
# module from another working directory must not silently select a different DB.
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

import urllib.parse

# Read PostgreSQL connection string from environment
# Priority 1: DATABASE_URL
# Priority 2: Construct from individual DB variables (DB_USER, DB_PASSWORD, DB_HOST, DB_PORT, DB_NAME)
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    db_user = os.getenv("DB_USER", "postgres")
    db_pass = os.getenv("DB_PASSWORD", "postgres")
    db_host = os.getenv("DB_HOST", "localhost")
    db_port = os.getenv("DB_PORT", "5432")
    db_name = os.getenv("DB_NAME", "postgres")
    
    # Properly URL-encode username and password to handle special characters
    encoded_user = urllib.parse.quote_plus(db_user)
    encoded_pass = urllib.parse.quote_plus(db_pass)
    
    # Construct the URI
    DATABASE_URL = f"postgresql://{encoded_user}:{encoded_pass}@{db_host}:{db_port}/{db_name}"

# Modern connection pooling configuration
engine = create_engine(
    DATABASE_URL,
    pool_size=10,            # Permanent pool size
    max_overflow=20,         # Allow up to 20 temporary connections beyond pool_size
    pool_recycle=1800,       # Recycle connections older than 30 minutes
    pool_pre_ping=True,      # Test connections before giving them to the session
    pool_use_lifo=True,      # Use LIFO to recycle connections more efficiently
    connect_args={"connect_timeout": 10}  # 10 second timeout for initial connection
)

# SessionLocal session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Declarative base class for models
Base = declarative_base()

# FastAPI dependency to yield database sessions
def get_db() -> Generator:
    """
    FastAPI dependency that yields a database session and ensures it is closed
    after the request is processed.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
