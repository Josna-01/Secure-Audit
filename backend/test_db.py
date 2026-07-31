import sys
from sqlalchemy import text
from db import engine

def main():
    print("Attempting to connect to PostgreSQL database using db.py configuration...")
    try:
        with engine.connect() as conn:
            # Execute standard query to get PG version
            result = conn.execute(text("SELECT version();"))
            db_version = result.scalar()
            print("\n[SUCCESS] Database Connection Successful!")
            print("====================================")
            print(f"PostgreSQL Version:\n{db_version}")
            print("====================================")
    except Exception as e:
        print("\n[FAILED] Database Connection Failed!")
        print("====================================")
        print(f"Error details: {e}")
        print("====================================")
        print("\nSuggestions:")
        print("1. Ensure PostgreSQL is running.")
        print("2. Check if DATABASE_URL or DB_PASSWORD is set correctly in backend/.env.")
        print("3. Ensure the database user has correct access permissions.")

if __name__ == "__main__":
    main()
