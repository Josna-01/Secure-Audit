import sys
sys.path.append('.')
from db import SessionLocal
from sqlalchemy import text

db = SessionLocal()
res = db.execute(text("SELECT t.token, t.expires_at, t.used, u.email, u.full_name, u.role FROM otp_tokens t LEFT JOIN users u ON t.user_id = u.id ORDER BY t.created_at DESC LIMIT 5")).fetchall()
for r in res:
    print(r)
