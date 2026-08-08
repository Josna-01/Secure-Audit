import sys
import os
import uuid
import datetime

# Add backend directory to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db import SessionLocal
from models import User, OTPToken
from app import sync_user_to_postgres

def test_sync_and_otp():
    db = SessionLocal()
    try:
        # Create a mock Supabase user object
        fake_user_id = str(uuid.uuid4())
        mock_supabase_user = {
            "id": fake_user_id,
            "email": f"test_sync_{fake_user_id[:8]}@example.com",
            "full_name": "Test Officer",
            "role": "Investigator",
            "department": "Cyber Crime",
            "badge_number": "BC-9999",
            "clearance_level": 2,
            "is_active": True,
            "can_create_case": True,
            "last_login": None
        }

        print(f"[TEST] Synchronizing Supabase user {fake_user_id} to PostgreSQL...")
        sync_user_to_postgres(mock_supabase_user, db)

        # Verify user exists in PostgreSQL
        pg_user = db.query(User).filter(User.id == uuid.UUID(fake_user_id)).first()
        assert pg_user is not None, "PostgreSQL user record was not found after sync!"
        assert pg_user.email == mock_supabase_user["email"], "Email mismatch!"
        assert str(pg_user.id) == fake_user_id, "UUID mismatch!"
        print(f"[TEST SUCCESS] PostgreSQL user record found: ID={pg_user.id}, Email={pg_user.email}, Role={pg_user.role}")

        # Try inserting OTPToken
        print("[TEST] Inserting OTP token referencing PostgreSQL user...")
        otp_token = OTPToken(
            id=uuid.uuid4(),
            user_id=uuid.UUID(fake_user_id),
            token="123456",
            expires_at=datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=5),
            used=False
        )
        db.add(otp_token)
        db.commit()

        # Verify OTP token stored successfully
        saved_otp = db.query(OTPToken).filter(OTPToken.id == otp_token.id).first()
        assert saved_otp is not None, "OTPToken record not found!"
        print(f"[TEST SUCCESS] OTP Token stored successfully! Token ID={saved_otp.id}, User ID={saved_otp.user_id}")

        # Clean up test records
        db.delete(saved_otp)
        db.delete(pg_user)
        db.commit()
        print("[TEST SUCCESS] Cleanup completed successfully!")

    except Exception as e:
        db.rollback()
        print(f"[TEST FAILED] Error: {e}")
        raise e
    finally:
        db.close()

if __name__ == "__main__":
    test_sync_and_otp()
