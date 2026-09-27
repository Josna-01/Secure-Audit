import requests, json

email = "ancilla.souza2005@gmail.com"
print("Testing send-otp...")
r = requests.post("http://localhost:8000/auth/send-otp", json={"email": email})
print("send-otp status:", r.status_code, r.text)

# Check what OTP was generated in DB
import sys
sys.path.append('.')
from db import SessionLocal
from sqlalchemy import text
db = SessionLocal()
otp_row = db.execute(text("SELECT token, expires_at, used FROM otp_tokens WHERE user_id = (SELECT id FROM users WHERE email=:e) ORDER BY created_at DESC LIMIT 1"), {"e": email}).fetchone()
print("Latest OTP in DB:", otp_row)

if otp_row:
    token = otp_row[0]
    print(f"Testing verify-otp with token={token} and dummy password...")
    r2 = requests.post("http://localhost:8000/auth/verify-otp", json={"email": email, "otp": token, "password": "WrongPassword123!"})
    print("verify-otp with wrong password:", r2.status_code, r2.text)
