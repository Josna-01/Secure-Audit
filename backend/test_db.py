import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

print("Starting test")

# 1. Create case
try:
    res = supabase.table("cases").insert({"title": "Test run", "offence_type": "Robbery", "fir_description": "test"}).execute()
    case_id = res.data[0]['id']
    print(f"Case ID: {case_id}")
except Exception as e:
    print(f"Error creating case: {e}")

# 2. Add evidence
try:
    res = supabase.table("evidence").insert({"case_id": case_id, "evidence_type": "Image", "description": "test", "file_url": "test.jpg", "file_hash": "test"}).execute()
    ev_id = res.data[0]['id']
    print(f"Evidence ID: {ev_id}")
except Exception as e:
    print(f"Error creating evidence: {e}")

# 3. Add detection
try:
    res = supabase.table("detections").insert({
        "case_id": case_id,
        "evidence_id": ev_id,
        "image_url": "http://localhost:8000/test.jpg",
        "predictions": {"objects": [{"label": "test", "confidence": 0.9, "bbox": [0,0,10,10]}]}
    }).execute()
    print(f"Detection inserted: {res.data[0]['id']}")
except Exception as e:
    print(f"Error creating detection: {e}")
