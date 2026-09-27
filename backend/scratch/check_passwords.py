import sys, os
sys.path.append('.')
from dotenv import load_dotenv
load_dotenv()
from supabase import create_client

url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_KEY")
client = create_client(url, key)

candidates = [
    "Jesusblessme@13",
    "password",
    "password123",
    "admin123",
    "Admin@123",
    "Ancilla@123",
    "ancilla123",
    "SecureAudit@123",
    "Secure@123"
]

email = "ancilla.souza2005@gmail.com"
found = None
for p in candidates:
    try:
        res = client.auth.sign_in_with_password({"email": email, "password": p})
        if res.user:
            found = p
            print(f"MATCH FOUND for {email}: {p}")
            break
    except Exception:
        pass

if not found:
    print(f"None of the candidate passwords matched for {email}")
