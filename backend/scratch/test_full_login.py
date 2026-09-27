import requests, sys
sys.path.append('.')
from db import SessionLocal
from sqlalchemy import text

email = "ancilla.souza2005@gmail.com"
password = "SecureAudit@123"

# 1. Send OTP
r1 = requests.post("http://localhost:8000/auth/send-otp", json={"email": email})
print("send-otp status:", r1.status_code, r1.text)

# 2. Get the newly generated OTP directly from DB
db = SessionLocal()
otp_row = db.execute(text("SELECT token FROM otp_tokens WHERE user_id = (SELECT id FROM users WHERE email=:e) ORDER BY created_at DESC LIMIT 1"), {"e": email}).fetchone()
token = otp_row[0]
print("Generated OTP:", token)

# 3. Verify OTP + Password
r2 = requests.post("http://localhost:8000/auth/verify-otp", json={"email": email, "otp": token, "password": password})
print("verify-otp status:", r2.status_code)
res = r2.json()
print("Success:", res.get("success"))
if res.get("data", {}).get("token"):
    print("JWT Token successfully generated! Token length:", len(res["data"]["token"]))
    print("User Name:", res["data"]["user"]["name"])
    print("User Role:", res["data"]["user"]["role"])
else:
    print("Failed response:", res)
