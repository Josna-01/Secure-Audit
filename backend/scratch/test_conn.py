import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

print(f"Connecting to Supabase at: {url}")
supabase = create_client(url, key)

try:
    res = supabase.table("evidence").select("id").limit(1).execute()
    print("Connection successful! Evidence data:", res.data)
except Exception as e:
    print("Connection failed:", e)
