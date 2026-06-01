from supabase import create_client
import os
from dotenv import load_dotenv
load_dotenv()
supabase = create_client(os.environ['SUPABASE_URL'], os.environ['SUPABASE_KEY'])

data = {
    "case_id": "dd2099c9-11c4-436b-a853-a2aba819e019",
    "evidence_type": "Image",
    "description": "test",
    "file_url": "test",
    "file_hash": "test12345",
    "status": "Verified"
}
try:
    res = supabase.table("evidence").insert(data).execute()
    print("Success:", res.data)
except Exception as e:
    print("Error:", e)
