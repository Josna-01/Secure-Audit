
import os
from urllib.parse import urlparse
import shutil
import uuid
import datetime
import random
import string
import smtplib
import logging
import subprocess
import threading
import time
from pathlib import Path
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from fastapi import FastAPI, File, UploadFile, HTTPException, Form, BackgroundTasks, Request, Depends
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from fastapi.staticfiles import StaticFiles
from supabase import create_client, Client
from gotrue.errors import AuthApiError
import hashlib
import jwt as pyjwt
from dotenv import load_dotenv
from roboflow import Roboflow
import requests
from sqlalchemy import text
from sqlalchemy.orm import Session
from db import get_db, SessionLocal
from models import User, Case, Evidence, AuditLog, OCRResult, BNSPrediction, OTPToken, EvidenceCustodyRecord, BlockchainLog
from services.ocr_service import OCRServiceError, build_document_result, ocr_service
from services.ocr_text import UNKNOWN_LANGUAGE, detect_languages
from services.translation_service import (TARGET_LANGUAGES, TranslationError,
                                          resolve_target_language, translation_service)
from services.blockchain_service import blockchain_service, BlockchainUnavailable, BlockchainTransactionError

load_dotenv()
logger = logging.getLogger("secure_audit.application")


def serialize_case(case) -> dict:
    if not case:
        return {}
    return {
        "id": str(case.id),
        "title": case.title,
        "offence_type": case.offence_type,
        "fir_description": case.fir_description,
        "fir_language": case.fir_language,
        "complainant_name": case.complainant_name,
        "complainant_contact": case.complainant_contact,
        "victims": case.victims,
        "suspects": case.suspects,
        "incident_date": case.incident_date.isoformat() if case.incident_date else None,
        "incident_time": case.incident_time.strftime("%H:%M") if case.incident_time else None,
        "incident_location": case.incident_location,
        "created_at": case.created_at.isoformat().replace("+00:00", "Z") if case.created_at else None,
        "case_number": case.case_number,
        "created_by": str(case.created_by) if case.created_by else None,
        "created_by_name": case.created_by_name
    }

def serialize_evidence(evidence) -> dict:
    if not evidence:
        return {}
    return {
        "id": str(evidence.id),
        "case_id": str(evidence.case_id) if evidence.case_id else None,
        "evidence_type": evidence.evidence_type,
        "description": evidence.description,
        "file_url": evidence.file_url,
        "file_hash": evidence.file_hash,
        "created_at": evidence.created_at.isoformat().replace("+00:00", "Z") if evidence.created_at else None,
        "file_name": evidence.file_name,
        "file_size": evidence.file_size,
        "mime_type": evidence.mime_type,
        "uploaded_by": str(evidence.uploaded_by) if evidence.uploaded_by else None,
        "uploaded_by_name": evidence.uploaded_by_name,
        "verified_at": evidence.verified_at.isoformat().replace("+00:00", "Z") if evidence.verified_at else None,
        "verified_by": str(evidence.verified_by) if evidence.verified_by else None,
        "chain_of_custody_status": evidence.chain_of_custody_status,
        "status": evidence.status,
        "blockchain": {
            "transactionHash": evidence.blockchain_tx_hash,
            "blockNumber": evidence.blockchain_block_number,
            "contractAddress": evidence.blockchain_contract_address,
            "gasUsed": evidence.blockchain_gas_used,
            "registeredAt": evidence.blockchain_registered_at.isoformat() if evidence.blockchain_registered_at else None,
            "latestVerificationAt": evidence.latest_verification_at.isoformat() if evidence.latest_verification_at else None,
        }
    }

def serialize_case(case) -> dict:
    if not case:
        return {}
    return {
        "id": str(case.id),
        "title": case.title,
        "offence_type": case.offence_type,
        "fir_description": case.fir_description,
        "fir_language": case.fir_language,
        "complainant_name": case.complainant_name,
        "complainant_contact": case.complainant_contact,
        "victims": case.victims,
        "suspects": case.suspects,
        "incident_date": case.incident_date.isoformat() if case.incident_date else None,
        "incident_time": case.incident_time.strftime("%H:%M") if case.incident_time else None,
        "incident_location": case.incident_location,
        "created_at": case.created_at.isoformat().replace("+00:00", "Z") if case.created_at else None,
        "case_number": case.case_number,
        "created_by": str(case.created_by) if case.created_by else None,
        "created_by_name": case.created_by_name
    }

def serialize_evidence(evidence) -> dict:
    if not evidence:
        return {}
    return {
        "id": str(evidence.id),
        "case_id": str(evidence.case_id) if evidence.case_id else None,
        "evidence_type": evidence.evidence_type,
        "description": evidence.description,
        "file_url": evidence.file_url,
        "file_hash": evidence.file_hash,
        "created_at": evidence.created_at.isoformat().replace("+00:00", "Z") if evidence.created_at else None,
        "file_name": evidence.file_name,
        "file_size": evidence.file_size,
        "mime_type": evidence.mime_type,
        "uploaded_by": str(evidence.uploaded_by) if evidence.uploaded_by else None,
        "uploaded_by_name": evidence.uploaded_by_name,
        "verified_at": evidence.verified_at.isoformat().replace("+00:00", "Z") if evidence.verified_at else None,
        "verified_by": str(evidence.verified_by) if evidence.verified_by else None,
        "chain_of_custody_status": evidence.chain_of_custody_status,
        "status": evidence.status
    }

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
ROBOFLOW_API_KEY = os.environ.get("ROBOFLOW_API_KEY")
JWT_SECRET = os.environ.get("JWT_SECRET")
EMAIL_USER = os.environ.get("EMAIL_USER")
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD")
USE_LOCAL_STORAGE = os.environ.get("USE_LOCAL_STORAGE", "False").lower() in ("true", "1", "yes")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
supabase_admin: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

app = FastAPI()


_blockchain_event_cursor: Optional[int] = None


def make_json_safe(obj):
    if isinstance(obj, (bytes, bytearray)):
        return "0x" + obj.hex() if not str(obj).startswith("0x") else obj.hex()
    if isinstance(obj, dict):
        return {str(k): make_json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [make_json_safe(x) for x in obj]
    return obj


def synchronize_blockchain_events() -> None:
    """Mirror contract events created outside this API without duplicating receipt writes."""
    global _blockchain_event_cursor
    session = SessionLocal()
    try:
        if _blockchain_event_cursor is None:
            status = blockchain_service.status()
            if not status["connected"]:
                return
            _blockchain_event_cursor = max(0, status["latestBlock"] - 1)
        events, latest = blockchain_service.events_since(_blockchain_event_cursor)
        for event in events:
            raw_ev_id = event["args"].get("evidenceId")
            ev_str = raw_ev_id.hex() if isinstance(raw_ev_id, (bytes, bytearray)) else str(raw_ev_id)
            
            # Find evidence by transaction hash or valid UUID
            evidence = session.query(Evidence).filter(Evidence.blockchain_tx_hash == event["transactionHash"]).first()
            if not evidence and ev_str:
                try:
                    parsed_uuid = uuid.UUID(ev_str)
                    evidence = session.query(Evidence).filter(Evidence.id == parsed_uuid).first()
                except Exception:
                    evidence = None
            
            safe_payload = make_json_safe(event["args"])

            if evidence:
                if event["name"] == "EvidenceVerified":
                    evidence.status = "Verified" if event["args"].get("isMatch") else "Tampered"
                    evidence.latest_verification_at = event["timestamp"]
                if event["name"] == "CustodyTransferred" and not session.query(EvidenceCustodyRecord.id).filter(EvidenceCustodyRecord.transaction_hash == event["transactionHash"]).first():
                    session.add(EvidenceCustodyRecord(
                        evidence_id=evidence.id,
                        officer_id=str(event["args"].get("officerId", "system")),
                        action=str(event["args"].get("action", "TRANSFERRED")),
                        occurred_at=event["timestamp"],
                        transaction_hash=event["transactionHash"],
                        block_number=event["blockNumber"]
                    ))
            
            if not session.query(BlockchainLog.id).filter(
                BlockchainLog.transaction_hash == event["transactionHash"],
                BlockchainLog.event_name == event["name"]
            ).first():
                session.add(BlockchainLog(
                    evidence_id=evidence.id if evidence else None,
                    event_name=event["name"],
                    transaction_hash=event["transactionHash"],
                    block_number=event["blockNumber"],
                    payload=safe_payload
                ))
        session.commit()
        _blockchain_event_cursor = latest + 1
    except Exception as exc:
        session.rollback()
        logger.warning("Blockchain event synchronization deferred: %s", exc)
    finally:
        session.close()


def blockchain_event_listener() -> None:
    while True:
        synchronize_blockchain_events()
        time.sleep(int(os.getenv("BLOCKCHAIN_EVENT_POLL_SECONDS", "10")))


@app.on_event("startup")
def start_blockchain_event_listener() -> None:
    threading.Thread(target=blockchain_event_listener, name="blockchain-event-listener", daemon=True).start()


@app.on_event("startup")
def ensure_ocr_result_columns() -> None:
    """Add the nullable OCR page-metadata columns if an older schema lacks them.

    Purely additive and idempotent. Duplicate clean-up and the unique
    (evidence_id, page_number) index are left to migrate_ocr_results.py.
    """
    try:
        with SessionLocal() as session:
            session.execute(text("ALTER TABLE ocr_results ADD COLUMN IF NOT EXISTS detected_languages JSONB"))
            session.execute(text("ALTER TABLE ocr_results ADD COLUMN IF NOT EXISTS ocr_metadata JSONB"))
            session.commit()
    except Exception as exc:
        print(f"[OCR WARNING] Could not verify ocr_results columns; run migrate_ocr_results.py: {exc}")

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOADS_DIR = os.path.join(BACKEND_DIR, "uploads")
os.makedirs(UPLOADS_DIR, exist_ok=True)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/uploads", StaticFiles(directory=UPLOADS_DIR), name="uploads")

# Load model
try:
    rf = Roboflow(api_key=ROBOFLOW_API_KEY)
    project = rf.workspace().project("weapon-detection-using-yolov8")
    model = project.version(1).model
except Exception as e:
    print(f"Warning: Failed to load Roboflow model. Provide a valid key. Error: {e}")
    model = None

# ====== Pydantic Models ======
class CaseCreate(BaseModel):
    title: str
    offence_type: str
    fir_description: str
    fir_language: str = "en"
    complainant_name: str
    complainant_contact: Optional[str] = None
    victims: List[Dict[str, Any]] = []
    suspects: List[Dict[str, Any]] = []
    incident_date: Optional[str] = None
    incident_time: Optional[str] = None
    incident_location: Optional[str] = None

class DetectionRequest(BaseModel):
    evidence_id: str
    case_id: str

class OCRRequest(BaseModel):
    evidence_id: Optional[str] = None
    language: Optional[str] = "auto"
    force: Optional[bool] = False
    # Optional translation; the original OCR text is always returned unchanged.
    translate: Optional[bool] = False
    target_language: Optional[str] = "en"


class LoginRequest(BaseModel):
    email: str
    password: Optional[str] = None

class VerifyOTPRequest(BaseModel):
    email: str
    otp: str
    password: Optional[str] = None

class RegisterRequest(BaseModel):
    name: str
    badge_id: str
    email: str
    department: str
    password: str
    phone: Optional[str] = None

class ForgotPasswordRequest(BaseModel):
    email: str

class ResetPasswordRequest(BaseModel):
    email: str
    otp: str
    new_password: str

class ChangePasswordRequest(BaseModel):
    new_password: str

class DirectLoginRequest(BaseModel):
    email: str
    password: str
    department: Optional[str] = None
    role: Optional[str] = None


@app.get("/")
def home():
    return {"message": "API is running"}

# ====== EMAIL HELPER ======
def send_otp_email(to_email: str, otp: str, officer_name: str):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Secure Audits — Your Access Token"
    msg["From"] = EMAIL_USER
    msg["To"] = to_email

    body = f"""
    <html><body style="font-family: monospace; background: #0a0a0a; color: #00ff88; padding: 32px;">
    <h2 style="color: #00ff88;">SECURE AUDITS</h2>
    <p style="color: #ccc;">Officer {officer_name},</p>
    <p style="color: #ccc;">Your one-time access token:</p>
    <h1 style="letter-spacing: 8px; color: #00ff88; font-size: 48px;">{otp}</h1>
    <p style="color: #888;">Valid for 5 minutes. Do not share this token.</p>
    <p style="color: #444; font-size: 11px;">Secure Audits — Digital Evidence Investigation System</p>
    </body></html>
    """

    msg.attach(MIMEText(body, "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(EMAIL_USER, EMAIL_PASSWORD)
        server.sendmail(EMAIL_USER, to_email, msg.as_string())


# ====== JWT HELPER ======
def create_jwt(user_id: str, email: str, role: str, name: str) -> str:
    payload = {
        "sub": user_id,
        "email": email,
        "role": role,
        "name": name,
        "iat": datetime.datetime.utcnow(),
        "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=24)
    }
    return pyjwt.encode(payload, JWT_SECRET, algorithm="HS256")


def decode_jwt(token: str) -> dict:
    return pyjwt.decode(token, JWT_SECRET, algorithms=["HS256"])

def get_current_user_id(request: Request) -> str:
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
        try:
            payload = decode_jwt(token)
            return payload.get("sub") or "system"
        except Exception:
            pass
    return "system"

# ====== RBAC CONFIGURATION & HELPERS ======
ROLE_PERMISSIONS = {
    "Admin": {
        "permissions": {
            "create_case": True,
            "upload_evidence": True,
            "run_ai_analysis": True,
            "generate_storyboard": True,
            "view_cases": "all",          # "all" or "owned"
            "view_audit_logs": "all",     # "all" or "owned"
            "manage_users": True,
            "system_settings": True,
            "dashboard_analytics": "all"   # "all" or "limited"
        }
    },
    "Investigator": {
        "permissions": {
            "create_case": True,
            "upload_evidence": True,
            "run_ai_analysis": True,
            "generate_storyboard": True,
            "view_cases": "owned",
            "view_audit_logs": "owned",
            "manage_users": False,
            "system_settings": False,
            "dashboard_analytics": "limited"
        }
    }
}

def sync_user_to_postgres(user: dict, db: Session) -> None:
    """Ensure a Supabase user record exists in local PostgreSQL users table before relational operations."""
    user_id = user.get("id")
    if not user_id:
        return

    email = user.get("email")
    full_name = user.get("full_name") or "Investigator"
    role = user.get("role") or "Investigator"
    department = user.get("department")
    badge_number = user.get("badge_number")
    clearance_level = user.get("clearance_level", 1)
    is_active = user.get("is_active", True)
    can_create_case = user.get("can_create_case", True)
    last_login = user.get("last_login")

    db.execute(
        text("""
            INSERT INTO users (id, email, full_name, role, department, badge_number, clearance_level, is_active, can_create_case, last_login)
            VALUES (:id, :email, :full_name, :role, :department, :badge_number, :clearance_level, :is_active, :can_create_case, :last_login)
            ON CONFLICT (id) DO UPDATE SET
                email = EXCLUDED.email,
                full_name = EXCLUDED.full_name,
                role = EXCLUDED.role,
                department = EXCLUDED.department,
                badge_number = EXCLUDED.badge_number,
                clearance_level = EXCLUDED.clearance_level,
                is_active = EXCLUDED.is_active,
                can_create_case = EXCLUDED.can_create_case,
                last_login = EXCLUDED.last_login
        """),
        {
            "id": user_id,
            "email": email,
            "full_name": full_name,
            "role": role,
            "department": department,
            "badge_number": badge_number,
            "clearance_level": clearance_level,
            "is_active": is_active,
            "can_create_case": can_create_case,
            "last_login": last_login
        }
    )
    db.commit()


def get_current_user_info(request: Request) -> dict:
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid authorization token.")
    token = auth_header.split(" ")[1]
    try:
        payload = decode_jwt(token)
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token payload.")
        
        # Check database to see if user is active
        supabase_user = {}
        try:
            user_res = supabase_admin.table("users").select("*").eq("id", user_id).execute()
            if user_res.data:
                supabase_user = user_res.data[0]
                if not supabase_user.get("is_active", True):
                    raise HTTPException(status_code=403, detail="Your account has been deactivated by an administrator.")
        except HTTPException:
            raise
        except Exception:
            pass

        # Sync the user to local PostgreSQL to ensure foreign keys can be resolved
        db = SessionLocal()
        try:
            sync_user_to_postgres({
                "id": user_id,
                "email": supabase_user.get("email") or payload.get("email"),
                "full_name": supabase_user.get("full_name") or payload.get("name"),
                "role": supabase_user.get("role") or payload.get("role"),
                "department": supabase_user.get("department"),
                "badge_number": supabase_user.get("badge_number"),
                "clearance_level": supabase_user.get("clearance_level", 1),
                "is_active": supabase_user.get("is_active", True),
                "can_create_case": supabase_user.get("can_create_case", True),
                "last_login": supabase_user.get("last_login")
            }, db)
        except Exception as e:
            print(f"[USER SYNC ERROR] Failed to sync user to local PostgreSQL: {e}")
        finally:
            db.close()
            
        return {
            "id": user_id,
            "email": payload.get("email"),
            "role": payload.get("role") or "Investigator",
            "name": payload.get("name") or "Investigator"
        }
    except pyjwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired. Please log in again.")
    except pyjwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token.")

def has_permission(user_info: dict, permission_name: str) -> bool:
    role = user_info.get("role", "Investigator")
    if role.lower() == "investigator" and permission_name == "create_case":
        if "can_create_case" in user_info:
            return bool(user_info["can_create_case"])
        try:
            user_id = user_info.get("id")
            if user_id:
                res = supabase_admin.table("users").select("can_create_case").eq("id", user_id).execute()
                if res.data:
                    return bool(res.data[0].get("can_create_case", True))
        except Exception as e:
            print(f"[PERMISSION CHECK WARNING] Failed to query user permission: {e}")
        return True

    # Case-insensitive role mapping fallback
    matched_role = "Investigator"
    for r in ROLE_PERMISSIONS:
        if r.lower() == role.lower():
            matched_role = r
            break
    role_cfg = ROLE_PERMISSIONS.get(matched_role)
    return bool(role_cfg["permissions"].get(permission_name, False))

def get_data_visibility(user_info: dict, visibility_type: str) -> str:
    role = user_info.get("role", "Investigator")
    matched_role = "Investigator"
    for r in ROLE_PERMISSIONS:
        if r.lower() == role.lower():
            matched_role = r
            break
    role_cfg = ROLE_PERMISSIONS.get(matched_role)
    return role_cfg["permissions"].get(visibility_type, "owned")

def check_case_access(case_id: str, user_info: dict, db: Session = None) -> bool:
    visibility = get_data_visibility(user_info, "view_cases")
    if visibility == "all":
        return True

    session = db or SessionLocal()
    try:
        case = session.query(Case.created_by).filter(Case.id == case_id).first()
        if not case:
            raise HTTPException(status_code=404, detail="Case not found")
        
        created_by = case[0]
        if created_by is not None and str(created_by) != user_info["id"]:
            raise HTTPException(status_code=403, detail="Forbidden: You do not have permission to access this case.")
    finally:
        if not db:
            session.close()
    return True



# ====== AUTH ENDPOINTS ======

@app.post("/auth/send-otp")
def send_otp(req: LoginRequest, db: Session = Depends(get_db)):
    """Step 1 — officer enters email, gets OTP sent to their registered email."""
    clean_email = req.email.strip()
    # Look up officer in users table
    try:
        user_res = supabase_admin.table("users").select("*").eq("email", clean_email).execute()
        if not user_res.data:
            raise HTTPException(status_code=404, detail="No active account found for this email.")
        user = user_res.data[0]
        if not user.get("is_active", True):
            raise HTTPException(status_code=403, detail="Your account has been deactivated by an administrator.")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

    # Ensure user exists in local PostgreSQL users table before inserting into otp_tokens
    try:
        sync_user_to_postgres(user, db)
    except Exception as e:
        db.rollback()
        print(f"[USER SYNC ERROR] Failed to sync user to local PostgreSQL in send_otp: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to synchronize user record: {str(e)}")

    # Generate 6-digit OTP
    otp = "".join(random.choices(string.digits, k=6))
    print(f"[DEBUG OTP] Generated OTP for {user['email']}: {otp}")
    expires_at = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=5)

    # Store OTP in PostgreSQL otp_tokens table
    try:
        u_id = uuid.UUID(user["id"])
        local_user = db.query(User).filter(User.id == u_id).first()
        if not local_user:
            db.add(User(
                id=u_id,
                email=user.get("email", ""),
                full_name=user.get("full_name", "Officer"),
                role=user.get("role", "Officer")
            ))
            db.commit()

        otp_db = OTPToken(
            id=uuid.uuid4(),
            user_id=u_id,
            token=otp,
            expires_at=expires_at,
            used=False
        )
        db.add(otp_db)
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to store OTP: {str(e)}")

    # Send OTP via Gmail
    try:
        send_otp_email(user["email"], otp, user["full_name"])
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to send email: {str(e)}")

    return {"success": True, "message": f"Token sent to {user['email']}. Valid for 5 minutes."}


@app.post("/auth/verify-otp")
def verify_otp(req: VerifyOTPRequest, db: Session = Depends(get_db)):
    """Step 2 — officer enters password + OTP, gets JWT back."""
    clean_email = req.email.strip()
    clean_otp = req.otp.strip()
    # Look up officer
    try:
        user_res = supabase_admin.table("users").select("*").eq("email", clean_email).execute()
        if not user_res.data:
            print("[AUTH DEBUG] FAILED: User lookup")
            raise HTTPException(status_code=404, detail="Account not found.")
        user = user_res.data[0]
        if not user.get("is_active", True):
            raise HTTPException(status_code=403, detail="Your account has been deactivated by an administrator.")
        print("[AUTH DEBUG] User found")
    except HTTPException:
        raise
    except Exception as e:
        print(f"[AUTH DEBUG] FAILED: User lookup - database error: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

    # Verify password via Supabase Auth
    try:
        sign_in_res = supabase.auth.sign_in_with_password({
            "email": clean_email,
            "password": req.password
        })
        if not sign_in_res.user:
            print("[AUTH DEBUG] FAILED: Password verification")
            raise HTTPException(status_code=401, detail="Invalid password.")
        print("[AUTH DEBUG] Password verification passed")
    except AuthApiError as ae:
        print(f"[AUTH DEBUG] FAILED: Password verification - AuthApiError: {ae}")
        raise HTTPException(status_code=401, detail="Invalid password.")
    except HTTPException:
        raise
    except Exception as e:
        print(f"[AUTH DEBUG] FAILED: Password verification - exception: {e}")
        raise HTTPException(status_code=401, detail="Invalid password.")

    # Verify OTP — find latest unused, non-expired token in PostgreSQL
    try:
        otp_record = db.query(OTPToken)\
            .filter(OTPToken.user_id == uuid.UUID(user["id"]), OTPToken.token == clean_otp)\
            .order_by(OTPToken.created_at.desc())\
            .first()

        if not otp_record:
            print("[AUTH DEBUG] FAILED: OTP not found")
            raise HTTPException(status_code=401, detail="Invalid or expired token. Request a new one.")
        
        print("[AUTH DEBUG] OTP record found")

        if otp_record.used:
            print("[AUTH DEBUG] FAILED: OTP already used")
            raise HTTPException(status_code=401, detail="Invalid or expired token. Request a new one.")
        print("[AUTH DEBUG] OTP unused")

        now_utc = datetime.datetime.now(datetime.timezone.utc)
        exp_at = otp_record.expires_at
        if exp_at.tzinfo is None:
            exp_at = exp_at.replace(tzinfo=datetime.timezone.utc)
        if exp_at < now_utc:
            print("[AUTH DEBUG] FAILED: OTP expired")
            raise HTTPException(status_code=401, detail="Invalid or expired token. Request a new one.")
        print("[AUTH DEBUG] OTP not expired")

    except HTTPException:
        raise
    except Exception as e:
        print(f"[AUTH DEBUG] FAILED: OTP verification error: {e}")
        raise HTTPException(status_code=500, detail=f"OTP verification error: {str(e)}")

    # Mark OTP as used
    try:
        if otp_record:
            otp_record.used = True
            db.commit()
    except Exception as e:
        db.rollback()
        print(f"[AUTH UPDATE WARNING] failed to mark OTP as used: {e}")

    # Issue JWT
    token = create_jwt(
        user_id=user["id"],
        email=user["email"],
        role=user["role"],
        name=user["full_name"]
    )
    print("[AUTH DEBUG] JWT generated")

    # Fetch last_sign_in_at and must_change_password dynamically from GoTrue Auth
    last_sign_in = None
    must_change_password = False
    try:
        auth_user = supabase_admin.auth.admin.get_user_by_id(user["id"])
        last_sign_in = auth_user.user.last_sign_in_at
        must_change_password = auth_user.user.user_metadata.get("must_change_password", False)
    except Exception as e:
        print(f"[AUTH METADATA WARNING] failed to fetch GoTrue last_sign_in_at: {e}")

    current_time = datetime.datetime.now(datetime.timezone.utc).isoformat()

    # Update last_login in Auth metadata
    try:
        auth_user = supabase_admin.auth.admin.get_user_by_id(user["id"])
        existing_meta = auth_user.user.user_metadata or {}
        supabase_admin.auth.admin.update_user_by_id(
            user["id"],
            attributes={"user_metadata": {**existing_meta, "last_login": current_time}}
        )
    except Exception as e:
        print(f"[AUTH UPDATE WARNING] failed to update GoTrue last_login: {e}")

    # Safely try to update users.last_login (in case the column is added)
    try:
        supabase_admin.table("users").update({"last_login": current_time}).eq("id", user["id"]).execute()
    except Exception as e:
        print(f"[DB UPDATE WARNING] failed to update users.last_login: {e}")

    write_audit_log(
        user_id=user["id"],
        action="Login Successful",
        metadata={"email": user["email"], "role": user["role"], "full_name": user["full_name"]}
    )

    return {
        "success": True,
        "data": {
            "token": token,
            "user": {
                "id": user["id"],
                "name": user["full_name"],
                "full_name": user["full_name"],
                "email": user["email"],
                "badge_id": user.get("badge_number", ""),
                "badge_number": user.get("badge_number", ""),
                "department": user.get("department", ""),
                "role": user["role"],
                "clearance_level": user.get("clearance_level", 1),
                "is_active": user.get("is_active", True),
                "status": "active" if user.get("is_active", True) else "inactive",
                "last_login": current_time,
                "last_sign_in_at": last_sign_in or current_time,
                "must_change_password": must_change_password,
                "can_create_case": has_permission(user, "create_case")
            }
        }
    }


@app.get("/auth/me")
def get_me(request: Request):
    """Validates JWT and returns current officer profile."""
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid authorization token.")

    token = auth_header.split(" ")[1]

    try:
        payload = decode_jwt(token)
    except pyjwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired. Please log in again.")
    except pyjwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token.")

    try:
        user_res = supabase_admin.table("users").select("*").eq("id", payload["sub"]).execute()
        if not user_res.data:
            raise HTTPException(status_code=404, detail="User not found.")
        user = user_res.data[0]
        if not user.get("is_active", True):
            raise HTTPException(status_code=403, detail="Your account has been deactivated by an administrator.")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

    # Fetch last_sign_in_at and must_change_password dynamically from GoTrue Auth
    last_sign_in = None
    must_change_password = False
    try:
        auth_user = supabase_admin.auth.admin.get_user_by_id(user["id"])
        last_sign_in = auth_user.user.last_sign_in_at
        must_change_password = auth_user.user.user_metadata.get("must_change_password", False)
    except Exception as e:
        pass

    return {
        "success": True,
        "data": {
            "id": user["id"],
            "name": user["full_name"],
            "full_name": user["full_name"],
            "email": user["email"],
            "badge_id": user.get("badge_number", ""),
            "badge_number": user.get("badge_number", ""),
            "department": user.get("department", ""),
            "role": user["role"],
            "clearance_level": user.get("clearance_level", 1),
            "is_active": user.get("is_active", True),
            "status": "active" if user.get("is_active", True) else "inactive",
            "last_login": user.get("last_login") or last_sign_in,
            "last_sign_in_at": last_sign_in,
            "must_change_password": must_change_password,
            "can_create_case": has_permission(user, "create_case")
        }
    }


@app.post("/auth/logout")
def logout(request: Request):
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
        try:
            payload = decode_jwt(token)
            user_id = payload["sub"]
            write_audit_log(
                user_id=user_id,
                action="Logout Successful",
                metadata={"email": payload.get("email"), "role": payload.get("role"), "full_name": payload.get("name")}
            )
        except Exception as e:
            print(f"[LOGOUT AUDIT FAILED] decoding JWT failed: {e}")
    try:
        supabase.auth.sign_out()
    except Exception:
        pass
    return {"success": True, "message": "Logged out successfully."}


@app.post("/auth/change-password")
def change_password(req: ChangePasswordRequest, request: Request):
    user_info = get_current_user_info(request)
    try:
        # Get existing metadata from Supabase Auth
        auth_user = supabase_admin.auth.admin.get_user_by_id(user_info["id"])
        existing_meta = auth_user.user.user_metadata or {}
        
        # Update password and clear must_change_password flag in Supabase Auth user_metadata
        supabase_admin.auth.admin.update_user_by_id(
            user_info["id"],
            attributes={
                "password": req.new_password,
                "user_metadata": {**existing_meta, "must_change_password": False}
            }
        )
        
        # Write "Password Changed" audit log
        write_audit_log(
            user_id=user_info["id"],
            action="Password Changed",
            metadata={"email": user_info["email"], "full_name": user_info["name"]}
        )
        
        return {"success": True, "message": "Password changed successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to change password: {str(e)}")

@app.post("/auth/reset-password")
def reset_password(req: ResetPasswordRequest, db: Session = Depends(get_db)):
    """Reset password using 2FA OTP sent to registered email."""
    try:
        user_res = supabase_admin.table("users").select("*").eq("email", req.email).execute()
        if not user_res.data:
            raise HTTPException(status_code=404, detail="Account not found.")
        user = user_res.data[0]
        if not user.get("is_active", True):
            raise HTTPException(status_code=403, detail="Your account has been deactivated.")

        otp_record = db.query(OTPToken)\
            .filter(OTPToken.user_id == uuid.UUID(user["id"]), OTPToken.token == req.otp)\
            .order_by(OTPToken.created_at.desc())\
            .first()

        if not otp_record or otp_record.used:
            raise HTTPException(status_code=401, detail="Invalid or expired verification code.")

        now_utc = datetime.datetime.now(datetime.timezone.utc)
        exp_at = otp_record.expires_at
        if exp_at.tzinfo is None:
            exp_at = exp_at.replace(tzinfo=datetime.timezone.utc)
        if exp_at < now_utc:
            raise HTTPException(status_code=401, detail="Verification code has expired.")

        auth_user = supabase_admin.auth.admin.get_user_by_id(user["id"])
        existing_meta = auth_user.user.user_metadata or {}

        supabase_admin.auth.admin.update_user_by_id(
            user["id"],
            attributes={
                "password": req.new_password,
                "user_metadata": {**existing_meta, "must_change_password": False}
            }
        )

        otp_record.used = True
        db.commit()

        write_audit_log(
            user_id=user["id"],
            action="Password Reset via OTP",
            metadata={"email": user["email"], "full_name": user["full_name"]}
        )

        return {"success": True, "message": "Password reset successfully. You can now log in with your new passphrase."}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to reset password: {str(e)}")


# ====== AUDIT LOG HELPER ======
def write_audit_log(user_id: str, action: str, case_id: str = None, file_hash: str = None, metadata: dict = None, db: Session = None):
    """Append-only audit log writer. Never updates, never deletes."""
    own_session = False
    if db is None:
        db = SessionLocal()
        own_session = True
    try:
        parsed_case_id = None
        if case_id:
            if isinstance(case_id, str):
                try:
                    parsed_case_id = uuid.UUID(case_id)
                except ValueError:
                    parsed_case_id = None
            elif isinstance(case_id, uuid.UUID):
                parsed_case_id = case_id

        log_entry = AuditLog(
            user_id=user_id or "system",
            action=action,
            case_id=parsed_case_id,
            file_hash=file_hash,
            metadata_=metadata
        )
        db.add(log_entry)
        db.commit()
    except Exception as e:
        db.rollback()
        # Never crash the main request due to audit failure — just log to console
        print(f"[AUDIT LOG FAILED] {action}: {e}")
    finally:
        if own_session:
            db.close()

# ====== CASE ENDPOINTS ======
@app.post("/cases")
def create_case(case_data: CaseCreate, request: Request, db: Session = Depends(get_db)):
    user_info = get_current_user_info(request)
    if not has_permission(user_info, "create_case"):
        raise HTTPException(status_code=403, detail="Forbidden: You do not have permission to create cases.")

    current_year = datetime.datetime.now().year
    start_date = datetime.datetime(current_year, 1, 1, tzinfo=datetime.timezone.utc)
    end_date = datetime.datetime(current_year, 12, 31, 23, 59, 59, 999999, tzinfo=datetime.timezone.utc)

    try:
        count = db.query(Case.id).filter(Case.created_at >= start_date, Case.created_at <= end_date).count()
    except Exception as e:
        print(f"[CASE NUMBER GENERATION ERROR] count failed: {e}")
        count = 0

    sequence_num = count + 1
    while True:
        case_number = f"SA-{current_year}-{sequence_num:04d}"
        try:
            dup_check = db.query(Case.id).filter(Case.case_number == case_number).first()
            if not dup_check:
                break
        except Exception:
            break
        sequence_num += 1

    # Safely parse date and time strings
    inc_date = None
    if case_data.incident_date:
        try:
            inc_date = datetime.date.fromisoformat(case_data.incident_date)
        except ValueError:
            pass

    inc_time = None
    if case_data.incident_time:
        try:
            parts = case_data.incident_time.split(":")
            if len(parts) >= 2:
                inc_time = datetime.time(int(parts[0]), int(parts[1]), int(parts[2]) if len(parts) > 2 else 0)
        except ValueError:
            pass

    db_case = Case(
        title=case_data.title,
        offence_type=case_data.offence_type,
        fir_description=case_data.fir_description,
        fir_language=case_data.fir_language,
        complainant_name=case_data.complainant_name,
        complainant_contact=case_data.complainant_contact,
        victims=case_data.victims,
        suspects=case_data.suspects,
        incident_date=inc_date,
        incident_time=inc_time,
        incident_location=case_data.incident_location,
        case_number=case_number,
        created_by=uuid.UUID(user_info["id"]) if user_info["id"] else None,
        created_by_name=user_info["name"]
    )

    try:
        db.add(db_case)
        db.commit()
        db.refresh(db_case)
        new_case = serialize_case(db_case)
        
        write_audit_log(
            user_id=user_info["id"],
            action="Case Created",
            case_id=new_case["id"],
            metadata={"title": new_case.get("title"), "offence_type": new_case.get("offence_type")},
            db=db
        )
        return {"data": new_case}
    except Exception as e:
        db.rollback()
        print(f"[CASE CREATE ERROR] {e}")
        raise HTTPException(status_code=400, detail="Failed to create case")

@app.get("/cases")
def get_cases(request: Request, search: str = None, db: Session = Depends(get_db)):
    user_info = get_current_user_info(request)
    visibility = get_data_visibility(user_info, "view_cases")

    try:
        query = db.query(Case)
        if visibility == "owned":
            user_uuid = uuid.UUID(user_info['id']) if user_info['id'] else None
            query = query.filter((Case.created_by == user_uuid) | (Case.created_by.is_(None)))

        if search:
            query = query.filter(Case.title.ilike(f"%{search}%"))

        cases = query.order_by(Case.created_at.desc()).all()
        
        serialized_cases = []
        for case in cases:
            row = serialize_case(case)
            row["case_number"] = row.get("case_number") or f'SA-{row["id"][:4].upper()}'
            row["status"] = "Open"
            serialized_cases.append(row)
            
        return {"data": serialized_cases}
    except Exception as e:
        print(f"[FALLBACK] get_cases failed: {e}")
        # Return a mock case so the app works even offline or if table doesn't exist
        mock_cases = [
            {
                "id": "11111111-2222-3333-4444-555555555555",
                "case_number": "SA-DEMO",
                "title": "Suspected Weapon Storage",
                "offence_type": "Illegal Arms Possession",
                "status": "Open",
                "priority": "High",
                "fir_description": "First Information Report regarding suspicious activity and stored weapons.",
                "complainant_name": "Ravi Kumar",
                "complainant_contact": "+91 98765 43210",
                "victims": [{"name": "State"}],
                "suspects": [{"name": "John Doe"}],
                "incident_date": "2026-05-15",
                "incident_time": "14:30",
                "incident_location": "Warehouse 4, Sector 7",
                "created_at": "2026-05-15T14:30:00Z"
            }
        ]
        return {"data": mock_cases}

@app.get("/cases/stats")
def get_case_stats(request: Request, db: Session = Depends(get_db)):
    user_info = get_current_user_info(request)
    visibility = get_data_visibility(user_info, "view_cases")

    if visibility == "all":
        # Admin: System-wide metrics
        try:
            active_count = db.query(Case.id).count()
        except Exception as e:
            print(f"[STATS CASES ERROR] {e}")
            active_count = 0
            
        try:
            total_evidence = db.query(Evidence.id).count()
        except Exception as e:
            print(f"[STATS EVIDENCE COUNT ERROR] {e}")
            total_evidence = 0

        # Count real tampered evidence
        try:
            tamper_count = db.query(Evidence.id).filter(Evidence.status == "Tampered").count()
        except Exception as e:
            print(f"[STATS TAMPERED COUNT ERROR] {e}")
            tamper_count = 0
            
        # Count BNS classifications
        try:
            bns_count = db.query(BNSPrediction.id).count()
        except Exception as e:
            print(f"[STATS BNS COUNT ERROR] {e}")
            bns_count = 0

        # Count total active users for admin dashboard
        try:
            users_res = supabase_admin.table("users").select("id", count="exact").eq("is_active", True).execute()
            total_users = users_res.count if users_res.count is not None else len(users_res.data)
        except:
            total_users = 0

        return {"data": {
            "active": active_count,
            "total_evidence": total_evidence,
            "tamper_alerts": tamper_count,
            "bns_classified": bns_count,
            "total_users": total_users
        }}
    else:
        # Investigator: Scoped metrics
        try:
            user_uuid = uuid.UUID(user_info['id']) if user_info['id'] else None
            cases_res = db.query(Case.id).filter((Case.created_by == user_uuid) | (Case.created_by.is_(None))).all()
            case_ids = [str(c[0]) for c in cases_res]
            active_count = len(case_ids)
        except Exception as e:
            print(f"[STATS SCOPED CASES ERROR] {e}")
            active_count = 0
            case_ids = []

        try:
            if case_ids:
                case_uuids = [uuid.UUID(cid) for cid in case_ids]
                total_evidence = db.query(Evidence.id).filter(Evidence.case_id.in_(case_uuids)).count()
            else:
                total_evidence = 0
        except Exception as e:
            print(f"[STATS EVIDENCE ERROR] {e}")
            total_evidence = 0

        try:
            if case_ids:
                case_ids_str = ",".join([f'"{cid}"' for cid in case_ids])
                det_res = supabase_admin.table("detections").select("id", count="exact").filter("case_id", "in", f"({case_ids_str})").execute()
                ai_count = det_res.count if det_res.count is not None else len(det_res.data)
            else:
                ai_count = 0
        except Exception:
            ai_count = 0

        try:
            audit_count = db.query(AuditLog.id).filter(AuditLog.user_id == user_info["id"]).count()
        except Exception as e:
            print(f"[STATS AUDIT COUNT ERROR] {e}")
            audit_count = 0

        return {"data": {
            "active": active_count,
            "total_evidence": total_evidence,
            "ai_analyses": ai_count,
            "my_audit_logs": audit_count
        }}

@app.get("/cases/{case_id}")
def get_case(case_id: str, request: Request, db: Session = Depends(get_db)):
    user_info = get_current_user_info(request)
    check_case_access(case_id, user_info, db)

    try:
        case = db.query(Case).filter(Case.id == case_id).first()
        if case:
            row = serialize_case(case)
            row["case_number"] = row.get("case_number") or f'SA-{row["id"][:4].upper()}'
            row["status"] = "Open"
            return {"data": row}
    except Exception as e:
        print(f"[FALLBACK] get_case failed: {e}")
        
    # Return a demo case if the request is for the demo case
    if case_id == "11111111-2222-3333-4444-555555555555":
        return {
            "data": {
                "id": "11111111-2222-3333-4444-555555555555",
                "case_number": "SA-DEMO",
                "title": "Suspected Weapon Storage",
                "offence_type": "Illegal Arms Possession",
                "status": "Open",
                "priority": "High",
                "fir_description": "First Information Report regarding suspicious activity and stored weapons.",
                "complainant_name": "Ravi Kumar",
                "complainant_contact": "+91 98765 43210",
                "victims": [{"name": "State"}],
                "suspects": [{"name": "John Doe"}],
                "incident_date": "2026-05-15",
                "incident_time": "14:30",
                "incident_location": "Warehouse 4, Sector 7",
                "created_at": "2026-05-15T14:30:00Z"
            }
        }
    raise HTTPException(status_code=404, detail="Case not found")

# ====== EVIDENCE ENDPOINTS ======
@app.post("/evidence/upload")
def upload_evidence(
    request: Request,
    case_id: str = Form(...),
    evidence_type: str = Form(...),
    description: Optional[str] = Form(None),
    language: Optional[str] = Form(None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    user_info = get_current_user_info(request)
    if not has_permission(user_info, "upload_evidence"):
        raise HTTPException(status_code=403, detail="Forbidden: You do not have permission to upload evidence.")
    
    check_case_access(case_id, user_info, db)

    try:
        # Read file bytes in memory
        file_bytes = file.file.read()
        file_size = len(file_bytes)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to read upload file: {str(e)}")

    # ── 1. Hash the file ─────────────────────────────────────────────────────
    sha256_hash = hashlib.sha256(file_bytes)
    hash_hex = sha256_hash.hexdigest()

    # ── 2. Duplicate detection ────────────────────────────────────────────────
    try:
        case_uuid = uuid.UUID(case_id) if case_id else None
        dup_check = db.query(Evidence.id).filter(Evidence.case_id == case_uuid, Evidence.file_hash == hash_hex).first()
        if dup_check:
            dup_id_str = str(dup_check[0])
            return JSONResponse(
                status_code=409,
                content={
                    "detail": f"Duplicate file detected. This file was already uploaded (evidence ID: {dup_id_str}). SHA-256: {hash_hex[:16]}...",
                    "evidence_id": dup_id_str,
                    "duplicate": True
                }
            )
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        pass  # if duplicate check fails, continue — don't block uploads

    # ── 3. Upload to local storage or Supabase Storage ────────────────────────
    file_uuid = str(uuid.uuid4())
    original_filename = os.path.basename(file.filename or "uploaded_evidence")

    if USE_LOCAL_STORAGE:
        # Create local directory uploads/cases/{case_id}
        local_dir = os.path.join(UPLOADS_DIR, "cases", case_id)
        os.makedirs(local_dir, exist_ok=True)
        local_file_path = os.path.join(local_dir, f"{file_uuid}_{original_filename}")
        try:
            with open(local_file_path, "wb") as f:
                f.write(file_bytes)
            # Create a URL relative to the FastAPI base URL
            base_url = str(request.base_url)
            file_url = f"{base_url}uploads/cases/{case_id}/{file_uuid}_{original_filename}"
        except Exception as e:
            print(f"[LOCAL UPLOAD FAILED] {e}")
            raise HTTPException(status_code=500, detail=f"Failed to write file locally: {str(e)}")
    else:
        # Path format: cases/{case_id}/{file_uuid}_{original_filename}
        storage_path = f"cases/{case_id}/{file_uuid}_{original_filename}"

        try:
            supabase_admin.storage.from_("evidence").upload(
                path=storage_path,
                file=file_bytes,
                file_options={"content-type": file.content_type}
            )
        except Exception as e:
            print(f"[STORAGE UPLOAD FAILED] {e}")
            raise HTTPException(status_code=500, detail=f"Failed to upload file to Supabase Storage: {str(e)}")

        # Retrieve public URL
        try:
            file_url = supabase_admin.storage.from_("evidence").get_public_url(storage_path)
            if file_url.endswith("?"):
                file_url = file_url[:-1]
        except Exception:
            file_url = f"{SUPABASE_URL}/storage/v1/object/public/evidence/{storage_path}"

    # Flush relational metadata, wait for a mined chain receipt, then commit both.
    db_evidence = Evidence(
        case_id=uuid.UUID(case_id) if case_id else None,
        evidence_type=evidence_type,
        description=description,
        file_url=file_url,
        file_hash=hash_hex,
        file_name=original_filename,
        file_size=file_size,
        mime_type=file.content_type,
        uploaded_by=uuid.UUID(user_info["id"]) if user_info["id"] else None,
        uploaded_by_name=user_info["name"],
        chain_of_custody_status="Collected",
        status="Verified"
    )

    try:
        db.add(db_evidence)
        db.flush()
        registration = blockchain_service.register_evidence(str(db_evidence.id), case_id, original_filename, hash_hex, user_info["id"])
        db_evidence.blockchain_tx_hash = registration["transactionHash"]
        db_evidence.blockchain_block_number = registration["blockNumber"]
        db_evidence.blockchain_contract_address = registration["contractAddress"]
        db_evidence.blockchain_gas_used = registration["gasUsed"]
        db_evidence.blockchain_registered_at = registration["timestamp"]
        db.add(EvidenceCustodyRecord(evidence_id=db_evidence.id, officer_id=user_info["id"], action="REGISTERED", occurred_at=registration["timestamp"], transaction_hash=registration["transactionHash"], block_number=registration["blockNumber"]))
        db.add(BlockchainLog(evidence_id=db_evidence.id, event_name="EvidenceRegistered", transaction_hash=registration["transactionHash"], block_number=registration["blockNumber"], payload={"contractAddress": registration["contractAddress"], "gasUsed": registration["gasUsed"]}))
        db.commit()
        db.refresh(db_evidence)
        evidence_row = serialize_evidence(db_evidence)
        
        # Ensure returned dictionary contains expected keys for the frontend
        evidence_row["file_name"] = original_filename
        evidence_row["file_type"] = evidence_type
        evidence_row["file_size"] = file_size
        evidence_row["sha256_hash"] = hash_hex

        # ── 5. Audit log ─────────────────────────────────────────────────────
        write_audit_log(
            user_id=user_info["id"],
            action="Evidence Upload",
            case_id=case_id,
            file_hash=hash_hex,
            metadata={
                "file_name": original_filename,
                "file_size": file_size,
                "evidence_id": evidence_row["id"],
                "evidence_type": evidence_type
            },
            db=db
        )
        logger.info("Evidence %s registered on chain: %s", db_evidence.id, registration["transactionHash"])
        return {"data": evidence_row, "success": True}
    except (BlockchainUnavailable, BlockchainTransactionError) as e:
        db.rollback()
        logger.exception("Blockchain registration failed; rolling back evidence upload")
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        db.rollback()
        print(f"[EVIDENCE UPLOAD DB ERROR] {e}")
        raise HTTPException(status_code=400, detail="Failed to upload evidence")

@app.get("/evidence")
def get_evidence(request: Request, case_id: Optional[str] = None, db: Session = Depends(get_db)):
    user_info = get_current_user_info(request)
    
    # Check case access
    if case_id:
        check_case_access(case_id, user_info, db)
        allowed_case_ids = [case_id]
    else:
        # If case_id is not provided, check visibility rules
        visibility = get_data_visibility(user_info, "view_cases")
        if visibility == "owned":
            try:
                user_uuid = uuid.UUID(user_info['id']) if user_info['id'] else None
                cases_res = db.query(Case.id).filter((Case.created_by == user_uuid) | (Case.created_by.is_(None))).all()
                allowed_case_ids = [str(c[0]) for c in cases_res]
            except Exception:
                allowed_case_ids = []
        else:
            allowed_case_ids = None

    try:
        query = db.query(Evidence)
        if case_id:
            case_uuid = uuid.UUID(case_id) if case_id else None
            query = query.filter(Evidence.case_id == case_uuid)
        elif allowed_case_ids is not None:
            if not allowed_case_ids:
                return {"data": []}
            allowed_uuids = [uuid.UUID(cid) for cid in allowed_case_ids]
            query = query.filter(Evidence.case_id.in_(allowed_uuids))
            
        evidences = query.order_by(Evidence.created_at.desc()).all()
        serialized_evidences = []
        for ev_obj in evidences:
            row = serialize_evidence(ev_obj)
            row["file_name"] = row.get("file_name") or ("Evidence " + row["id"][:4])
            row["file_type"] = row.get("evidence_type", "Image")
            row["file_size"] = row.get("file_size") or 1048576
            row["status"] = row.get("status", "Verified")
            row["sha256_hash"] = row.get("file_hash") or ("hash_" + row["id"][:8])
            row["uploaded_at"] = row.get("created_at")
            serialized_evidences.append(row)
        return {"data": serialized_evidences}
    except Exception as e:
        print(f"[FALLBACK] get_evidence failed: {e}")
        # Return mock evidence if it's the demo case
        if case_id == "11111111-2222-3333-4444-555555555555":
            return {
                "data": [
                    {
                        "id": "e1e1e1e1-e2e2-e3e3-e4e4-e5e5e5e5e5e5",
                        "case_id": "11111111-2222-3333-4444-555555555555",
                        "file_name": "weapon_cache.jpg",
                        "file_type": "Image",
                        "file_size": 256000,
                        "file_url": "uploads/demo_weapon.jpg",
                        "status": "Verified",
                        "sha256_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
                        "created_at": "2026-05-15T15:00:00Z",
                        "uploaded_at": "2026-05-15T15:00:00Z"
                    }
                ]
            }
        return {"data": []}

# ── 5. Hash verification endpoint ────────────────────────────────────────────
class EvidenceFileMissing(Exception):
    """The evidence file no longer exists at its recorded location."""


def compute_evidence_file_hash(file_url: str) -> str:
    """SHA-256 of the stored evidence file.

    Raises ``EvidenceFileMissing`` when the file is gone, and HTTPException
    (502/500) when storage cannot be read for other reasons — an outage is not
    evidence of tampering, so callers must not change the evidence status then.
    """
    def hash_local(path: str) -> str:
        if not os.path.isfile(path):
            raise EvidenceFileMissing(f"Evidence file not found on local disk: {path}")
        sha256 = hashlib.sha256()
        try:
            with open(path, "rb") as f:
                while chunk := f.read(8192):
                    sha256.update(chunk)
        except OSError as e:
            raise HTTPException(status_code=500, detail=f"Failed to read local evidence file: {e}")
        return sha256.hexdigest()

    if "/uploads/" in file_url:
        relative_path = file_url.split("/uploads/")[-1]
        return hash_local(os.path.join(UPLOADS_DIR, relative_path.replace("/", os.sep)))
    if file_url.startswith(("http://", "https://")):
        try:
            response = requests.get(file_url, timeout=30)
        except requests.RequestException as e:
            raise HTTPException(status_code=502, detail=f"Could not reach evidence storage: {e}")
        # Supabase Storage answers 400 {"error": "not_found"} for missing public objects.
        if response.status_code == 404 or (response.status_code == 400 and "not_found" in response.text.lower()):
            raise EvidenceFileMissing("Evidence file not found in Supabase Storage")
        if response.status_code != 200:
            raise HTTPException(status_code=502, detail=f"Evidence storage returned HTTP {response.status_code}")
        return hashlib.sha256(response.content).hexdigest()
    return hash_local(file_url)


@app.post("/evidence/{evidence_id}/verify")
def verify_evidence_hash(evidence_id: str, request: Request, db: Session = Depends(get_db)):
    """Recomputes SHA-256 from disk or storage and verifies it on the blockchain.

    The verdict is the smart contract's own result (EvidenceVerified.isMatch)
    for the recomputed file hash. The database hash is reported alongside the
    on-chain hash and any difference between them is flagged.
    """
    user_info = get_current_user_info(request)

    evidence_obj = db.query(Evidence).filter(Evidence.id == evidence_id).first()
    if not evidence_obj:
        raise HTTPException(status_code=404, detail="Evidence not found")

    evidence = serialize_evidence(evidence_obj)
    case_id = evidence.get("case_id")
    check_case_access(case_id, user_info, db)

    stored_hash = evidence.get("file_hash")
    file_path = evidence.get("file_url")
    if not file_path:
        raise HTTPException(status_code=400, detail="No file URL for this evidence record")

    def set_status(status: str, audit_action: str, metadata: dict) -> None:
        try:
            evidence_obj.status = status
            evidence_obj.verified_at = datetime.datetime.now(datetime.timezone.utc)
            evidence_obj.verified_by = uuid.UUID(user_info["id"]) if user_info["id"] else None
            db.commit()
        except Exception as e:
            db.rollback()
            print(f"[VERIFY STATUS UPDATE FAILED] {e}")
        write_audit_log(user_id=user_info["id"], action=audit_action, case_id=case_id, file_hash=stored_hash,
                        metadata={"evidence_id": evidence_id, **metadata}, db=db)

    try:
        current_hash = compute_evidence_file_hash(file_path)
    except EvidenceFileMissing as e:
        set_status("Missing", "Evidence File Missing", {"file_url": file_path, "reason": str(e)})
        raise HTTPException(status_code=404, detail=f"{e}. Integrity cannot be verified; the evidence is now marked Missing.")

    try:
        registration = blockchain_service.get_registration(evidence_id)
        if registration is None:
            set_status("Unregistered", "Evidence Not Registered On-Chain",
                       {"computed_hash": current_hash, "database_hash": stored_hash})
            raise HTTPException(status_code=409, detail="Evidence is not registered on the blockchain, so its integrity "
                                                        "cannot be verified. It is now marked Unregistered.")
        is_verified, chain_result = blockchain_service.verify_evidence(evidence_id, current_hash, user_info["id"])
        on_chain = blockchain_service.custody_history(evidence_id)
    except (BlockchainUnavailable, BlockchainTransactionError) as e:
        logger.exception("Blockchain verification failed for %s", evidence_id)
        raise HTTPException(status_code=503, detail=str(e))

    blockchain_hash = chain_result["onChainHash"]
    database_matches_blockchain = stored_hash == blockchain_hash
    status = "Verified" if is_verified else "Tampered"
    warnings = []
    if not database_matches_blockchain:
        warnings.append("The hash stored in the database differs from the hash registered on the blockchain; "
                        "the database record may have been altered. The blockchain hash is authoritative.")

    # Update status and verification metadata
    try:
        evidence_obj.verified_at = datetime.datetime.now(datetime.timezone.utc)
        evidence_obj.verified_by = uuid.UUID(user_info["id"]) if user_info["id"] else None
        evidence_obj.status = status
        evidence_obj.latest_verification_at = chain_result["timestamp"]
        custody = chain_result["custodyTransaction"]
        db.add(EvidenceCustodyRecord(evidence_id=evidence_obj.id, officer_id=user_info["id"], action="VERIFIED", occurred_at=custody["timestamp"], transaction_hash=custody["transactionHash"], block_number=custody["blockNumber"]))
        db.add(BlockchainLog(
            evidence_id=evidence_obj.id,
            event_name="EvidenceVerified",
            transaction_hash=chain_result["transactionHash"],
            block_number=chain_result["blockNumber"],
            payload={
                "isMatch": is_verified,
                "status": status,
                "calculatedHash": current_hash,
                "blockchainHash": blockchain_hash,
                "databaseHash": stored_hash,
                "contractAddress": chain_result.get("contractAddress"),
                "gasUsed": chain_result.get("gasUsed")
            }
        ))
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"[VERIFY UPDATE FAILED] {e}")
        raise HTTPException(status_code=500, detail="Failed to update verification status")

    # Log verification attempt (both clean and tampered)
    write_audit_log(
        user_id=user_info["id"],
        action="Hash Verified" if is_verified else "Tamper Detected",
        case_id=case_id,
        file_hash=current_hash,
        metadata={
            "evidence_id": evidence_id,
            "stored_hash": stored_hash,
            "blockchain_hash": blockchain_hash,
            "computed_hash": current_hash,
            "match": is_verified,
            "transaction_hash": chain_result["transactionHash"]
        },
        db=db
    )
    if not database_matches_blockchain:
        write_audit_log(user_id=user_info["id"], action="Database Hash Mismatch", case_id=case_id, file_hash=stored_hash,
                        metadata={"evidence_id": evidence_id, "database_hash": stored_hash, "blockchain_hash": blockchain_hash},
                        db=db)

    return {
        "data": {
            "isVerified": is_verified,
            "verified": is_verified,
            "storedHash": stored_hash,
            "stored_hash": stored_hash,
            "calculatedHash": current_hash,
            "computed_hash": current_hash,
            "databaseHash": stored_hash,
            "blockchainHash": blockchain_hash,
            "fileMatchesBlockchain": is_verified,
            "databaseMatchesBlockchain": database_matches_blockchain,
            "verificationSource": "blockchain",
            "warnings": warnings,
            "transactionHash": chain_result["transactionHash"],
            "blockNumber": chain_result["blockNumber"],
            "custodyHistory": on_chain,
            "status": status
        },
        "success": True
    }


@app.get("/evidence/{evidence_id}/blockchain")
def evidence_blockchain_details(evidence_id: str, request: Request, db: Session = Depends(get_db)):
    user_info = get_current_user_info(request)
    evidence = db.query(Evidence).filter(Evidence.id == evidence_id).first()
    if not evidence:
        raise HTTPException(status_code=404, detail="Evidence not found")
    check_case_access(str(evidence.case_id), user_info, db)
    try:
        custody = blockchain_service.custody_history(evidence_id)
    except BlockchainUnavailable as e:
        raise HTTPException(status_code=503, detail=str(e))
    return {"data": {"status": blockchain_service.status(), "evidence": serialize_evidence(evidence)["blockchain"], "custodyHistory": custody}, "success": True}


class CustodyTransferRequest(BaseModel):
    officer_id: str


@app.post("/evidence/{evidence_id}/custody/transfer")
def transfer_evidence_custody(evidence_id: str, body: CustodyTransferRequest, request: Request, db: Session = Depends(get_db)):
    user_info = get_current_user_info(request)
    evidence = db.query(Evidence).filter(Evidence.id == evidence_id).first()
    if not evidence:
        raise HTTPException(status_code=404, detail="Evidence not found")
    check_case_access(str(evidence.case_id), user_info, db)
    if not body.officer_id.strip():
        raise HTTPException(status_code=422, detail="officer_id is required")
    try:
        result = blockchain_service.transfer_custody(evidence_id, body.officer_id.strip())
        db.add(EvidenceCustodyRecord(evidence_id=evidence.id, officer_id=body.officer_id.strip(), action="TRANSFERRED", occurred_at=result["timestamp"], transaction_hash=result["transactionHash"], block_number=result["blockNumber"]))
        db.add(BlockchainLog(
            evidence_id=evidence.id,
            event_name="CustodyTransferred",
            transaction_hash=result["transactionHash"],
            block_number=result["blockNumber"],
            payload={
                "officerId": body.officer_id.strip(),
                "contractAddress": result.get("contractAddress"),
                "gasUsed": result.get("gasUsed")
            }
        ))
        db.commit()
        write_audit_log(user_info["id"], "Evidence Custody Transferred", str(evidence.case_id), evidence.file_hash, {"evidence_id": evidence_id, "officer_id": body.officer_id, "transaction_hash": result["transactionHash"]}, db)
        return {"data": result, "success": True}
    except (BlockchainUnavailable, BlockchainTransactionError) as e:
        db.rollback()
        raise HTTPException(status_code=503, detail=str(e))


@app.get("/blockchain/status")
def blockchain_status():
    status = blockchain_service.status()
    return {
        "network": "Ganache" if status.get("connected") else "Unavailable",
        "status": "online" if status.get("connected") else "offline",
        "connected": status.get("connected", False),
        "chainId": status.get("chainId"),
        "chain_id": status.get("chainId"),
        "contractAddress": status.get("contractAddress"),
        "contract_address": status.get("contractAddress"),
        "latestBlock": status.get("latestBlock"),
        "latest_block": status.get("latestBlock"),
        "sender": status.get("sender"),
        "error": status.get("error"),
        "success": True
    }


class BlockchainRegisterRequest(BaseModel):
    evidence_id: str
    case_id: str
    file_name: str
    sha256_hash: str
    officer_id: Optional[str] = None


@app.post("/blockchain/register")
def blockchain_register(body: BlockchainRegisterRequest, request: Request, db: Session = Depends(get_db)):
    user_info = get_current_user_info(request)
    officer_id = body.officer_id or user_info.get("id") or "system"
    try:
        receipt = blockchain_service.register_evidence(
            evidence_id=body.evidence_id,
            case_id=body.case_id,
            file_name=body.file_name,
            sha256_hash=body.sha256_hash,
            officer_id=str(officer_id)
        )
        
        # Sync with local database if evidence record exists
        evidence = None
        try:
            val_uuid = uuid.UUID(str(body.evidence_id))
            evidence = db.query(Evidence).filter(Evidence.id == val_uuid).first()
        except (ValueError, TypeError, AttributeError):
            evidence = None

        if evidence:
            evidence.blockchain_tx_hash = receipt["transactionHash"]
            evidence.blockchain_block_number = receipt["blockNumber"]
            evidence.blockchain_contract_address = receipt["contractAddress"]
            evidence.blockchain_gas_used = receipt["gasUsed"]
            evidence.blockchain_registered_at = receipt["timestamp"]
            evidence.status = "Verified"
            
            db.add(EvidenceCustodyRecord(
                evidence_id=evidence.id,
                officer_id=str(officer_id),
                action="REGISTERED",
                occurred_at=receipt["timestamp"],
                transaction_hash=receipt["transactionHash"],
                block_number=receipt["blockNumber"]
            ))
            db.add(BlockchainLog(
                evidence_id=evidence.id,
                event_name="EvidenceRegistered",
                transaction_hash=receipt["transactionHash"],
                block_number=receipt["blockNumber"],
                payload={
                    "caseId": body.case_id,
                    "fileName": body.file_name,
                    "sha256Hash": body.sha256_hash,
                    "officerId": str(officer_id),
                    "contractAddress": receipt["contractAddress"],
                    "gasUsed": receipt["gasUsed"]
                }
            ))
        else:
            db.add(BlockchainLog(
                event_name="EvidenceRegistered",
                transaction_hash=receipt["transactionHash"],
                block_number=receipt["blockNumber"],
                payload={
                    "evidenceId": body.evidence_id,
                    "caseId": body.case_id,
                    "fileName": body.file_name,
                    "sha256Hash": body.sha256_hash,
                    "officerId": str(officer_id),
                    "contractAddress": receipt["contractAddress"],
                    "gasUsed": receipt["gasUsed"]
                }
            ))
        db.commit()

        formatted_receipt = {
            "transactionHash": receipt["transactionHash"],
            "blockNumber": receipt["blockNumber"],
            "gasUsed": receipt["gasUsed"],
            "contractAddress": receipt["contractAddress"],
            "timestamp": receipt["timestamp"].isoformat()
        }
        return {"data": formatted_receipt, "success": True}
    except (BlockchainUnavailable, BlockchainTransactionError) as e:
        db.rollback()
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        db.rollback()
        logger.exception("Error in blockchain register: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


class BlockchainVerifyRequest(BaseModel):
    evidence_id: str
    sha256_hash: str
    officer_id: Optional[str] = None


@app.post("/blockchain/verify")
def blockchain_verify(body: BlockchainVerifyRequest, request: Request, db: Session = Depends(get_db)):
    user_info = get_current_user_info(request)
    officer_id = body.officer_id or user_info.get("id") or "system"
    try:
        is_match, verification = blockchain_service.verify_evidence(
            evidence_id=body.evidence_id,
            sha256_hash=body.sha256_hash,
            officer_id=str(officer_id)
        )
        
        evidence = None
        try:
            val_uuid = uuid.UUID(str(body.evidence_id))
            evidence = db.query(Evidence).filter(Evidence.id == val_uuid).first()
        except (ValueError, TypeError, AttributeError):
            evidence = None

        if evidence:
            # The hash here is supplied by the caller, not computed from the
            # stored file, so it must not change the evidence status; only
            # POST /evidence/{id}/verify (server-side re-hash) does that.
            custody = verification.get("custodyTransaction", {})
            db.add(EvidenceCustodyRecord(
                evidence_id=evidence.id,
                officer_id=str(officer_id),
                action="VERIFIED",
                occurred_at=custody.get("timestamp", verification["timestamp"]),
                transaction_hash=custody.get("transactionHash"),
                block_number=custody.get("blockNumber")
            ))
            db.add(BlockchainLog(
                evidence_id=evidence.id,
                event_name="EvidenceVerified",
                transaction_hash=verification["transactionHash"],
                block_number=verification["blockNumber"],
                payload={
                    "isMatch": is_match,
                    "status": "Verified" if is_match else "Tampered",
                    "calculatedHash": body.sha256_hash,
                    "officerId": str(officer_id),
                    "contractAddress": verification.get("contractAddress"),
                    "gasUsed": verification.get("gasUsed")
                }
            ))
        else:
            db.add(BlockchainLog(
                event_name="EvidenceVerified",
                transaction_hash=verification["transactionHash"],
                block_number=verification["blockNumber"],
                payload={
                    "evidenceId": body.evidence_id,
                    "isMatch": is_match,
                    "status": "Verified" if is_match else "Tampered",
                    "calculatedHash": body.sha256_hash,
                    "officerId": str(officer_id),
                    "contractAddress": verification.get("contractAddress"),
                    "gasUsed": verification.get("gasUsed")
                }
            ))
        db.commit()

        return {
            "data": {
                "verified": is_match,
                "isMatch": is_match,
                "status": "Verified" if is_match else "Tampered",
                "transactionHash": verification["transactionHash"],
                "blockNumber": verification["blockNumber"],
                "gasUsed": verification.get("gasUsed"),
                "timestamp": verification["timestamp"].isoformat()
            },
            "success": True
        }
    except (BlockchainUnavailable, BlockchainTransactionError) as e:
        db.rollback()
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        db.rollback()
        logger.exception("Error in blockchain verify: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/blockchain/history/{evidence_id}")
def blockchain_evidence_history(evidence_id: str, request: Request, db: Session = Depends(get_db)):
    user_info = get_current_user_info(request)
    try:
        chain_history = blockchain_service.custody_history(evidence_id)
    except BlockchainUnavailable as e:
        raise HTTPException(status_code=503, detail=str(e))
    
    try:
        try:
            val_uuid = uuid.UUID(str(evidence_id))
            logs = db.query(BlockchainLog).filter(
                (BlockchainLog.evidence_id == val_uuid) | 
                (BlockchainLog.payload["evidenceId"].astext == str(evidence_id))
            ).order_by(BlockchainLog.created_at.asc()).all()
        except (ValueError, TypeError, AttributeError):
            logs = db.query(BlockchainLog).filter(
                BlockchainLog.payload["evidenceId"].astext == str(evidence_id)
            ).order_by(BlockchainLog.created_at.asc()).all()
    except Exception:
        logs = []

    serialized_logs = [
        {
            "id": str(log.id),
            "eventName": log.event_name,
            "transactionHash": log.transaction_hash,
            "blockNumber": log.block_number,
            "payload": log.payload,
            "createdAt": log.created_at.isoformat() if log.created_at else None
        }
        for log in logs
    ]
    return {
        "data": {
            "evidenceId": evidence_id,
            "custodyHistory": chain_history,
            "blockchainLogs": serialized_logs
        },
        "success": True
    }


@app.get("/blockchain/dashboard")
def blockchain_dashboard(request: Request, db: Session = Depends(get_db)):
    user_info = get_current_user_info(request)
    status = blockchain_service.status()
    total_ev = db.query(Evidence).filter(Evidence.blockchain_tx_hash.isnot(None)).count()
    verified_ev = db.query(Evidence).filter(Evidence.blockchain_tx_hash.isnot(None), Evidence.status == "Verified").count()
    tampered_ev = db.query(Evidence).filter(Evidence.blockchain_tx_hash.isnot(None), Evidence.status == "Tampered").count()

    log_reg_count = db.query(BlockchainLog).filter(BlockchainLog.event_name == "EvidenceRegistered").count()
    total = max(total_ev, log_reg_count)

    log_ver_count = db.query(BlockchainLog).filter(BlockchainLog.event_name == "EvidenceVerified", BlockchainLog.payload["isMatch"].astext == "true").count()
    verified = max(verified_ev, log_ver_count)

    log_tamp_count = db.query(BlockchainLog).filter(BlockchainLog.event_name == "EvidenceVerified", BlockchainLog.payload["isMatch"].astext == "false").count()
    tampered = max(tampered_ev, log_tamp_count)

    transactions = db.query(BlockchainLog).order_by(BlockchainLog.created_at.desc()).limit(10).all()
    recent_txs = [
        {
            "event": log.event_name,
            "transactionHash": log.transaction_hash,
            "transaction_hash": log.transaction_hash,
            "blockNumber": log.block_number,
            "block_number": log.block_number,
            "createdAt": log.created_at.isoformat() if log.created_at else None,
            "created_at": log.created_at.isoformat() if log.created_at else None,
            "payload": log.payload
        }
        for log in transactions
    ]
    blocks = []
    if status.get("connected"):
        try:
            blocks = blockchain_service.recent_blocks()
        except Exception as e:
            logger.warning("Could not fetch recent blocks: %s", e)
            blocks = []
            
    return {
        "network": "Ganache" if status.get("connected") else "Unavailable",
        "chain_id": status.get("chainId", 1337),
        "contract_address": status.get("contractAddress", ""),
        "latest_block": status.get("latestBlock", 0),
        "registered_evidence": total,
        "verified_evidence": verified,
        "tampered_evidence": tampered,
        "pending_transactions": 0,
        "recent_transactions": recent_txs,
        "status": "online" if status.get("connected") else "offline",
        "data": {
            "status": status,
            "totalRegisteredEvidence": total,
            "verifiedEvidence": verified,
            "tamperedEvidence": tampered,
            "latestTransactions": recent_txs,
            "latestBlocks": blocks,
            "pendingTransactions": 0
        },
        "success": True
    }


@app.post("/admin/blockchain/redeploy")
def redeploy_evidence_registry(request: Request):
    user_info = get_current_user_info(request)
    if user_info.get("role", "").lower() != "admin":
        raise HTTPException(status_code=403, detail="Administrator access required")
    root = Path(__file__).resolve().parents[1]
    try:
        completed = subprocess.run(["npx", "hardhat", "compile"], cwd=root / "blockchain", check=True, capture_output=True, text=True, timeout=120)
        completed = subprocess.run(["node", "scripts/deploy.js"], cwd=root / "blockchain", check=True, capture_output=True, text=True, timeout=120)
        blockchain_service.reload()
        write_audit_log(user_info["id"], "EvidenceRegistry Redeployed", metadata={"contract_address": blockchain_service.status().get("contractAddress")})
        return {"data": blockchain_service.status(), "success": True}
    except (subprocess.SubprocessError, BlockchainUnavailable) as e:
        logger.exception("Admin contract redeployment failed")
        raise HTTPException(status_code=503, detail=f"Contract deployment failed: {e}")

# ====== DETECTION ENDPOINTS ======
@app.post("/detect")
async def detect_direct(image: UploadFile = File(...)):
    if not model:
        raise HTTPException(status_code=500, detail="Model not loaded")
    file_path = "temp.jpg"
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(image.file, buffer)
    prediction = model.predict(file_path).json()
    return JSONResponse(content=prediction)

@app.post("/ai/detect")
def run_ai_detect(req: DetectionRequest, request: Request, db: Session = Depends(get_db)):
    print(f"\n[DEBUG] /ai/detect called with evidence_id: {req.evidence_id}, case_id: {req.case_id}")
    
    user_info = get_current_user_info(request)
    check_case_access(req.case_id, user_info, db)

    if not model:
        print("[DEBUG] Roboflow model is None")
        raise HTTPException(status_code=500, detail="Roboflow model not loaded")

    evidence_obj = db.query(Evidence).filter(Evidence.id == req.evidence_id).first()
    if not evidence_obj:
        print(f"[DEBUG] Evidence {req.evidence_id} not found in database")
        raise HTTPException(status_code=404, detail="Evidence not found")

    evidence = serialize_evidence(evidence_obj)
    file_path = evidence.get("file_url")
    stored_hash = evidence.get("file_hash")
    
    print(f"[DEBUG] file_path: {file_path}")
    print(f"[DEBUG] stored_hash: {stored_hash}")

    if not file_path:
        raise HTTPException(status_code=400, detail="No file URL for this evidence record")

    if not stored_hash:
        print("[DEBUG] stored_hash is missing/empty, blocking detection.")
        raise HTTPException(status_code=400, detail="Evidence lacks a stored SHA-256 hash. Integrity cannot be verified.")

    # ── Resolve file path and compute hash ───────────────────────────────────
    is_remote = file_path.startswith("http://") or file_path.startswith("https://")
    local_temp_file = None
    is_remote_download = False

    try:
        if "/uploads/" in file_path:
            # Local file on disk
            relative_path = file_path.split("/uploads/")[-1]
            disk_path = os.path.join(UPLOADS_DIR, relative_path.replace("/", os.sep))
            if not os.path.exists(disk_path):
                raise HTTPException(status_code=404, detail="File missing on local disk")
            local_temp_file = disk_path
            is_remote_download = False
            
            sha256 = hashlib.sha256()
            with open(disk_path, "rb") as f:
                while chunk := f.read(8192):
                    sha256.update(chunk)
            current_hash = sha256.hexdigest()
        elif is_remote:
            is_remote_download = True
            # Download file in memory from Supabase Storage
            response = requests.get(file_path, timeout=30)
            if response.status_code != 200:
                raise HTTPException(status_code=404, detail="Evidence file missing in Supabase Storage")
            file_bytes = response.content
            current_hash = hashlib.sha256(file_bytes).hexdigest()

            # Save to temporary local file for Roboflow prediction
            file_id = str(uuid.uuid4())
            ext = file_path.split(".")[-1].split("?")[0]
            local_temp_file = os.path.join(UPLOADS_DIR, f"temp_{file_id}.{ext}")
            with open(local_temp_file, "wb") as f:
                f.write(file_bytes)
        else:
            is_remote_download = False
            # Legacy local file on disk
            if not os.path.exists(file_path):
                print(f"[DEBUG] File missing on disk at: {file_path}")
                raise HTTPException(status_code=404, detail="File missing on disk")
            local_temp_file = file_path
            
            sha256 = hashlib.sha256()
            with open(file_path, "rb") as f:
                while chunk := f.read(8192):
                    sha256.update(chunk)
            current_hash = sha256.hexdigest()

        print(f"[DEBUG] computed_hash: {current_hash}")

        # ── Integrity check BEFORE running AI ───────────────────────────────────
        if current_hash != stored_hash:
            print("[DEBUG] Hash mismatch detected! Raising 403 Forbidden.")
            # Mark as tampered and block detection
            try:
                evidence_obj.status = "Tampered"
                db.commit()
            except Exception as e:
                db.rollback()
                print(f"[AI DETECT TAMPER UPDATE FAILED] {e}")
            write_audit_log(
                user_id=user_info["id"],
                action="Tamper Detected",
                case_id=req.case_id,
                file_hash=current_hash,
                metadata={
                    "evidence_id": req.evidence_id,
                    "stored_hash": stored_hash,
                    "computed_hash": current_hash,
                    "blocked_action": "AI Detection"
                },
                db=db
            )
            raise HTTPException(
                status_code=403,
                detail=f"Evidence integrity check failed — file may have been tampered. Detection blocked. Stored: {stored_hash[:16]}... Current: {current_hash[:16]}..."
            )

        # Run prediction
        prediction = model.predict(local_temp_file).json()
        print(f"[DEBUG] Prediction response: {str(prediction)[:200]}...")
    except HTTPException:
        raise
    except Exception as e:
        print(f"[DEBUG] Roboflow prediction threw error: {e}")
        raise HTTPException(status_code=500, detail=f"Roboflow prediction failed: {e}")
    finally:
        # Always clean up temporary file if it was downloaded from storage
        if is_remote and is_remote_download and local_temp_file and os.path.exists(local_temp_file):
            try:
                os.remove(local_temp_file)
            except Exception as e:
                print(f"[DEBUG] Failed to delete temporary file {local_temp_file}: {e}")

    image_width = float(prediction.get("image", {}).get("width", 1))
    image_height = float(prediction.get("image", {}).get("height", 1))

    objects = []
    for pred in prediction.get("predictions", []):
        pred_x = float(pred.get("x", 0))
        pred_y = float(pred.get("y", 0))
        pred_w = float(pred.get("width", 0))
        pred_h = float(pred.get("height", 0))

        left_pct = ((pred_x - pred_w/2) / image_width) * 100
        top_pct = ((pred_y - pred_h/2) / image_height) * 100
        w_pct = (pred_w / image_width) * 100
        h_pct = (pred_h / image_height) * 100

        objects.append({
            "label": pred["class"],
            "confidence": pred["confidence"],
            "bbox": [f"{left_pct:.2f}%", f"{top_pct:.2f}%", f"{w_pct:.2f}%", f"{h_pct:.2f}%"]
        })

    image_url_full = file_path if is_remote else f"http://localhost:8000/{file_path}"
    result_data = {"objects": objects, "image_url": image_url_full}

    det_record = {
        "case_id": req.case_id,
        "evidence_id": req.evidence_id,
        "image_url": image_url_full,
        "predictions": {"objects": objects}
    }
    supabase_admin.table("detections").insert(det_record).execute()

    # Audit log for successful detection
    write_audit_log(
        user_id=user_info["id"],
        action="YOLO Scan",
        case_id=req.case_id,
        metadata={"evidence_id": req.evidence_id, "objects_found": len(objects)},
        db=db
    )

    return {"data": result_data}

@app.get("/ai/detect/case/{case_id}")
def get_case_detections(case_id: str, request: Request):
    user_info = get_current_user_info(request)
    check_case_access(case_id, user_info)
    res = supabase_admin.table("detections").select("*").eq("case_id", case_id).execute()
    return {"data": res.data}

@app.get("/ai/bns/case/{case_id}")
def get_bns_case(case_id: str, request: Request):
    user_info = get_current_user_info(request)
    check_case_access(case_id, user_info)
    return {"data": []}

# ── OCR ───────────────────────────────────────────────────────────────────────
# Placeholder text written by earlier OCR versions when extraction failed.
# Cached rows containing it are treated as missing and re-extracted.
LEGACY_OCR_PLACEHOLDERS = ("SECURE AUDIT OCR ENGINE", "SECURE AUDIT SYSTEM - OCR TEXT EXTRACTION",
                           "SECURE AUDIT SYSTEM - TEXT EXTRACTION", "FT DOATION")
_ocr_evidence_locks: Dict[str, threading.Lock] = {}
_ocr_evidence_locks_guard = threading.Lock()


def _ocr_evidence_lock(evidence_id: str) -> threading.Lock:
    """Serialize OCR runs per evidence item so concurrent requests reuse one result."""
    with _ocr_evidence_locks_guard:
        return _ocr_evidence_locks.setdefault(evidence_id, threading.Lock())


def resolve_ocr_evidence_source(evidence: Evidence):
    """Return an OCR-ready local path or downloaded bytes for stored evidence."""
    file_url = evidence.file_url
    if not file_url:
        raise HTTPException(status_code=400, detail="Evidence has no file URL")
    print(f"[OCR] evidence file={evidence.file_name or 'unknown'} url={file_url}")

    # Local-storage uploads are recorded as an application URL. Prefer the
    # original file path instead of making the backend call itself over HTTP.
    is_local_upload_url = USE_LOCAL_STORAGE and "/uploads/" in file_url
    if file_url.startswith(("http://", "https://")) and not is_local_upload_url:
        max_bytes = int(os.getenv("OCR_MAX_FILE_BYTES", str(50 * 1024 * 1024)))
        try:
            with requests.get(file_url, timeout=(10, 60), stream=True) as response:
                response.raise_for_status()
                content = bytearray()
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    content.extend(chunk)
                    if len(content) > max_bytes:
                        raise HTTPException(status_code=413, detail="The evidence file exceeds the OCR size limit")
            return bytes(content)
        except requests.RequestException as exc:
            print(f"[OCR] remote evidence retrieval failed: {exc}")
            raise HTTPException(status_code=502, detail="Unable to retrieve the uploaded evidence file") from exc

    if "/uploads/" in file_url:
        relative_path = file_url.split("/uploads/", 1)[1].replace("/", os.sep)
        local_path = os.path.abspath(os.path.join("uploads", relative_path))
    else:
        local_path = os.path.abspath(file_url)

    uploads_root = os.path.abspath("uploads")
    if file_url.startswith(("/uploads/", "uploads/", "uploads\\")) and os.path.commonpath([uploads_root, local_path]) != uploads_root:
        raise HTTPException(status_code=400, detail="Invalid local evidence path")
    if not os.path.isfile(local_path):
        print(f"[OCR] resolved local path does not exist: {local_path}")
        raise HTTPException(status_code=404, detail="Uploaded evidence file was not found")
    return local_path


def load_cached_ocr_pages(db: Session, evidence_uuid: uuid.UUID) -> List[OCRResult]:
    """Latest stored row per page (older versions could store duplicates)."""
    rows = (db.query(OCRResult).filter(OCRResult.evidence_id == evidence_uuid)
            .order_by(OCRResult.page_number.asc(), OCRResult.created_at.desc()).all())
    latest: Dict[int, OCRResult] = {}
    for row in rows:
        latest.setdefault(row.page_number, row)
    return [latest[number] for number in sorted(latest)]


def cached_ocr_is_usable(rows: List[OCRResult], requested_languages: List[str], requested: str) -> bool:
    """A cache hit needs complete, clean text produced for the same language request.

    ``auto`` accepts any previous extraction; an explicit language selection
    that differs from the stored run re-extracts (replacing, not duplicating).
    """
    if not rows:
        return False
    combined = "\n".join(row.extracted_text or "" for row in rows)
    if any(marker in combined for marker in LEGACY_OCR_PLACEHOLDERS):
        return False
    if any((row.ocr_metadata or {}).get("status") == "failed" for row in rows):
        return False  # retry pages that failed last time
    if (requested or "auto").strip().lower() == "auto":
        return True
    stored = (rows[0].ocr_metadata or {}).get("requested_languages")
    if stored is None:  # rows from before metadata existed: compare the language column
        stored = [code for code in (rows[0].language or "").split("+") if code]
    return set(stored) == set(requested_languages)


def cached_ocr_result(rows: List[OCRResult]) -> Dict[str, Any]:
    pages = []
    for row in rows:
        metadata = row.ocr_metadata or {}
        page_text = row.extracted_text or ""
        pages.append({
            **{key: value for key, value in metadata.items()
               if key not in ("requested_languages", "document_type", "translations")},
            "page_number": row.page_number,
            "text": page_text,
            "confidence": row.confidence if row.confidence is not None else 0.0,
            "language": row.language or UNKNOWN_LANGUAGE,
            "detected_languages": row.detected_languages if row.detected_languages is not None else detect_languages(page_text),
            "status": metadata.get("status", "success" if page_text else "empty"),
            "warnings": metadata.get("warnings", []),
        })
    metadata = rows[0].ocr_metadata or {}
    return build_document_result(pages, metadata.get("requested_languages") or [],
                                 metadata.get("document_type", "unknown"), processing_time_ms=0)


def store_ocr_pages(db: Session, evidence_uuid: uuid.UUID, result: Dict[str, Any]) -> None:
    """Replace the evidence's OCR rows with one row per page, atomically."""
    try:
        # Serializes writers for this evidence across worker processes; the
        # lock is released automatically when the transaction ends.
        db.execute(text("SELECT pg_advisory_xact_lock(hashtext(:key))"), {"key": f"ocr:{evidence_uuid}"})
        db.query(OCRResult).filter(OCRResult.evidence_id == evidence_uuid).delete(synchronize_session=False)
        for page in result["pages"]:
            metadata = {key: page[key] for key in (
                "status", "error", "warnings", "tables", "lines", "line_count", "width", "height", "scale",
                "rotation", "skew_angle", "preprocessing", "processing_time_ms", "raw_text") if key in page}
            metadata.update(requested_languages=result["requested_languages"], document_type=result["document_type"])
            db.add(OCRResult(evidence_id=evidence_uuid, extracted_text=page["text"], language=page["language"],
                             confidence=page["confidence"], page_number=page["page_number"],
                             detected_languages=page["detected_languages"], ocr_metadata=metadata))
        db.commit()
    except Exception as exc:
        db.rollback()
        print(f"[OCR] database save failed: {exc}")
        raise HTTPException(status_code=500, detail="Failed to save OCR results") from exc


def _text_digest(value: str) -> str:
    return hashlib.sha256((value or "").encode("utf-8")).hexdigest()


def translate_ocr_result(db: Session, evidence_uuid: uuid.UUID, result: Dict[str, Any], target_language: Optional[str]) -> Dict[str, Any]:
    """Translate OCR pages, reusing translations stored with the OCR rows.

    Translations live under ``ocr_metadata["translations"][<target>]`` and are
    keyed to a digest of the page text they were made from; the original
    ``extracted_text`` column is never modified. Failures are reported in the
    returned dict and never raised.
    """
    try:
        target = resolve_target_language(target_language)
    except TranslationError as exc:
        return {"status": "failed", "error": str(exc), "target_language": target_language,
                "translated_text": None, "pages": [], "providers": [], "source_languages": []}

    rows = load_cached_ocr_pages(db, evidence_uuid)
    stored = []
    for page, row in zip(result["pages"], rows):
        entry = ((row.ocr_metadata or {}).get("translations") or {}).get(target)
        if entry and entry.get("source_digest") == _text_digest(page.get("text")):
            stored.append(entry)
    if rows and len(stored) == len(result["pages"]):
        pages = [{"page_number": page["page_number"], "translated_text": entry["text"]}
                 for page, entry in zip(result["pages"], stored)]
        return {"status": stored[0].get("status", "success"), "cached": True, "error": None,
                "message": stored[0].get("message"),
                "target_language": target, "target_language_name": TARGET_LANGUAGES[target],
                "providers": stored[0].get("providers", []), "source_languages": stored[0].get("source_languages", []),
                "pages": pages, "processing_time_ms": 0,
                "translated_text": "\n\n".join(p["translated_text"] for p in pages if p["translated_text"]).strip()}

    translation = translation_service.translate_pages(result["pages"], target)
    translation["cached"] = False
    if translation["status"] in ("success", "skipped") and len(rows) == len(result["pages"]):
        try:
            translated_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
            for row, page, translated in zip(rows, result["pages"], translation["pages"]):
                metadata = dict(row.ocr_metadata or {})
                translations = dict(metadata.get("translations") or {})
                translations[target] = {
                    "text": translated["translated_text"], "source_digest": _text_digest(page.get("text")),
                    "providers": translation["providers"], "source_languages": translation["source_languages"],
                    "status": translation["status"], "translated_at": translated_at,
                    "message": translation.get("message"),
                }
                metadata["translations"] = translations
                row.ocr_metadata = metadata  # reassign so SQLAlchemy persists the JSONB change
            db.commit()
        except Exception as exc:  # caching is best effort; the translation is still returned
            db.rollback()
            print(f"[OCR] could not store translation: {exc}")
    return translation


def ocr_response(evidence_id: str, result: Dict[str, Any], cached: bool, processing_time_ms: int,
                 translation: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """API payload. ``text``/``language``/``detected_language`` are kept for existing clients.

    ``text``/``extracted_text`` are always the original OCR output; any
    translation is returned beside it in ``translated_text``.
    """
    pages = result["pages"]
    warnings = list(result["warnings"])
    if translation:
        by_page = {page["page_number"]: page["translated_text"] for page in translation.get("pages", [])}
        pages = [{**page, "translated_text": by_page.get(page["page_number"])} for page in pages]
        if translation.get("error"):
            warnings.append(f"Translation: {translation['error']}")
    return {"success": True, "message": "OCR completed successfully.", "data": {
        "evidence_id": evidence_id,
        "text": result["text"],
        "extracted_text": result["text"],
        "confidence": result["confidence"],
        "language": result["language"],
        "detected_language": result["language"],
        "detected_languages": result["detected_languages"],
        "requested_languages": result["requested_languages"],
        "pages": pages,
        "total_pages": result["total_pages"],
        "processing_time_ms": processing_time_ms,
        "warnings": warnings,
        "cached": cached,
        "translated_text": translation.get("translated_text") if translation else None,
        "translation": {key: value for key, value in translation.items() if key not in ("pages", "translated_text")}
        if translation else None,
    }}


def run_stored_evidence_ocr(evidence_id: str, language: str, request: Request, db: Session, force: bool = False,
                            translate: bool = False, target_language: Optional[str] = "en"):
    started = time.perf_counter()
    user_info = get_current_user_info(request)
    try:
        evidence_uuid = uuid.UUID(str(evidence_id))
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="Invalid evidence ID format")

    evidence = db.query(Evidence).filter(Evidence.id == evidence_uuid).first()
    if not evidence:
        raise HTTPException(status_code=404, detail="Evidence not found")
    case_id = str(evidence.case_id) if evidence.case_id else None
    if case_id:
        check_case_access(case_id, user_info, db)

    requested = language or "auto"
    try:
        requested_languages = ocr_service.resolve_languages(requested)
    except OCRServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

    def elapsed_ms() -> int:
        return int(round((time.perf_counter() - started) * 1000))

    cached = False
    with _ocr_evidence_lock(str(evidence_uuid)):
        # Checked inside the lock so a concurrent request that just finished
        # the same evidence is reused instead of extracted and stored twice.
        rows = [] if force else load_cached_ocr_pages(db, evidence_uuid)
        if rows and cached_ocr_is_usable(rows, requested_languages, requested):
            print(f"[OCR] returning cached result ({len(rows)} page(s)) for evidence_id={evidence_id}")
            result, cached = cached_ocr_result(rows), True
        else:
            source = resolve_ocr_evidence_source(evidence)
            try:
                result = ocr_service.extract_document(source, language=requested)
            except OCRServiceError as exc:
                print(f"[OCR] extraction failed for {evidence_id}: {exc}")
                raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
            except Exception as exc:
                logging.exception("[OCR] unexpected extraction failure for %s", evidence_id)
                raise HTTPException(status_code=500, detail="OCR processing failed unexpectedly") from exc
            store_ocr_pages(db, evidence_uuid, result)

    if not cached:
        print(f"[OCR] {evidence_id}: pages={result['total_pages']} chars={len(result['text'])} "
              f"confidence={result['confidence']} languages={result['language']} time_ms={elapsed_ms()}")
        write_audit_log(user_id=user_info["id"], action="OCR Extraction", case_id=case_id,
                        metadata={"evidence_id": evidence_id, "filename": evidence.file_name,
                                  "confidence": result["confidence"], "pages": result["total_pages"],
                                  "languages": result["language"], "forced": bool(force)}, db=db)

    # Translation runs outside the per-evidence lock (it waits on the network)
    # and can only add information: the OCR result is returned either way.
    translation = None
    if translate:
        translation = translate_ocr_result(db, evidence_uuid, result, target_language)
        print(f"[OCR] translation {evidence_id} -> {translation.get('target_language')}: {translation['status']}")
    return ocr_response(evidence_id, result, cached=cached, processing_time_ms=elapsed_ms(), translation=translation)


@app.post("/ai/ocr/{evidence_id}")
def run_ai_ocr_by_id(evidence_id: str, req: Optional[OCRRequest] = None, request: Request = None, db: Session = Depends(get_db)):
    req = req or OCRRequest()
    return run_stored_evidence_ocr(evidence_id, req.language or "auto", request, db, force=bool(req.force),
                                   translate=bool(req.translate), target_language=req.target_language)


@app.post("/ai/ocr")
def run_ai_ocr_body(req: OCRRequest, request: Request, db: Session = Depends(get_db)):
    if not req.evidence_id:
        raise HTTPException(status_code=400, detail="Missing evidence ID")
    return run_stored_evidence_ocr(req.evidence_id, req.language or "auto", request, db, force=bool(req.force),
                                   translate=bool(req.translate), target_language=req.target_language)

@app.get("/ocr/search")
def search_ocr(q: str, request: Request, db: Session = Depends(get_db)):
    """Search existing OCRResult records for the frontend OCR search panel."""
    user_info = get_current_user_info(request)
    query = (q or "").strip()
    if not query:
        return {"success": True, "data": []}
    if len(query) > 200:
        raise HTTPException(status_code=400, detail="Search query must be 200 characters or fewer")
    escaped = query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    rows = (db.query(OCRResult, Evidence, Case)
            .join(Evidence, OCRResult.evidence_id == Evidence.id)
            .outerjoin(Case, Evidence.case_id == Case.id)
            .filter(OCRResult.extracted_text.ilike(f"%{escaped}%", escape="\\"))
            .order_by(OCRResult.created_at.desc()).all())
    results = {}
    for ocr, evidence, case in rows:
        if evidence.case_id:
            check_case_access(str(evidence.case_id), user_info, db)
        key = str(evidence.id)
        record = results.setdefault(key, {
            "id": key, "file_name": evidence.file_name or "Unnamed evidence",
            "file_type": evidence.evidence_type,
            "case_id": str(evidence.case_id) if evidence.case_id else None,
            "case_title": case.title if case else None,
            "uploaded_by_name": evidence.uploaded_by_name,
            "ocr_matches": [],
        })
        start = max(0, ocr.extracted_text.lower().find(query.lower()) - 100)
        record["ocr_matches"].append({"page_number": ocr.page_number,
            "snippet": ocr.extracted_text[start:start + 300], "confidence": ocr.confidence})
    return {"success": True, "data": list(results.values())}



# ── 6. Real audit log retrieval ───────────────────────────────────────────────
def get_status_for_action(action: str) -> str:
    if action == "Tamper Detected":
        return "Warning"
    elif action in ["Login Successful", "Logout Successful", "Case Created", "Evidence Upload", "Hash Verified", "YOLO Scan", "BNS Classified"]:
        return "Success"
    return "Success"

@app.get("/audit")
def get_audit(
    request: Request,
    page: int = 1,
    limit: int = 20,
    action: str = None,
    user_id: str = None,
    role: str = None,
    start_date: str = None,
    end_date: str = None,
    search: str = None,
    db: Session = Depends(get_db)
):
    user_info = get_current_user_info(request)
    visibility = get_data_visibility(user_info, "view_audit_logs")
    
    # Investigators can only view their own audit logs
    if visibility == "owned":
        target_user_id = user_info["id"]
        # Hide role and user filters for investigators
        user_id = user_info["id"]
        role = None
    else:
        target_user_id = user_id

    try:
        # Build query
        query = db.query(AuditLog)
        
        # Apply filters in database where possible
        if target_user_id and target_user_id != "All Users":
            query = query.filter(AuditLog.user_id == target_user_id)
        if action:
            query = query.filter(AuditLog.action == action)
        if start_date:
            try:
                s_date = start_date
                if "T" not in s_date:
                    s_date = f"{s_date}T00:00:00"
                start_dt = datetime.datetime.fromisoformat(s_date.replace("Z", "+00:00"))
                query = query.filter(AuditLog.created_at >= start_dt)
            except Exception as e:
                print(f"[AUDIT GET] Failed to parse start_date: {e}")
                query = query.filter(AuditLog.created_at >= start_date)
        if end_date:
            try:
                e_date = end_date
                if "T" not in e_date:
                    e_date = f"{e_date}T23:59:59"
                end_dt = datetime.datetime.fromisoformat(e_date.replace("Z", "+00:00"))
                query = query.filter(AuditLog.created_at <= end_dt)
            except Exception as e:
                print(f"[AUDIT GET] Failed to parse end_date: {e}")
                query = query.filter(AuditLog.created_at <= end_date)
            
        db_logs = query.order_by(AuditLog.created_at.desc()).all()
        logs = []
        for log in db_logs:
            logs.append({
                "id": str(log.id),
                "user_id": log.user_id,
                "action": log.action,
                "case_id": str(log.case_id) if log.case_id else None,
                "file_hash": log.file_hash,
                "metadata": log.metadata_,
                "created_at": log.created_at.isoformat() if log.created_at else None
            })
        
        # Fetch users and cases maps
        users_res = supabase_admin.table("users").select("id, full_name, role").execute()
        users_map = {u["id"]: u for u in users_res.data}
        
        cases_res = db.query(Case.id, Case.title, Case.case_number).all()
        cases_map = {str(c[0]): {"id": str(c[0]), "title": c[1], "case_number": c[2]} for c in cases_res}
        
        # Hydrate log entries and apply memory filters (role, search)
        hydrated_logs = []
        for log in logs:
            uid = log.get("user_id")
            user_detail = users_map.get(uid, {})
            log_user_name = user_detail.get("full_name", "System")
            log_user_role = user_detail.get("role", "System")
            
            # Filter by Role (Admin only)
            if role and role != "All Roles" and log_user_role.lower() != role.lower():
                continue
                
            cid = log.get("case_id")
            case_detail = cases_map.get(cid, {})
            case_title = case_detail.get("title", "N/A")
            case_number = case_detail.get("case_number") or (f"SA-{cid[:4].upper()}" if cid else "N/A")
            
            # Status mapping
            log_action = log.get("action", "")
            status = get_status_for_action(log_action)
            
            # Search query matching (matches User Name, Case Title, Case ID, Action, and Role)
            if search:
                search_lower = search.lower()
                matches_search = (
                    search_lower in log_user_name.lower() or
                    search_lower in case_title.lower() or
                    (cid and search_lower in cid.lower()) or
                    (cid and search_lower in case_number.lower()) or
                    search_lower in log_action.lower() or
                    search_lower in log_user_role.lower()
                )
                if not matches_search:
                    continue
            
            # Formatted date/time
            created_at_str = log.get("created_at")
            try:
                # Handle timezone parsing correctly
                dt = datetime.datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))
                date_str = dt.strftime("%Y-%m-%d")
                time_str = dt.strftime("%H:%M:%S")
            except Exception:
                date_str = created_at_str[:10] if created_at_str else "N/A"
                time_str = created_at_str[11:19] if created_at_str else "N/A"
                
            hydrated_logs.append({
                "id": log.get("id"),
                "user_id": uid,
                "user_name": log_user_name,
                "user_role": log_user_role,
                "action": log_action,
                "status": status,
                "case_id": cid,
                "case_title": case_title,
                "case_number": case_number,
                "file_hash": log.get("file_hash"),
                "metadata": log.get("metadata") or {},
                "created_at": created_at_str,
                "date": date_str,
                "time": time_str
            })
            
        # Paginate results in memory after filtering
        total = len(hydrated_logs)
        offset = (page - 1) * limit
        paginated_logs = hydrated_logs[offset:offset + limit]
        
        return {"data": paginated_logs, "total": total}
    except Exception as e:
        print(f"[AUDIT GET ERROR] {e}")
        return {"data": [], "total": 0}

# ====== GRAPH API ======
@app.get("/cases/{case_id}/graph")
def get_case_graph(case_id: str, request: Request, db: Session = Depends(get_db)):
    user_info = get_current_user_info(request)
    check_case_access(case_id, user_info, db)
    
    case_obj = db.query(Case).filter(Case.id == case_id).first()
    if not case_obj:
        raise HTTPException(status_code=404, detail="Case not found")
        
    case = serialize_case(case_obj)
    
    # Just returning the format expected by our new frontend
    nodes = []
    edges = []

    # Central case node
    nodes.append({
        "id": f"case-{case_id}",
        "type": "case",
        "data": { "label": case.get("case_number") or f"SA-{case_id[:4].upper()}", "subtitle": case.get("title", ""), "status": case.get("status", "Open") },
        "position": { "x": 400, "y": 300 }
    })

    # Location node
    if case.get("incident_location"):
        lid = f"location-{case_id}"
        nodes.append({
            "id": lid,
            "type": "location",
            "data": { "label": case["incident_location"], "subtitle": case.get("incident_date", "") },
            "position": { "x": 400, "y": 550 }
        })
        edges.append({
            "id": f"e-case-{lid}",
            "source": f"case-{case_id}",
            "target": lid,
            "label": "occurred at"
        })

    # Event node — FIR
    if case.get("offence_type"):
        eid = f"event-{case_id}"
        nodes.append({
            "id": eid,
            "type": "event",
            "data": { "label": case["offence_type"], "subtitle": "FIR Filed" },
            "position": { "x": 400, "y": 100 }
        })
        edges.append({ "id": f"e-case-{eid}", "source": f"case-{case_id}", "target": eid, "label": "FIR" })

    # Person nodes (Victims & Suspects)
    for i, v in enumerate(case.get("victims", [])):
        vid = f"person-v-{i}-{case_id}"
        nodes.append({"id": vid, "type": "person", "data": {"label": v.get("name"), "subtitle": "Victim", "role": "victim"}, "position": {"x": 100, "y": 200 + (i * 100)}})
        edges.append({"id": f"e-case-{vid}", "source": f"case-{case_id}", "target": vid, "label": "involved"})
        
    for i, s in enumerate(case.get("suspects", [])):
        sid = f"person-s-{i}-{case_id}"
        nodes.append({"id": sid, "type": "person", "data": {"label": s.get("name"), "subtitle": "Suspect", "role": "suspect"}, "position": {"x": 700, "y": 200 + (i * 100)}})
        edges.append({"id": f"e-case-{sid}", "source": f"case-{case_id}", "target": sid, "label": "suspect"})

    # Evidence nodes
    try:
        case_uuid = uuid.UUID(case_id) if case_id else None
        ev_res = db.query(Evidence.id, Evidence.file_name, Evidence.status).filter(Evidence.case_id == case_uuid).all()
        for i, ev in enumerate(ev_res):
            eid = f"ev-{ev[0]}"
            nodes.append({"id": eid, "type": "object", "data": {"label": ev[1][:15] if ev[1] else "Evidence", "subtitle": ev[2] or "Verified"}, "position": {"x": 200 + (i*150), "y": 450}})
            edges.append({"id": f"e-case-{eid}", "source": f"case-{case_id}", "target": eid, "label": "evidence"})
    except Exception:
        pass

    return { "data": { "nodes": nodes, "edges": edges }, "success": True }

# ====== PERSONAL NOTES API ======
@app.get("/notes")
def get_notes():
    # Attempt to fetch notes, if table doesn't exist yet, return mock data
    try:
        res = supabase_admin.table("personal_notes").select("*").order("updated_at", desc=True).execute()
        return {"data": res.data}
    except Exception as e:
        return {"data": []}

@app.post("/notes")
def create_note(note_data: dict):
    # Ensure note_data has required fields
    note_data["updated_at"] = datetime.datetime.now().isoformat()
    # Assuming user_id is injected, omitting for demo
    try:
        res = supabase_admin.table("personal_notes").insert(note_data).execute()
        if len(res.data) > 0:
            return {"data": res.data[0]}
    except Exception as e:
        # Provide a mocked response if table isn't created yet
        note_data["id"] = str(uuid.uuid4())
        return {"data": note_data}
    raise HTTPException(status_code=400, detail="Failed to create note")

@app.patch("/notes/{note_id}")
def update_note(note_id: str, note_data: dict):
    note_data["updated_at"] = datetime.datetime.now().isoformat()
    try:
        res = supabase_admin.table("personal_notes").update(note_data).eq("id", note_id).execute()
        if len(res.data) > 0:
            return {"data": res.data[0]}
    except Exception as e:
        note_data["id"] = note_id
        return {"data": note_data}
    raise HTTPException(status_code=400, detail="Failed to update note")

# ====== BNS PROXY ENDPOINTS ======
class BNSRequest(BaseModel):
    fir_text: str
    threshold: Optional[float] = 0.35
    top_k: Optional[int] = 15

class BNSStore(BaseModel):
    case_id: str
    crime_type: str
    sections: list
    fir_text: str

@app.post("/bns/predict")
def bns_predict(payload: BNSRequest):
    try:
        # Proxy request to BNS server on port 8001
        res = requests.post(
            "http://localhost:8001/predict",
            json={
                "facts": payload.fir_text,
                "threshold": payload.threshold if payload.threshold is not None else 0.35,
                "top_k": payload.top_k if payload.top_k is not None else 15
            },
            timeout=30
        )
        res.raise_for_status()
        raw_data = res.json()
        
        bns_list = []
        for sec in raw_data.get("bns", []):
            sid = str(sec.get("section_id", "Unknown"))
            title = sec.get("title") or sec.get("name") or f"BNS Section {sid}"
            raw_meaning = sec.get("description") or sec.get("meaning", "")
            
            bns_list.append({
                "section_id": sid,
                "title": title,
                "name": title,
                "meaning": raw_meaning,
                "description": raw_meaning,
                "score": float(sec.get("confidence") or sec.get("score", 0.0)),
                "confidence": float(sec.get("confidence") or sec.get("score", 0.0)),
                "confidence_percent": sec.get("confidence_percent", f"{round(float(sec.get('confidence', 0.0)) * 100)}%"),
                "severity": sec.get("severity", "medium"),
                "cognizable": sec.get("cognizable", True),
                "bailable": sec.get("bailable", True),
                "category": sec.get("category", "General Offence"),
                "legal_elements": sec.get("legal_elements", []),
                "punishment": sec.get("punishment", ""),
                "explanation": sec.get("explanation", ""),
                "trigger_sentences": sec.get("trigger_sentences", []),
                "matched_keywords": sec.get("matched_keywords", [])
            })
            
        return {
            "bns": bns_list,
            "sections": bns_list,
            "crime_type": raw_data.get("crime_type", "Multi-Offence Incident"),
            "crime_categories": raw_data.get("crime_categories", []),
            "total_sections": len(bns_list),
            "threshold_applied": raw_data.get("threshold_applied", payload.threshold or 0.35)
        }
    except requests.RequestException as e:
        raise HTTPException(status_code=502, detail=f"Failed to communicate with BNS server: {str(e)}")

@app.post("/bns/store")
def bns_store(payload: BNSStore, request: Request, db: Session = Depends(get_db)):
    user_info = get_current_user_info(request)
    check_case_access(payload.case_id, user_info)
    
    try:
        # Delete existing prediction for this case_id
        db.query(BNSPrediction).filter(BNSPrediction.case_id == uuid.UUID(payload.case_id)).delete()
        
        # Insert the new prediction
        db_pred = BNSPrediction(
            id=uuid.uuid4(),
            case_id=uuid.UUID(payload.case_id),
            crime_type=payload.crime_type,
            sections=payload.sections,
            fir_text=payload.fir_text
        )
        db.add(db_pred)
        db.commit()
        db.refresh(db_pred)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to store BNS prediction: {str(e)}")

    write_audit_log(
        user_id=user_info["id"],
        action="BNS Classified",
        case_id=payload.case_id,
        metadata={"crime_type": payload.crime_type, "sections_count": len(payload.sections)}
    )
    
    data = {
        "id": str(db_pred.id),
        "case_id": str(db_pred.case_id),
        "crime_type": db_pred.crime_type,
        "sections": db_pred.sections,
        "fir_text": db_pred.fir_text,
        "created_at": db_pred.created_at.isoformat().replace("+00:00", "Z") if db_pred.created_at else None
    }
    
    return {"data": data, "success": True}

@app.get("/bns/case/{case_id}")
def bns_get_case(case_id: str, request: Request, db: Session = Depends(get_db)):
    user_info = get_current_user_info(request)
    check_case_access(case_id, user_info)
    
    try:
        preds = db.query(BNSPrediction).filter(BNSPrediction.case_id == uuid.UUID(case_id)).order_by(BNSPrediction.created_at.desc()).all()
        serialized = []
        for p in preds:
            serialized.append({
                "id": str(p.id),
                "case_id": str(p.case_id),
                "crime_type": p.crime_type,
                "sections": p.sections,
                "fir_text": p.fir_text,
                "created_at": p.created_at.isoformat().replace("+00:00", "Z") if p.created_at else None
            })
        return {"data": serialized}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch BNS predictions: {str(e)}")

# ====== USER MANAGEMENT ENDPOINTS (Admin Only) ======
class UserCreateRequest(BaseModel):
    email: str
    password: str
    full_name: str
    role: str
    department: str
    badge_number: str
    clearance_level: Optional[int] = 1

class UserUpdate(BaseModel):
    role: Optional[str] = None
    is_active: Optional[bool] = None
    full_name: Optional[str] = None
    department: Optional[str] = None
    badge_number: Optional[str] = None
    clearance_level: Optional[int] = None
    can_create_case: Optional[bool] = None

@app.get("/users")
def get_users(request: Request):
    user_info = get_current_user_info(request)
    if user_info.get("role") != "Admin":
        raise HTTPException(status_code=403, detail="Forbidden: Admin access required.")
    
    try:
        res = supabase_admin.table("users").select("*").order("created_at", desc=True).execute()
        db_users = res.data or []
        
        # Merge last_login from GoTrue Auth user_metadata (with last_sign_in_at fallback)
        try:
            auth_users_res = supabase_admin.auth.admin.list_users()
            auth_users_map = {u.id: u for u in auth_users_res}
            for u in db_users:
                auth_u = auth_users_map.get(u["id"])
                if auth_u:
                    auth_meta = auth_u.user_metadata or {}
                    u["last_login"] = u.get("last_login") or auth_meta.get("last_login") or auth_u.last_sign_in_at
        except Exception as e:
            print(f"[FALLBACK LOGINS WARNING] {e}")
            
        return {"data": db_users}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@app.patch("/users/{user_id}")
def update_user(user_id: str, payload: UserUpdate, request: Request):
    user_info = get_current_user_info(request)
    if user_info.get("role") != "Admin":
        raise HTTPException(status_code=403, detail="Forbidden: Admin access required.")
    
    # 1. Protect current admin
    if user_id == user_info["id"]:
        raise HTTPException(status_code=400, detail="Cannot modify your own administrative account.")
        
    try:
        # Fetch target user details
        target_res = supabase_admin.table("users").select("*").eq("id", user_id).execute()
        if not target_res.data:
            raise HTTPException(status_code=404, detail="User not found")
        target_user = target_res.data[0]
        
        # 2. Protect last active Admin
        is_target_admin = target_user.get("role") == "Admin"
        is_target_active = target_user.get("is_active", True)
        
        demoting = payload.role is not None and payload.role != "Admin"
        deactivating = payload.is_active is not None and not payload.is_active
        
        if is_target_admin and is_target_active and (demoting or deactivating):
            # Count active admins in database
            admins_res = supabase_admin.table("users").select("id").eq("role", "Admin").eq("is_active", True).execute()
            active_admins = admins_res.data or []
            if len(active_admins) <= 1:
                raise HTTPException(status_code=400, detail="Cannot modify the last active administrator account.")
                
        # 3. Apply updates
        update_data = {}
        if payload.role is not None:
            update_data["role"] = payload.role
        if payload.is_active is not None:
            update_data["is_active"] = payload.is_active
        if payload.full_name is not None:
            update_data["full_name"] = payload.full_name
        if payload.department is not None:
            update_data["department"] = payload.department
        if payload.badge_number is not None:
            update_data["badge_number"] = payload.badge_number
        if payload.clearance_level is not None:
            update_data["clearance_level"] = payload.clearance_level
        if payload.can_create_case is not None:
            update_data["can_create_case"] = payload.can_create_case
            
        if not update_data:
            raise HTTPException(status_code=400, detail="No fields to update.")
            
        res = supabase_admin.table("users").update(update_data).eq("id", user_id).execute()
        
        # 4. Sync metadata to Supabase Auth GoTrue
        try:
            auth_user = supabase_admin.auth.admin.get_user_by_id(user_id)
            existing_meta = auth_user.user.user_metadata or {}
            meta_updates = {}
            if payload.full_name is not None:
                meta_updates["full_name"] = payload.full_name
            if payload.role is not None:
                meta_updates["role"] = payload.role
            if payload.department is not None:
                meta_updates["department"] = payload.department
            if payload.badge_number is not None:
                meta_updates["badge_number"] = payload.badge_number
            
            if meta_updates:
                supabase_admin.auth.admin.update_user_by_id(
                    user_id,
                    attributes={"user_metadata": {**existing_meta, **meta_updates}}
                )
        except Exception as ae:
            print(f"[AUTH UPDATE WARNING] failed to update GoTrue: {ae}")
            
        # 5. Formulate descriptions and write audit log
        old_role = target_user.get("role")
        old_status = "Active" if target_user.get("is_active", True) else "Inactive"
        old_can_create = target_user.get("can_create_case", True)
        
        new_role = payload.role if payload.role is not None else old_role
        new_status = ("Active" if payload.is_active else "Inactive") if payload.is_active is not None else old_status
        new_can_create = payload.can_create_case if payload.can_create_case is not None else old_can_create
        
        changes = []
        if old_role != new_role:
            changes.append(f"Role changed from {old_role} → {new_role}")
        if old_status != new_status:
            changes.append(f"Status changed from {old_status} → {new_status}")
        if old_can_create != new_can_create:
            changes.append(f"Case creation permission changed from {old_can_create} → {new_can_create}")
            
        change_summary = ", ".join(changes) if changes else "Account details updated"
        
        write_audit_log(
            user_id=user_info["id"],
            action="User Updated" if payload.is_active is None else ("User Activated" if payload.is_active else "User Deactivated"),
            metadata={
                "target_user_id": user_id,
                "target_user_name": target_user.get("full_name"),
                "target_user_role": new_role,
                "old_role": old_role,
                "new_role": new_role,
                "description": change_summary
            }
        )
        return {"data": res.data[0]}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@app.post("/users/{user_id}/reset-access")
def reset_user_access(user_id: str, request: Request):
    user_info = get_current_user_info(request)
    if user_info.get("role") != "Admin":
        raise HTTPException(status_code=403, detail="Forbidden: Admin access required.")
        
    if user_id == user_info["id"]:
        raise HTTPException(status_code=400, detail="Cannot reset access for your own administrative account.")
        
    try:
        target_res = supabase_admin.table("users").select("*").eq("id", user_id).execute()
        if not target_res.data:
            raise HTTPException(status_code=404, detail="User not found")
        target_user = target_res.data[0]
        
        # Get existing metadata from Supabase Auth
        auth_user = supabase_admin.auth.admin.get_user_by_id(user_id)
        existing_meta = auth_user.user.user_metadata or {}
        
        # Update password to 'Password123!' and metadata to require password change
        supabase_admin.auth.admin.update_user_by_id(
            user_id,
            attributes={
                "password": "Password123!",
                "user_metadata": {**existing_meta, "must_change_password": True}
            }
        )
        
        write_audit_log(
            user_id=user_info["id"],
            action="Reset Access",
            metadata={
                "target_user_id": user_id,
                "target_user_name": target_user.get("full_name"),
                "target_user_role": target_user.get("role"),
                "description": "Password recovery request generated"
            }
        )
        
        return {
            "success": True,
            "message": "Password recovery initiated. Officer must create a new password during next login."
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to reset access: {str(e)}")


@app.post("/users")
def create_user_admin(payload: UserCreateRequest, request: Request):
    user_info = get_current_user_info(request)
    if user_info.get("role") != "Admin":
        raise HTTPException(status_code=403, detail="Forbidden: Admin access required.")
        
    try:
        # 1. Create user in Supabase Auth with must_change_password=True
        auth_user = supabase_admin.auth.admin.create_user({
            "email": payload.email,
            "password": payload.password,
            "email_confirm": True,
            "user_metadata": {
                "full_name": payload.full_name,
                "role": payload.role,
                "department": payload.department,
                "badge_number": payload.badge_number,
                "must_change_password": True
            }
        })
        
        if not auth_user.user:
            raise HTTPException(status_code=400, detail="Failed to create auth user")
            
        user_id = auth_user.user.id
        
        # 2. Insert into users table
        db_user = {
            "id": user_id,
            "email": payload.email,
            "full_name": payload.full_name,
            "role": payload.role,
            "department": payload.department,
            "badge_number": payload.badge_number,
            "clearance_level": payload.clearance_level,
            "is_active": True
        }
        
        res = supabase_admin.table("users").insert(db_user).execute()
        
        write_audit_log(
            user_id=user_info["id"],
            action="User Created",
            metadata={
                "target_user_id": user_id,
                "target_user_name": payload.full_name,
                "target_user_role": payload.role,
                "description": f"User created with role {payload.role}"
            }
        )
        
        return {"data": res.data[0]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create user: {str(e)}")


# ====== PHOTOGRAMMETRY PROXY ENDPOINTS ======
class PhotogrammetryRequest(BaseModel):
    evidence_id: str


def resolve_local_evidence_path(file_url: str) -> str | None:
    """Map this backend's /uploads URL to the shared local evidence file."""
    path = urlparse(file_url).path.replace("\\", "/")
    marker = "/uploads/"
    if marker not in path:
        return None
    relative = path.split(marker, 1)[1]
    upload_root = UPLOADS_DIR
    candidate = os.path.abspath(os.path.join(upload_root, *relative.split("/")))
    if os.path.commonpath([upload_root, candidate]) != upload_root:
        raise HTTPException(status_code=400, detail="Evidence URL resolves outside the uploads directory.")
    if not os.path.isfile(candidate):
        raise HTTPException(
            status_code=409,
            detail="Evidence record refers to a local upload that no longer exists on disk."
        )
    return candidate

@app.post("/photogrammetry/trigger/{case_id}")
def photogrammetry_trigger(case_id: str, payload: PhotogrammetryRequest, request: Request, db: Session = Depends(get_db)):
    try:
        user_info = get_current_user_info(request)
        if not has_permission(user_info, "run_ai_analysis"):
            raise HTTPException(status_code=403, detail="Forbidden: You do not have permission to run reconstruction.")
        try:
            case_uuid = uuid.UUID(case_id)
            evidence_uuid = uuid.UUID(payload.evidence_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="case_id and evidence_id must be valid UUIDs.") from exc

        check_case_access(case_id, user_info, db)
        evidence = db.query(Evidence).filter(Evidence.id == evidence_uuid, Evidence.case_id == case_uuid).first()
        if not evidence:
            raise HTTPException(status_code=404, detail="Video evidence for this case was not found.")
        media_type = (evidence.mime_type or "").lower()
        if not (media_type.startswith("video/") or (evidence.file_name or "").lower().endswith((".mp4", ".mov", ".avi", ".mkv"))):
            raise HTTPException(status_code=400, detail="Selected evidence is not a supported video file.")
        # Proxy request to photogrammetry-backend server on port 8004
        local_path = resolve_local_evidence_path(evidence.file_url)
        res = requests.post(
            f"http://localhost:8004/trigger/{case_id}",
            json={"evidence_id": payload.evidence_id, "file_url": evidence.file_url, "local_path": local_path},
            timeout=10
        )
        res.raise_for_status()
        return res.json()
    except requests.RequestException as e:
        raise HTTPException(status_code=502, detail=f"Failed to communicate with photogrammetry server: {str(e)}")

@app.get("/photogrammetry/status/{case_id}")
def photogrammetry_status(case_id: str, request: Request):
    try:
        user_info = get_current_user_info(request)
        # Keep the microservice private behind this authenticated, case-scoped proxy.
        with SessionLocal() as db:
            check_case_access(case_id, user_info, db)
        # Proxy request to photogrammetry-backend server on port 8004
        res = requests.get(f"http://localhost:8004/status/{case_id}", timeout=10)
        res.raise_for_status()
        return res.json()
    except requests.RequestException as e:
        raise HTTPException(status_code=502, detail=f"Failed to communicate with photogrammetry server: {str(e)}")


@app.get("/photogrammetry/status/job/{job_id}")
def photogrammetry_job_status(job_id: str, request: Request):
    try:
        user_info = get_current_user_info(request)
        res = requests.get(f"http://localhost:8004/status/job/{job_id}", timeout=10)
        res.raise_for_status()
        payload = res.json()
        with SessionLocal() as db:
            check_case_access(payload["case_id"], user_info, db)
        return payload
    except requests.RequestException as e:
        raise HTTPException(status_code=502, detail=f"Failed to communicate with photogrammetry server: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
