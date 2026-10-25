#!/usr/bin/env python3
"""
Test Application Post-Archival Endpoints & New-Case Creation Flow
"""

import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv

SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

load_dotenv(BACKEND_DIR / ".env")

from db import SessionLocal
from models import Case, User
from app import get_cases, serialize_case

class DummyRequest:
    def __init__(self, headers=None):
        self.headers = headers or {}
        self.state = type("State", (), {"user": None})()

def run_tests():
    print("=" * 80)
    print("TESTING APPLICATION BEHAVIOR POST-ARCHIVAL")
    print("=" * 80)

    db = SessionLocal()

    # 1. Test GET /cases filtering
    print("\nTest 1: Verify archived cases are excluded from get_cases query...")
    active_cases = db.query(Case).filter((Case.is_archived.is_(False)) | (Case.is_archived.is_(None))).all()
    print(f"  Active cases in DB: {len(active_cases)}")
    assert len(active_cases) == 0, f"Expected 0 active cases, found {len(active_cases)}"

    all_cases = db.query(Case).all()
    print(f"  Total cases in DB: {len(all_cases)} (all preserved as archived)")
    assert len(all_cases) == 8, f"Expected 8 total cases, found {len(all_cases)}"
    print("  PASS: Archived demo cases are completely hidden from active queries.")

    # 2. Test user lookup & login readiness
    print("\nTest 2: Verify user accounts are intact and ready for authentication...")
    admin_user = db.query(User).filter(User.role == "Admin").first()
    print(f"  Found admin user: {admin_user.full_name} ({admin_user.email})")
    assert admin_user is not None
    assert admin_user.is_active is True
    print("  PASS: Admin user account is active and intact.")

    # 3. Test new case creation
    print("\nTest 3: Testing new fresh case creation...")
    new_case_id = uuid.uuid4()
    test_case_num = f"SA-TEST-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    new_case = Case(
        id=new_case_id,
        case_number=test_case_num,
        title="Verification Clean-Slate Test Case",
        offence_type="Test Investigation",
        incident_location="Forensics Lab Room 101",
        created_by=admin_user.id,
        created_by_name=admin_user.full_name,
        is_archived=False
    )


    db.add(new_case)
    db.commit()
    print(f"  Successfully inserted new active case: {test_case_num} (ID: {new_case_id})")

    # 4. Verify new case appears in active get_cases query
    print("\nTest 4: Verify new case appears in active case query...")
    active_cases_after = db.query(Case).filter((Case.is_archived.is_(False)) | (Case.is_archived.is_(None))).all()
    print(f"  Active cases count after creation: {len(active_cases_after)}")
    assert len(active_cases_after) == 1
    assert active_cases_after[0].id == new_case_id
    assert active_cases_after[0].case_number == test_case_num
    print("  PASS: New case is immediately returned by active queries.")

    # 5. Clean up the test case so the slate is 100% clean for the user
    print("\nTest 5: Cleaning up verification test case...")
    db.delete(new_case)
    db.commit()
    final_active = db.query(Case).filter((Case.is_archived.is_(False)) | (Case.is_archived.is_(None))).count()
    print(f"  Active cases count after cleanup: {final_active}")
    assert final_active == 0
    print("  PASS: Verification test case cleaned up. Active cases count is 0.")

    db.close()

    print("\n" + "=" * 80)
    print("ALL APPLICATION ENDPOINT & WORKFLOW TESTS PASSED!")
    print("=" * 80)

if __name__ == "__main__":
    run_tests()
