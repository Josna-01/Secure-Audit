import sys, os
sys.path.append('.')
from dotenv import load_dotenv
load_dotenv()
from supabase import create_client

url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_KEY")
client = create_client(url, key)

candidates = [
    "SecureAudit@123",
    "Jesusblessme@13",
    "password",
    "password123",
    "admin123",
    "Admin@123",
    "Amisha@123",
    "amisha123"
]

for email in ["amishajosnadsouza.1@gmail.com", "dsouzaglaina@gmail.com", "alishafdz28@gmail.com", "amishadsouza.2005@gmail.com"]:
    for p in candidates:
        try:
            res = client.auth.sign_in_with_password({"email": email, "password": p})
            if res.user:
                print(f"MATCH FOUND for {email}: {p}")
                break
        except Exception:
            pass
