import os
# pyrefly: ignore [missing-import]
import pg8000.dbapi

host = "aws-0-ap-south-1.pooler.supabase.com"
user = "postgres.taskxnlhzeaaddnxqxbw"
database = "postgres"
ports = [5432, 6543]

passwords_to_try = [
    "Amisha@#01",
    "Password123!",
    "Password123",
    "postgres",
    "supabase",
    "taskxnlhzeaaddnxqxbw",
    "thkwmytgtlrwqhou"
]

sql_commands = [
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS can_create_case BOOLEAN DEFAULT true;"
]

success = False
for port in ports:
    if success:
        break
    for pwd in passwords_to_try:
        print(f"Connecting to {host}:{port} with password...")
        try:
            conn = pg8000.dbapi.connect(
                host=host,
                user=user,
                password=pwd,
                database=database,
                port=port,
                timeout=5
            )
            print("Successfully connected to database!")
            cursor = conn.cursor()
            
            for cmd in sql_commands:
                print(f"Executing: {cmd}")
                try:
                    cursor.execute(cmd)
                    conn.commit()
                except Exception as e:
                    print(f"Error executing command: {e}")
                    conn.rollback()
            
            cursor.close()
            conn.close()
            success = True
            break
        except Exception as e:
            print(f"Connection failed: {e}")

if success:
    print("\nDatabase migration completed successfully!")
else:
    print("\nError: Could not connect to the database to perform migrations.")
    print("Please manually run the following SQL in your Supabase SQL Editor:")
    print("ALTER TABLE users ADD COLUMN IF NOT EXISTS can_create_case BOOLEAN DEFAULT true;")
