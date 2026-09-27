import sys
sys.path.append('.')
from db import SessionLocal
from sqlalchemy import text
from datetime import datetime, timezone

db = SessionLocal()
print("--- Recent OTP Tokens ---")
try:
    otps = db.execute(text("SELECT id, user_id, token, expires_at, used, created_at FROM otp_tokens ORDER BY created_at DESC LIMIT 10")).fetchall()
    now = datetime.now(timezone.utc)
    for otp in otps:
        exp = otp[3]
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        is_expired = exp < now
        print(f"Token: {otp[2]} | Used: {otp[4]} | Expired: {is_expired} | Created: {otp[5]} | Expires: {otp[3]}")
except Exception as e:
    print("Error fetching otps:", e)

print("\n--- Recent Audit Logs ---")
try:
    logs = db.execute(text("SELECT created_at, action, user_id, metadata FROM audit_logs ORDER BY created_at DESC LIMIT 10")).fetchall()
    for log in logs:
        print(log)
except Exception as e:
    print("Error fetching logs:", e)
