
import os
import base64
import json
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
from fastapi.responses import JSONResponse, FileResponse, Response, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from fastapi.staticfiles import StaticFiles
from supabase import create_client, Client
from gotrue.errors import AuthApiError
import hashlib
import re
import jwt as pyjwt
from dotenv import load_dotenv
from roboflow import Roboflow
import requests
from sqlalchemy import text
from sqlalchemy.orm import Session
from db import get_db, SessionLocal
from models import User, Case, Evidence, AuditLog, OCRResult, BNSPrediction, OTPToken, EvidenceCustodyRecord, BlockchainLog, Detection
from services.ocr_service import OCRServiceError, build_document_result, ocr_service
from services.ocr_text import UNKNOWN_LANGUAGE, detect_languages
from services.translation_service import (TARGET_LANGUAGES, TranslationError,
                                          resolve_target_language, translation_service)
from services.blockchain_service import (blockchain_service, BlockchainUnavailable, BlockchainTransactionError,
                                        hex_variants, is_sha256_hex, normalize_hex, TX_HASH_HEX)
from services import evidence_integrity as integrity
from services.storage_gateway import (
    get_storage_provider,
    LocalStorageProvider,
    build_storage_key,
    validate_storage_key,
    sanitize_filename,
    KeyNotFoundError,
    KeyAlreadyExistsError,
    StorageError,
    StorageConfigurationError,
    StoragePermissionError,
    StorageUnavailableError,
    StorageIntegrityError,
)
from migrate_blockchain import STATEMENTS as BLOCKCHAIN_SCHEMA_STATEMENTS

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
        "blockchain": serialize_blockchain_metadata(evidence),
    }


def serialize_blockchain_metadata(evidence) -> dict:
    """Blockchain receipt metadata persisted for an evidence item (no secrets)."""
    def iso(value):
        return value.isoformat() if value else None

    tx_hash = evidence.blockchain_tx_hash
    return {
        "transactionHash": tx_hash,
        "transactionHashHex": ("0x" + normalize_hex(tx_hash)) if tx_hash else None,
        "blockNumber": evidence.blockchain_block_number,
        "blockHash": evidence.blockchain_block_hash,
        "walletAddress": evidence.blockchain_wallet_address,
        "chainId": evidence.blockchain_chain_id,
        "network": blockchain_network_name(evidence.blockchain_chain_id),
        "contractAddress": evidence.blockchain_contract_address,
        "gasUsed": evidence.blockchain_gas_used,
        "transactionStatus": evidence.blockchain_tx_status or ("SUCCESS" if tx_hash else None),
        "registeredAt": iso(evidence.blockchain_registered_at),
        "latestVerificationAt": iso(evidence.latest_verification_at),
        "lastVerificationResult": evidence.last_verification_result,
        "lastVerificationReason": evidence.last_verification_reason,
        "registered": bool(tx_hash),
    }


def blockchain_network_name(chain_id) -> Optional[str]:
    if chain_id is None:
        return None
    configured = os.getenv("BLOCKCHAIN_NETWORK_NAME")
    if configured:
        return configured
    return "Ganache (local)" if int(chain_id) == 1337 else f"Chain {chain_id}"

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
ROBOFLOW_API_KEY = os.environ.get("ROBOFLOW_API_KEY")
JWT_SECRET = os.environ.get("JWT_SECRET")
EMAIL_USER = os.environ.get("EMAIL_USER")
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD")
SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "465"))
SMTP_TIMEOUT_SECONDS = int(os.environ.get("SMTP_TIMEOUT_SECONDS", "15"))
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
        
        seen_custody_tx = set()
        seen_log_keys = set()

        for event in events:
            raw_ev_id = event["args"].get("evidenceId")
            ev_str = raw_ev_id.hex() if isinstance(raw_ev_id, (bytes, bytearray)) else str(raw_ev_id)
            tx_hash = event.get("transactionHash")
            
            # Find evidence by transaction hash or valid UUID
            evidence = session.query(Evidence).filter(Evidence.blockchain_tx_hash.in_(hex_variants(tx_hash))).first()
            if not evidence and ev_str:
                try:
                    parsed_uuid = uuid.UUID(ev_str)
                    evidence = session.query(Evidence).filter(Evidence.id == parsed_uuid).first()
                except Exception:
                    evidence = None
            
            safe_payload = make_json_safe(event["args"])

            if evidence and event["name"] == "CustodyTransferred":
                action_str = str(event["args"].get("action", "TRANSFERRED"))
                custody_key = (str(evidence.id), tx_hash, action_str)
                if custody_key not in seen_custody_tx:
                    already_in_db = session.query(EvidenceCustodyRecord.id).filter(
                        EvidenceCustodyRecord.evidence_id == evidence.id,
                        EvidenceCustodyRecord.transaction_hash.in_(hex_variants(tx_hash)),
                        EvidenceCustodyRecord.action == action_str
                    ).first()
                    if not already_in_db:
                        seen_custody_tx.add(custody_key)
                        session.add(EvidenceCustodyRecord(
                            evidence_id=evidence.id,
                            officer_id=str(event["args"].get("officerId", "system")),
                            action=action_str,
                            occurred_at=event["timestamp"],
                            transaction_hash=tx_hash,
                            block_number=event["blockNumber"],
                            source="blockchain"
                        ))
            
            log_key = (tx_hash, event["name"])
            if log_key not in seen_log_keys:
                already_logged = session.query(BlockchainLog.id).filter(
                    BlockchainLog.transaction_hash.in_(hex_variants(tx_hash)),
                    BlockchainLog.event_name == event["name"]
                ).first()
                if not already_logged:
                    seen_log_keys.add(log_key)
                    session.add(BlockchainLog(
                        evidence_id=evidence.id if evidence else None,
                        event_name=event["name"],
                        transaction_hash=tx_hash,
                        block_number=event["blockNumber"],
                        payload=safe_payload
                    ))
        session.commit()
        _blockchain_event_cursor = latest + 1
    except Exception as exc:
        session.rollback()
        logger.warning("blockchain.sync_deferred error=%s", exc)
    finally:
        session.close()


def blockchain_event_listener() -> None:
    try:
        interval = max(2, int(os.getenv("BLOCKCHAIN_EVENT_POLL_SECONDS", "10")))
    except ValueError:
        interval = 10
    while True:
        synchronize_blockchain_events()
        time.sleep(interval)


@app.on_event("startup")
def ensure_blockchain_columns() -> None:
    """Apply the additive blockchain schema (same statements as migrate_blockchain.py).

    The ORM model selects the newer metadata columns, so an older database must gain
    them before the first query. Every statement is ADD/CREATE ... IF NOT EXISTS.
    """
    try:
        with SessionLocal() as session:
            for statement in BLOCKCHAIN_SCHEMA_STATEMENTS:
                session.execute(text(statement))
            session.commit()
    except Exception as exc:
        logger.error("blockchain.schema_check_failed error=%s (run migrate_blockchain.py)", exc)


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


ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        "ALLOWED_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173,http://localhost:5176,http://127.0.0.1:5176,http://localhost:3000,http://127.0.0.1:3000"
    ).split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# [SECURITY HARDENING] Direct public access to evidence storage is forbidden.
# All evidence downloads must be authenticated, authorized, and audited via /evidence/{id}/download.
@app.get("/uploads/{path:path}")
def forbidden_uploads_access(path: str):
    raise HTTPException(
        status_code=403,
        detail="Direct public access to raw evidence storage is disabled for forensic security. "
               "Access evidence via the authenticated and audited /evidence/{evidence_id}/download endpoint."
    )

# ---------------------------------------------------------
# Original Code (Alisha) - Roboflow Model Setup:
# try:
#     rf = Roboflow(api_key=ROBOFLOW_API_KEY)
#     project = rf.workspace().project("weapon-detection-using-yolov8")
#     model = project.version(1).model
# except Exception as e:
#     print(f"Warning: Failed to load Roboflow model. Provide a valid key. Error: {e}")
#     model = None
# ---------------------------------------------------------
# Updated: Local YOLOv8 Crime Detection Microservice (Port 8003)
CRIME_DETECTION_SERVICE_URL = os.getenv("CRIME_DETECTION_SERVICE_URL", "http://127.0.0.1:8003/detect/image")
model = None  # Kept for backward compatibility


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
    if not EMAIL_USER or not EMAIL_PASSWORD:
        raise RuntimeError("Email delivery is not configured on the server.")

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

    try:
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=SMTP_TIMEOUT_SECONDS) as server:
            server.login(EMAIL_USER, EMAIL_PASSWORD)
            server.sendmail(EMAIL_USER, [to_email], msg.as_string())
    except (OSError, smtplib.SMTPException) as exc:
        logger.exception("OTP email delivery failed for %s via %s:%s", to_email, SMTP_HOST, SMTP_PORT)
        raise RuntimeError("The email server could not be reached or rejected delivery.") from exc


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
        
        # Check database to see if user is active and retrieve canonical role
        supabase_user = {}
        server_role = None
        user_email = payload.get("email")
        user_name = payload.get("name") or "Investigator"
        can_create = True

        try:
            user_res = supabase_admin.table("users").select("*").eq("id", user_id).execute()
            if user_res.data:
                supabase_user = user_res.data[0]
                if not supabase_user.get("is_active", True):
                    raise HTTPException(status_code=403, detail="Your account has been deactivated by an administrator.")
                server_role = supabase_user.get("role")
                user_email = supabase_user.get("email") or user_email
                user_name = supabase_user.get("full_name") or user_name
                can_create = supabase_user.get("can_create_case", True)
        except HTTPException:
            raise
        except Exception as e:
            logger.warning("get_current_user_info: error querying supabase users: %s", e)

        # Check local PostgreSQL users table as source of truth or fallback
        db = SessionLocal()
        try:
            local_user = db.query(User).filter(User.id == uuid.UUID(user_id)).first() if user_id else None
            if local_user:
                if not local_user.is_active:
                    raise HTTPException(status_code=403, detail="Your account has been deactivated by an administrator.")
                if not server_role:
                    server_role = local_user.role
                user_email = local_user.email or user_email
                user_name = local_user.full_name or user_name
                can_create = local_user.can_create_case if local_user.can_create_case is not None else can_create

            final_role = server_role or "Investigator"

            # Sync the user to local PostgreSQL to ensure foreign keys can be resolved
            sync_user_to_postgres({
                "id": user_id,
                "email": user_email,
                "full_name": user_name,
                "role": final_role,
                "department": supabase_user.get("department") or (local_user.department if local_user else None),
                "badge_number": supabase_user.get("badge_number") or (local_user.badge_number if local_user else None),
                "clearance_level": supabase_user.get("clearance_level", 1) or (local_user.clearance_level if local_user else 1),
                "is_active": True,
                "can_create_case": can_create,
                "last_login": supabase_user.get("last_login") or (local_user.last_login if local_user else None)
            }, db)
        except HTTPException:
            raise
        except Exception as e:
            logger.warning("[USER SYNC ERROR] Failed to sync user to local PostgreSQL: %s", e)
        finally:
            db.close()

        final_role = server_role or "Investigator"

        return {
            "id": user_id,
            "email": user_email,
            "role": final_role,
            "name": user_name,
            "can_create_case": can_create
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
    logger.info("Generated OTP authentication token and queued secure dispatch")
    expires_at = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=5)

    # Deliver before persisting the OTP. A failed delivery must not leave a token
    # in the database that the officer never received.
    try:
        send_otp_email(user["email"], otp, user["full_name"])
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    # Store OTP in PostgreSQL otp_tokens table only after successful delivery.
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
AUDIT_BUFFER_FILE = os.path.join(BACKEND_DIR, "audit_buffer.jsonl")
_audit_buffer_lock = threading.Lock()

def buffer_failed_audit_log(entry: dict) -> None:
    """Safely append a failed audit record to emergency local disk buffer."""
    with _audit_buffer_lock:
        try:
            with open(AUDIT_BUFFER_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, default=str) + "\n")
            logger.warning("[AUDIT BUFFER] Persisted audit record to emergency disk buffer: %s", entry.get("action"))
        except Exception as buffer_err:
            logger.critical("[CRITICAL] Failed to write audit event to emergency buffer: %s", buffer_err)

def flush_audit_buffer(db: Optional[Session] = None) -> int:
    """Flush any buffered audit records to PostgreSQL when database connection is healthy."""
    if not os.path.isfile(AUDIT_BUFFER_FILE):
        return 0
    with _audit_buffer_lock:
        try:
            with open(AUDIT_BUFFER_FILE, "r", encoding="utf-8") as f:
                lines = f.readlines()
            if not lines:
                return 0

            session = db or SessionLocal()
            recovered = 0
            remaining = []
            try:
                for line in lines:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        record = json.loads(line)
                        p_case_id = uuid.UUID(record["case_id"]) if record.get("case_id") else None
                        log_entry = AuditLog(
                            user_id=record.get("user_id") or "system",
                            action=record.get("action") or "Unknown",
                            case_id=p_case_id,
                            file_hash=record.get("file_hash"),
                            metadata_=record.get("metadata")
                        )
                        session.add(log_entry)
                        recovered += 1
                    except Exception:
                        remaining.append(line)
                session.commit()
            except Exception as e:
                session.rollback()
                logger.error("[AUDIT BUFFER RECOVERY ERROR] Could not commit buffered records: %s", e)
                return 0
            finally:
                if not db:
                    session.close()

            # Rewrite remaining lines if any failed
            with open(AUDIT_BUFFER_FILE, "w", encoding="utf-8") as f:
                for line in remaining:
                    f.write(line + "\n")
            if recovered > 0:
                logger.info("[AUDIT BUFFER] Successfully flushed %d buffered audit records to database.", recovered)
            return recovered
        except Exception as e:
            logger.error("[AUDIT BUFFER ERROR] Failed processing buffer file: %s", e)
            return 0

def write_audit_log(user_id: str, action: str, case_id: str = None, file_hash: str = None, metadata: dict = None, db: Session = None):
    """Append-only audit log writer. Persists to PostgreSQL; buffers to disk on failure so no audit event is silently lost."""
    own_session = False
    if db is None:
        db = SessionLocal()
        own_session = True

    parsed_case_id = None
    if case_id:
        if isinstance(case_id, str):
            try:
                parsed_case_id = uuid.UUID(case_id)
            except ValueError:
                parsed_case_id = None
        elif isinstance(case_id, uuid.UUID):
            parsed_case_id = case_id

    entry_dict = {
        "user_id": user_id or "system",
        "action": action,
        "case_id": str(parsed_case_id) if parsed_case_id else None,
        "file_hash": file_hash,
        "metadata": metadata,
        "buffered_at": datetime.datetime.now(datetime.timezone.utc).isoformat()
    }

    try:
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
        # [AUDIT HARDENING] Do NOT silently swallow failure; write to durable disk buffer
        logger.error("[AUDIT LOG DB FAILURE] %s: %s - Writing to emergency append-only buffer", action, e)
        buffer_failed_audit_log(entry_dict)
    finally:
        if own_session:
            db.close()

# ====== EVIDENCE / BLOCKCHAIN HELPERS ======
MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_MB", "200")) * 1024 * 1024
MAX_EVIDENCE_TYPE_LENGTH = 50
MAX_DESCRIPTION_LENGTH = 5000
MAX_FILENAME_LENGTH = 200
_UNSAFE_FILENAME_CHARS = re.compile(r"[^A-Za-z0-9._() -]")


def parse_uuid(value: Optional[str], label: str = "ID") -> uuid.UUID:
    """Parse a path/body identifier, answering 400 instead of a database error."""
    try:
        return uuid.UUID(str(value))
    except (ValueError, TypeError, AttributeError):
        raise HTTPException(status_code=400, detail=f"Invalid {label}: expected a UUID")


def client_ip(request: Optional[Request]) -> Optional[str]:
    """Best-effort client IP. X-Forwarded-For is honoured only when TRUST_PROXY_HEADERS=true."""
    if request is None:
        return None
    if os.getenv("TRUST_PROXY_HEADERS", "false").lower() in ("1", "true", "yes"):
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()[:64]
    return request.client.host if request.client else None


def audit_event(action: str, user_info: Optional[dict], request: Optional[Request], *, result: str,
                evidence=None, case_id=None, file_hash: Optional[str] = None, details: Optional[dict] = None,
                db: Optional[Session] = None) -> None:
    """Blockchain/evidence audit entry with the standard fields (timestamp is set by the DB).

    Always written through its own session so a rolled-back request still leaves a trace.
    """
    metadata = {
        "evidence_id": str(evidence.id) if evidence is not None else (details or {}).get("evidence_id"),
        "result": result,
        "ip_address": client_ip(request),
        "user_name": (user_info or {}).get("name"),
        "user_role": (user_info or {}).get("role"),
        **(details or {}),
    }
    write_audit_log(
        user_id=(user_info or {}).get("id") or "system",
        action=action,
        case_id=str(case_id or (evidence.case_id if evidence is not None and evidence.case_id else "")) or None,
        file_hash=file_hash if file_hash is not None else (evidence.file_hash if evidence is not None else None),
        metadata=make_json_safe(metadata),
    )
    log = logger.warning if action in integrity.ALERT_ACTIONS or action in integrity.FAILURE_ACTIONS else logger.info
    log("audit action=%r result=%s evidence=%s user=%s ip=%s", action, result, metadata["evidence_id"],
        (user_info or {}).get("id"), metadata["ip_address"])


def add_offchain_custody(db: Session, evidence, user_info: dict, action: str, details: Optional[dict] = None) -> None:
    """Custody events the contract does not record (created, viewed, downloaded, modified)."""
    db.add(EvidenceCustodyRecord(
        evidence_id=evidence.id,
        officer_id=user_info.get("id") or "system",
        action=action,
        occurred_at=datetime.datetime.now(datetime.timezone.utc),
        source="database",
        details=make_json_safe(details) if details else None,
    ))


def load_evidence_for_user(evidence_id: str, user_info: dict, db: Session):
    """Evidence row after UUID validation and case-level authorisation."""
    evidence_uuid = parse_uuid(evidence_id, "evidence ID")
    evidence = db.query(Evidence).filter(Evidence.id == evidence_uuid).first()
    if not evidence:
        raise HTTPException(status_code=404, detail="Evidence not found")
    if evidence.case_id:
        check_case_access(str(evidence.case_id), user_info, db)
    elif not is_admin(user_info):
        raise HTTPException(status_code=403, detail="Forbidden: evidence is not linked to a case")
    return evidence


def is_admin(user_info: dict) -> bool:
    return (user_info.get("role") or "").lower() == "admin"


def require_admin(user_info: dict, request: Request, action: str) -> None:
    if not is_admin(user_info):
        audit_event(integrity.AUDIT_UNAUTHORISED, user_info, request, result="Denied", details={"attempted_action": action})
        raise HTTPException(status_code=403, detail="Administrator access required")


def safe_filename(name: Optional[str]) -> str:
    """Strip directories and unsafe characters from a client-supplied file name."""
    base = os.path.basename((name or "").replace("\\", "/")).strip().lstrip(".")
    cleaned = _UNSAFE_FILENAME_CHARS.sub("_", base)[:MAX_FILENAME_LENGTH]
    return cleaned or "uploaded_evidence"


def duplicate_evidence_ids(db: Session, evidence) -> List[str]:
    if not evidence.file_hash:
        return []
    rows = db.query(Evidence.id).filter(Evidence.file_hash == evidence.file_hash, Evidence.id != evidence.id).all()
    return [str(row[0]) for row in rows]


def apply_registration_receipt(evidence, receipt: dict) -> None:
    """Persist every receipt field the blockchain service returns."""
    evidence.blockchain_tx_hash = receipt["transactionHash"]
    evidence.blockchain_block_number = receipt["blockNumber"]
    evidence.blockchain_contract_address = receipt["contractAddress"]
    evidence.blockchain_gas_used = receipt["gasUsed"]
    evidence.blockchain_registered_at = receipt["timestamp"]
    evidence.blockchain_block_hash = receipt.get("blockHash")
    evidence.blockchain_wallet_address = receipt.get("from")
    evidence.blockchain_chain_id = receipt.get("chainId")
    evidence.blockchain_tx_status = receipt.get("status", "SUCCESS")


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
        query = db.query(Case).filter((Case.is_archived.is_(False)) | (Case.is_archived.is_(None)))
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
            row["status"] = "Archived" if case.is_archived else "Open"
            serialized_cases.append(row)

        return {"data": serialized_cases}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("[ERROR] get_cases database failure: %s", e)
        raise HTTPException(status_code=500, detail="Database error retrieving cases. Contact system administrator.")

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

    # ── 0. Input validation (the case ID becomes part of a storage path) ─────
    case_uuid = parse_uuid(case_id, "case ID")
    case_id = str(case_uuid)
    if not db.query(Case.id).filter(Case.id == case_uuid).first():
        raise HTTPException(status_code=404, detail="Case not found")
    check_case_access(case_id, user_info, db)
    evidence_type = (evidence_type or "").strip()
    if not evidence_type or len(evidence_type) > MAX_EVIDENCE_TYPE_LENGTH:
        raise HTTPException(status_code=422, detail=f"evidence_type is required (max {MAX_EVIDENCE_TYPE_LENGTH} characters)")
    if description and len(description) > MAX_DESCRIPTION_LENGTH:
        raise HTTPException(status_code=422, detail=f"description is limited to {MAX_DESCRIPTION_LENGTH} characters")

    try:
        file_bytes = file.file.read(MAX_UPLOAD_BYTES + 1)
    except Exception as e:
        logger.warning("evidence.upload_read_failed error=%s", e)
        raise HTTPException(status_code=400, detail="Failed to read the uploaded file")
    file_size = len(file_bytes)
    if file_size == 0:
        raise HTTPException(status_code=422, detail="The uploaded file is empty")
    if file_size > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail=f"File exceeds the {MAX_UPLOAD_BYTES // (1024 * 1024)} MB upload limit")

    # ── 1. Hash the file ─────────────────────────────────────────────────────
    hash_hex = hashlib.sha256(file_bytes).hexdigest()

    # ── 2. Duplicate detection ───────────────────────────────────────────────
    # Same file in the same case: rejected. Same file in another case: allowed
    # (one exhibit can belong to several cases) but flagged in the audit log.
    same_hash = db.query(Evidence.id, Evidence.case_id).filter(Evidence.file_hash == hash_hex).all()
    in_case = [row for row in same_hash if row[1] == case_uuid]
    if in_case:
        dup_id_str = str(in_case[0][0])
        return JSONResponse(
            status_code=409,
            content={
                "detail": f"Duplicate file detected. This file was already uploaded (evidence ID: {dup_id_str}). SHA-256: {hash_hex[:16]}...",
                "evidence_id": dup_id_str,
                "duplicate": True
            }
        )

    # ── 3. Upload to cloud storage (S3/R2), local storage, or Supabase ───────
    file_uuid = str(uuid.uuid4())
    original_filename = safe_filename(file.filename)
    stored_name = f"{file_uuid}_{original_filename}"
    local_file_path = None
    storage_path = None
    storage_backend = (os.getenv("STORAGE_BACKEND") or "local").strip().lower()

    if storage_backend in ("s3", "cloud"):
        canonical_key = build_storage_key(case_id, original_filename, file_uuid)
        storage_path = canonical_key
        try:
            provider = get_storage_provider()
            stored_obj = provider.put(
                key=canonical_key,
                data_or_stream=file_bytes,
                content_type=file.content_type or "application/octet-stream"
            )
        except KeyAlreadyExistsError as e:
            logger.warning("evidence.s3_collision key=%s error=%s", canonical_key, e)
            raise HTTPException(status_code=409, detail=f"Evidence storage key already exists: {canonical_key}")
        except StoragePermissionError as e:
            logger.error("evidence.s3_permission_denied key=%s error=%s", canonical_key, e)
            raise HTTPException(status_code=502, detail=f"Evidence cloud storage permission denied: {e}")
        except StorageUnavailableError as e:
            logger.error("evidence.s3_unavailable key=%s error=%s", canonical_key, e)
            raise HTTPException(status_code=502, detail=f"Evidence cloud storage provider unreachable: {e}")
        except StorageConfigurationError as e:
            logger.error("evidence.s3_config_error key=%s error=%s", canonical_key, e)
            raise HTTPException(status_code=500, detail=f"Evidence cloud storage misconfigured: {e}")
        except StorageError as e:
            logger.error("evidence.s3_upload_failed key=%s error=%s", canonical_key, e)
            raise HTTPException(status_code=502, detail=f"Failed to upload evidence to cloud storage: {e}")

        if stored_obj.sha256.lower() != hash_hex.lower():
            logger.error(
                "evidence.s3_integrity_mismatch key=%s expected=%s got=%s",
                canonical_key, hash_hex, stored_obj.sha256
            )
            raise HTTPException(
                status_code=500,
                detail="Evidence storage integrity error: stored SHA-256 does not match uploaded file."
            )

        file_url = canonical_key
    elif USE_LOCAL_STORAGE:
        local_dir = os.path.join(UPLOADS_DIR, "cases", case_id)
        os.makedirs(local_dir, exist_ok=True)
        local_file_path = os.path.join(local_dir, stored_name)
        try:
            with open(local_file_path, "wb") as f:
                f.write(file_bytes)
        except OSError as e:
            logger.error("evidence.local_write_failed error=%s", e)
            raise HTTPException(status_code=500, detail="Failed to store the evidence file")
        file_url = f"{str(request.base_url)}uploads/cases/{case_id}/{stored_name}"
    else:
        storage_path = f"cases/{case_id}/{stored_name}"
        try:
            supabase_admin.storage.from_("evidence").upload(
                path=storage_path,
                file=file_bytes,
                file_options={"content-type": file.content_type or "application/octet-stream"}
            )
        except Exception as e:
            logger.error("evidence.storage_upload_failed error=%s", e)
            raise HTTPException(status_code=502, detail="Failed to upload the file to evidence storage")
        try:
            file_url = supabase_admin.storage.from_("evidence").get_public_url(storage_path)
            if file_url.endswith("?"):
                file_url = file_url[:-1]
        except Exception:
            file_url = f"{SUPABASE_URL}/storage/v1/object/public/evidence/{storage_path}"

    def discard_stored_file() -> None:
        """A rolled-back upload must not leave an unregistered file behind on local/Supabase storage."""
        try:
            if storage_backend in ("s3", "cloud"):
                # Append-only immutability: StorageProvider defines no delete method.
                # Evidence is preserved without silent deletion; emit warning for audit tracking.
                logger.warning(
                    "evidence.cloud_object_unregistered key=%s hash=%s case=%s",
                    canonical_key, hash_hex, case_id
                )
            elif local_file_path and os.path.isfile(local_file_path):
                os.remove(local_file_path)
            elif storage_path:
                supabase_admin.storage.from_("evidence").remove([storage_path])
        except Exception as cleanup_error:
            logger.error("evidence.orphan_cleanup_failed path=%s error=%s", local_file_path or storage_path, cleanup_error)

    # Flush relational metadata, wait for a mined chain receipt, then commit both.
    db_evidence = Evidence(
        case_id=case_uuid,
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
        status=integrity.VERIFIED
    )

    try:
        db.add(db_evidence)
        db.flush()
        add_offchain_custody(db, db_evidence, user_info, integrity.CUSTODY_CREATED,
                             {"file_name": original_filename, "file_size": file_size, "sha256": hash_hex})
        registration = blockchain_service.register_evidence(str(db_evidence.id), case_id, original_filename, hash_hex, user_info["id"])
        apply_registration_receipt(db_evidence, registration)
        db_evidence.last_verification_result = integrity.VERIFIED
        db_evidence.last_verification_reason = "HASH_MATCH"
        db.add(EvidenceCustodyRecord(evidence_id=db_evidence.id, officer_id=user_info["id"], action="REGISTERED",
                                     occurred_at=registration["timestamp"], transaction_hash=registration["transactionHash"],
                                     block_number=registration["blockNumber"], source="blockchain"))
        db.add(BlockchainLog(evidence_id=db_evidence.id, event_name="EvidenceRegistered",
                             transaction_hash=registration["transactionHash"], block_number=registration["blockNumber"],
                             payload=make_json_safe({"contractAddress": registration["contractAddress"],
                                                     "gasUsed": registration["gasUsed"],
                                                     "blockHash": registration.get("blockHash"),
                                                     "from": registration.get("from"),
                                                     "chainId": registration.get("chainId"),
                                                     "sha256Hash": hash_hex})))
        db.commit()
        db.refresh(db_evidence)
    except (BlockchainUnavailable, BlockchainTransactionError) as e:
        db.rollback()
        discard_stored_file()
        logger.error("evidence.registration_failed case=%s error=%s", case_id, e)
        audit_event(integrity.AUDIT_REGISTRATION_FAILED, user_info, request, result="Failed", case_id=case_id,
                    file_hash=hash_hex, details={"file_name": original_filename, "reason": str(e)[:300]})
        raise HTTPException(status_code=503, detail=f"Evidence was not saved because blockchain registration failed: {e}")
    except Exception:
        db.rollback()
        discard_stored_file()
        logger.exception("evidence.upload_failed case=%s", case_id)
        raise HTTPException(status_code=400, detail="Failed to upload evidence")

    evidence_row = serialize_evidence(db_evidence)
    # Keys the frontend expects
    evidence_row["file_name"] = original_filename
    evidence_row["file_type"] = evidence_type
    evidence_row["file_size"] = file_size
    evidence_row["sha256_hash"] = hash_hex

    write_audit_log(
        user_id=user_info["id"],
        action=integrity.AUDIT_EVIDENCE_UPLOADED,
        case_id=case_id,
        file_hash=hash_hex,
        metadata={
            "file_name": original_filename,
            "file_size": file_size,
            "evidence_id": evidence_row["id"],
            "evidence_type": evidence_type,
            "ip_address": client_ip(request),
            "result": "Success"
        },
        db=db
    )
    audit_event(integrity.AUDIT_EVIDENCE_REGISTERED, user_info, request, result="Success", evidence=db_evidence,
                details={"transaction_hash": registration["transactionHash"], "block_number": registration["blockNumber"],
                         "wallet_address": registration.get("from"), "gas_used": registration["gasUsed"]})
    other_cases = [str(row[0]) for row in same_hash]
    if other_cases:
        audit_event(integrity.AUDIT_DUPLICATE_HASH, user_info, request, result="Flagged", evidence=db_evidence,
                    details={"duplicate_evidence_ids": other_cases})
        evidence_row["duplicateOf"] = other_cases
    logger.info("evidence.registered id=%s tx=%s", db_evidence.id, registration["transactionHash"])
    return {"data": evidence_row, "success": True}

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


class EvidenceStorageUnavailable(HTTPException):
    """Storage could not be read. Not evidence of tampering: callers must not change the status."""

    def __init__(self, detail: str, status_code: int = 503):
        super().__init__(status_code=status_code, detail=detail)


class UnsafeEvidenceLocation(HTTPException):
    """The recorded file location points outside the evidence stores (possible record tampering)."""

    def __init__(self, detail: str):
        super().__init__(status_code=400, detail=detail)


MAX_HASH_DOWNLOAD_BYTES = int(os.getenv("MAX_HASH_DOWNLOAD_MB", "1024")) * 1024 * 1024


def resolve_upload_path(file_url: str) -> str:
    """Absolute path of a local upload, refusing anything outside UPLOADS_DIR (path traversal)."""
    relative = urlparse(file_url).path.replace("\\", "/").split("/uploads/", 1)[-1]
    root = os.path.abspath(UPLOADS_DIR)
    candidate = os.path.abspath(os.path.join(root, *[part for part in relative.split("/") if part]))
    if os.path.commonpath([root, candidate]) != root:
        raise UnsafeEvidenceLocation("Evidence location resolves outside the uploads directory")
    return candidate


def storage_url_allowed(file_url: str) -> bool:
    """Remote evidence may only be fetched from the configured Supabase project (prevents SSRF)."""
    if not SUPABASE_URL:
        return False
    allowed, target = urlparse(SUPABASE_URL), urlparse(file_url)
    return target.scheme in ("http", "https") and target.netloc.lower() == allowed.netloc.lower()


def compute_evidence_deep_hash(file_url: str) -> tuple[str, int, Optional[str]]:
    """Deep byte-level calculation of evidence SHA-256 independent of stored metadata.

    Reads real object bytes chunk-by-chunk through hashlib.sha256.
    Returns (calculated_byte_hash, total_bytes, storage_metadata_hash).

    Raises ``EvidenceFileMissing`` when the file is gone, ``EvidenceStorageUnavailable``
    when storage cannot be read (an outage is not evidence of tampering), and
    ``UnsafeEvidenceLocation`` when the recorded location is not an evidence store.
    """
    if not file_url or not str(file_url).strip():
        raise EvidenceFileMissing("Evidence file URL is empty")

    url_str = str(file_url).strip()

    # 1. Canonical Storage Gateway key (e.g. "cases/{case_id}/{filename}")
    if url_str.startswith("cases/") or (not urlparse(url_str).scheme and "/uploads/" not in url_str):
        try:
            provider = get_storage_provider()
            # Deep byte read: reads real bytes chunk-by-chunk through hasher
            byte_hash, total_size = provider.read_bytes_sha256(url_str)
            # Retrieve metadata hash where available (for comparison against byte hash)
            metadata_hash = None
            try:
                obj_meta = provider.stat(url_str)
                metadata_hash = getattr(obj_meta, "metadata_sha256", None) or obj_meta.sha256
            except Exception:
                pass
            return byte_hash, total_size, metadata_hash
        except KeyNotFoundError:
            raise EvidenceFileMissing(f"Evidence object '{url_str}' not found in storage gateway")
        except StorageUnavailableError as e:
            raise EvidenceStorageUnavailable(f"Storage gateway unreachable: {e}", 502)
        except Exception as e:
            logger.error("evidence.storage_gateway_read_failed key=%s error=%s", url_str, e)
            raise EvidenceStorageUnavailable(f"Failed to read bytes from storage gateway: {e}", 500)

    # 2. Local uploads URL
    if "/uploads/" in url_str:
        path = resolve_upload_path(url_str)
        if not os.path.isfile(path):
            raise EvidenceFileMissing("Evidence file not found in local storage")
        sha256 = hashlib.sha256()
        total_size = 0
        try:
            with open(path, "rb") as f:
                while chunk := f.read(1 << 20):
                    sha256.update(chunk)
                    total_size += len(chunk)
        except OSError as e:
            logger.error("evidence.local_read_failed error=%s", e)
            raise EvidenceStorageUnavailable("Failed to read the local evidence file", 500)
        return sha256.hexdigest(), total_size, None

    # 3. Remote Supabase URL
    if not storage_url_allowed(url_str):
        raise UnsafeEvidenceLocation("Evidence location is not a recognised evidence store")
    try:
        response = requests.get(url_str, timeout=(5, 60), stream=True)
    except requests.RequestException as e:
        logger.warning("evidence.storage_unreachable error=%s", e)
        raise EvidenceStorageUnavailable("Could not reach evidence storage", 502)
    with response:
        # Supabase Storage answers 400 {"error": "not_found"} for missing public objects.
        if response.status_code == 404 or (response.status_code == 400 and "not_found" in response.text.lower()):
            raise EvidenceFileMissing("Evidence file not found in Supabase Storage")
        if response.status_code != 200:
            raise EvidenceStorageUnavailable(f"Evidence storage returned HTTP {response.status_code}", 502)
        sha256, total = hashlib.sha256(), 0
        for chunk in response.iter_content(1 << 20):
            total += len(chunk)
            if total > MAX_HASH_DOWNLOAD_BYTES:
                raise EvidenceStorageUnavailable("Evidence file exceeds the verification size limit", 413)
            sha256.update(chunk)
    return sha256.hexdigest(), total, None


def compute_evidence_file_hash(file_url: str) -> str:
    """SHA-256 of the stored evidence file (deep byte calculation)."""
    byte_hash, _, _ = compute_evidence_deep_hash(file_url)
    return byte_hash


def verification_failure(http_status: int, result: str, reason: str, message: str, evidence, extra: Optional[dict] = None) -> JSONResponse:
    """Error response that keeps the plain-string ``detail`` the frontend already shows."""
    return JSONResponse(status_code=http_status, content=make_json_safe({
        "detail": message,
        "status": result,
        "result": result,
        "reason": reason,
        "reasonText": integrity.REASONS.get(reason, reason),
        "evidenceId": str(evidence.id),
        "evidenceStatus": evidence.status,
        "success": False,
        **(extra or {}),
    }))


def sync_receipt_metadata(db: Session, evidence, receipt: Optional[dict], user_info: Optional[dict], request: Optional[Request]) -> bool:
    """Fill blockchain metadata columns that are empty (older rows) from the on-chain receipt."""
    if not receipt:
        return False
    fields = {
        "blockchain_tx_hash": receipt["transactionHash"],
        "blockchain_block_number": receipt["blockNumber"],
        "blockchain_contract_address": receipt["contractAddress"],
        "blockchain_gas_used": receipt["gasUsed"],
        "blockchain_registered_at": receipt["timestamp"],
        "blockchain_block_hash": receipt.get("blockHash"),
        "blockchain_wallet_address": receipt.get("from"),
        "blockchain_chain_id": receipt.get("chainId"),
        "blockchain_tx_status": receipt.get("status"),
    }
    filled = [name for name, value in fields.items() if value is not None and getattr(evidence, name) in (None, "")]
    if not filled:
        return False
    for name in filled:
        setattr(evidence, name, fields[name])
    db.commit()
    audit_event(integrity.AUDIT_METADATA_BACKFILLED, user_info, request, result="Success", evidence=evidence,
                details={"fields": filled, "transaction_hash": receipt["transactionHash"]})
    return True


def registration_receipt_state(evidence) -> tuple[Optional[dict], str]:
    """(receipt, state) for the stored registration tx: state is found, missing, unknown or none."""
    if not evidence.blockchain_tx_hash:
        return None, "none"
    try:
        receipt = blockchain_service.receipt_metadata(evidence.blockchain_tx_hash)
    except BlockchainUnavailable:
        return None, "unknown"
    return receipt, ("found" if receipt else "missing")


CUSTODY_LABELS = {
    integrity.CUSTODY_CREATED: "Evidence Created",
    "REGISTERED": "Evidence Registered",
    "VERIFIED": "Evidence Verified",
    integrity.CUSTODY_VIEWED: "Evidence Viewed",
    integrity.CUSTODY_DOWNLOADED: "Evidence Downloaded",
    integrity.CUSTODY_MODIFIED: "Evidence Modified (metadata only)",
    "TRANSFERRED": "Evidence Ownership Changed",
    integrity.CUSTODY_DELETED: "Evidence Deleted",
}


# Tie-break for events in the same second (block timestamps have 1 s resolution).
CUSTODY_ORDER = {integrity.CUSTODY_CREATED: 0, "REGISTERED": 1}


def utc_iso(value: Optional[datetime.datetime]) -> Optional[str]:
    return value.astimezone(datetime.timezone.utc).isoformat() if value else None


def build_custody_timeline(db: Session, evidence, chain_history: Optional[List[dict]]) -> List[dict]:
    """Chronological custody history: database records plus any on-chain entries not mirrored locally."""
    rows = db.query(EvidenceCustodyRecord).filter(EvidenceCustodyRecord.evidence_id == evidence.id).all()
    entries = [{
        "action": row.action,
        "label": CUSTODY_LABELS.get(row.action, row.action.title()),
        "officerId": row.officer_id,
        "timestamp": utc_iso(row.occurred_at),
        "source": row.source or ("blockchain" if row.transaction_hash else "database"),
        "transactionHash": row.transaction_hash,
        "blockNumber": row.block_number,
        "details": row.details,
    } for row in rows]
    mirrored = {(e["action"], e["officerId"], (e["timestamp"] or "")[:19]) for e in entries if e["source"] == "blockchain"}
    for item in chain_history or []:
        key = (item["action"], item["officerId"], item["timestamp"][:19])
        if key not in mirrored:
            entries.append({"action": item["action"], "label": CUSTODY_LABELS.get(item["action"], item["action"].title()),
                            "officerId": item["officerId"], "timestamp": item["timestamp"], "source": "blockchain",
                            "transactionHash": None, "blockNumber": None, "details": None})
    officer_ids = []
    for entry in entries:
        try:
            officer_ids.append(uuid.UUID(entry["officerId"]))
        except (ValueError, TypeError):
            pass
    names = {str(uid): name for uid, name in db.query(User.id, User.full_name).filter(User.id.in_(officer_ids)).all()} if officer_ids else {}
    for entry in entries:
        entry["officerName"] = names.get(entry["officerId"], entry["officerId"])
    return sorted(entries, key=lambda e: ((e["timestamp"] or "")[:19], CUSTODY_ORDER.get(e["action"], 2), e["timestamp"] or ""))


VIEW_LOG_INTERVAL = datetime.timedelta(minutes=10)


def record_view(db: Session, evidence, user_info: dict, request: Request) -> None:
    """Custody + audit entry for viewing, at most once per user per evidence every 10 minutes."""
    since = datetime.datetime.now(datetime.timezone.utc) - VIEW_LOG_INTERVAL
    recent = db.query(EvidenceCustodyRecord.id).filter(
        EvidenceCustodyRecord.evidence_id == evidence.id,
        EvidenceCustodyRecord.action == integrity.CUSTODY_VIEWED,
        EvidenceCustodyRecord.officer_id == user_info["id"],
        EvidenceCustodyRecord.occurred_at >= since).first()
    if recent:
        return
    add_offchain_custody(db, evidence, user_info, integrity.CUSTODY_VIEWED, {"ip_address": client_ip(request)})
    db.commit()
    audit_event(integrity.AUDIT_EVIDENCE_VIEWED, user_info, request, result="Success", evidence=evidence)


def public_blockchain_status(user_info: Optional[dict] = None) -> dict:
    """Chain status without internal details (RPC URL, stack text) for non-administrators."""
    status = blockchain_service.status()
    if not status.get("connected") and not (user_info and is_admin(user_info)):
        if status.get("error"):
            logger.warning("blockchain.unavailable error=%s", status["error"])
        status = {"connected": False, "error": "Blockchain network is currently unavailable"}
    return status


@app.post("/evidence/{evidence_id}/verify")
def verify_evidence_hash(evidence_id: str, request: Request, deep: bool = True, db: Session = Depends(get_db)):
    """Recomputes SHA-256 from storage and verifies it on the blockchain.

    When deep=True (default), reads actual object bytes and computes SHA-256
    independently of stored metadata. Compares calculated hash with:
    1. Database hash (evidence.file_hash)
    2. Storage metadata hash (where available)
    3. Blockchain registered hash (where applicable)

    When deep=False, performs a fast metadata-only check without certifying byte integrity.
    """
    user_info = get_current_user_info(request)
    evidence_obj = load_evidence_for_user(evidence_id, user_info, db)
    evidence_id = str(evidence_obj.id)
    case_id = str(evidence_obj.case_id) if evidence_obj.case_id else None
    stored_hash = evidence_obj.file_hash
    if not evidence_obj.file_url:
        raise HTTPException(status_code=400, detail="No file URL for this evidence record")

    if not deep:
        # Fast metadata-only check: compare database hash against storage gateway metadata
        url_str = str(evidence_obj.file_url).strip()
        meta_hash = None
        meta_match = False
        meta_status = "MetadataMismatch"
        note = "Fast metadata check only; does not certify byte-level integrity."

        # 1. Canonical Storage Gateway key (e.g. "cases/{case_id}/{filename}")
        if url_str.startswith("cases/") or (not urlparse(url_str).scheme and "/uploads/" not in url_str):
            try:
                provider = get_storage_provider()
                stat_obj = provider.stat(url_str)
                meta_hash = getattr(stat_obj, "metadata_sha256", None) or stat_obj.sha256
                meta_match = bool(stored_hash and meta_hash and stored_hash.lower() == meta_hash.lower())
                meta_status = "MetadataMatch" if meta_match else "MetadataMismatch"
            except KeyNotFoundError:
                raise HTTPException(status_code=404, detail=f"Evidence object '{url_str}' not found in storage gateway")
            except StorageUnavailableError as e:
                raise HTTPException(status_code=502, detail=f"Storage gateway unreachable: {e}")
            except StoragePermissionError as e:
                raise HTTPException(status_code=502, detail=f"Storage access denied: {e}")
            except StorageConfigurationError as e:
                raise HTTPException(status_code=500, detail=f"Storage gateway misconfigured: {e}")
            except Exception as e:
                raise HTTPException(status_code=502, detail=f"Storage provider error: {e}")

        # 2. Legacy local uploads URL (e.g. "http://localhost:8000/uploads/cases/...")
        elif "/uploads/" in url_str:
            try:
                path = resolve_upload_path(url_str)
            except UnsafeEvidenceLocation as e:
                raise HTTPException(status_code=400, detail=str(e.detail))

            if not os.path.isfile(path):
                raise HTTPException(status_code=404, detail="Evidence file not found in local storage")

            # Local filesystem does not store out-of-band SHA-256 headers; verify file existence and accessibility
            try:
                stat_info = os.stat(path)
                file_size = stat_info.st_size
            except OSError as e:
                raise HTTPException(status_code=500, detail=f"Failed to read local file metadata: {e}")

            meta_hash = None
            meta_match = False
            meta_status = "MetadataUnavailable"
            note = (
                "Fast metadata check: local evidence file exists and is accessible, but out-of-band SHA-256 "
                "metadata is not available on local storage. Use deep=true for byte-level cryptographic verification."
            )

        # 3. Remote URL (Supabase Storage)
        else:
            if not storage_url_allowed(url_str):
                raise HTTPException(status_code=400, detail="Evidence location is not a recognised evidence store")
            try:
                head_resp = requests.head(url_str, timeout=(5, 15))
            except requests.RequestException as e:
                raise HTTPException(status_code=502, detail=f"Could not reach remote storage: {e}")

            if head_resp.status_code == 404 or (head_resp.status_code == 400 and "not_found" in head_resp.text.lower()):
                raise HTTPException(status_code=404, detail="Evidence file not found in Supabase Storage")
            if head_resp.status_code != 200:
                raise HTTPException(status_code=502, detail=f"Remote evidence storage returned HTTP {head_resp.status_code}")

            # Look for explicit SHA-256 metadata headers (do NOT treat ETag as SHA-256)
            remote_sha256 = (
                head_resp.headers.get("x-amz-meta-sha256")
                or head_resp.headers.get("x-sha256")
                or head_resp.headers.get("content-sha256")
            )
            if remote_sha256 and is_sha256_hex(remote_sha256):
                meta_hash = normalize_hex(remote_sha256)
                meta_match = bool(stored_hash and meta_hash.lower() == stored_hash.lower())
                meta_status = "MetadataMatch" if meta_match else "MetadataMismatch"
            else:
                meta_hash = None
                meta_match = False
                meta_status = "MetadataUnavailable"
                note = (
                    "Fast metadata check: remote evidence file exists in storage, but out-of-band SHA-256 "
                    "metadata header is not available. Use deep=true for byte-level cryptographic verification."
                )

        return {
            "data": {
                "deepVerification": False,
                "metadataOnly": True,
                "databaseHash": stored_hash,
                "storageMetadataHash": meta_hash,
                "matchesDatabase": meta_match,
                "status": meta_status,
                "note": note
            },
            "success": True
        }

    def record_outcome(result: str, reason: str, audit_action: str, details: dict, new_status: Optional[str] = None) -> None:
        try:
            now = datetime.datetime.now(datetime.timezone.utc)
            evidence_obj.last_verification_result = result
            evidence_obj.last_verification_reason = reason
            if new_status:
                evidence_obj.status = new_status
                evidence_obj.verified_at = now
                evidence_obj.verified_by = uuid.UUID(user_info["id"]) if user_info["id"] else None
            db.commit()
        except Exception as e:
            db.rollback()
            logger.error("evidence.verification_status_update_failed id=%s error=%s", evidence_id, e)
        audit_event(audit_action, user_info, request, result=result, evidence=evidence_obj,
                    details={"reason": reason, "reason_text": integrity.REASONS.get(reason), **details})

    # 1. Re-hash the stored file using deep byte calculation.
    try:
        current_hash, total_bytes, metadata_hash = compute_evidence_deep_hash(evidence_obj.file_url)
    except EvidenceFileMissing as e:
        record_outcome(integrity.MISSING, "EVIDENCE_MISSING", integrity.AUDIT_EVIDENCE_MISSING, {"detail": str(e)},
                       new_status=integrity.MISSING)
        return verification_failure(404, integrity.MISSING, "EVIDENCE_MISSING",
                                    f"{e}. Integrity cannot be verified; the evidence is now marked Missing.", evidence_obj)
    except UnsafeEvidenceLocation as e:
        record_outcome(integrity.VERIFICATION_FAILED, "DATABASE_MISMATCH", integrity.AUDIT_INTEGRITY_INCONSISTENCY,
                       {"detail": e.detail})
        return verification_failure(400, integrity.VERIFICATION_FAILED, "DATABASE_MISMATCH",
                                    f"{e.detail}; the evidence record may have been modified.", evidence_obj)
    except EvidenceStorageUnavailable as e:
        record_outcome(integrity.VERIFICATION_FAILED, "STORAGE_UNAVAILABLE", integrity.AUDIT_VERIFICATION_FAILED, {"detail": e.detail})
        return verification_failure(503, integrity.VERIFICATION_FAILED, "STORAGE_UNAVAILABLE",
                                    f"{e.detail}. Integrity was not checked and the evidence status is unchanged.", evidence_obj)

    # 2. Look up the on-chain registration.
    try:
        registration = blockchain_service.get_registration(evidence_id)
    except BlockchainUnavailable as e:
        logger.error("evidence.verification_chain_unavailable id=%s error=%s", evidence_id, e)
        deep_report = integrity.deep_integrity_verification(
            evidence=evidence_obj,
            calculated_byte_hash=current_hash,
            total_bytes=total_bytes,
            storage_metadata_hash=metadata_hash,
            registration=None,
            receipt=None,
            duplicate_ids=duplicate_evidence_ids(db, evidence_obj),
            blockchain_available=False,
            is_missing=False,
            is_unreadable=False,
        )
        record_outcome(integrity.VERIFICATION_FAILED, "BLOCKCHAIN_UNAVAILABLE", integrity.AUDIT_VERIFICATION_FAILED, {})
        return verification_failure(503, integrity.VERIFICATION_FAILED, "BLOCKCHAIN_UNAVAILABLE",
                                    "The blockchain network is unavailable. Integrity was not checked and the evidence "
                                    "status is unchanged; try again when the node is back.", evidence_obj,
                                    {"calculatedHash": current_hash, "calculatedByteHash": current_hash,
                                     "storageMetadataHash": metadata_hash, "databaseHash": stored_hash,
                                     "deepVerification": True, "deepReport": deep_report})
    if registration is None:
        deep_report = integrity.deep_integrity_verification(
            evidence=evidence_obj,
            calculated_byte_hash=current_hash,
            total_bytes=total_bytes,
            storage_metadata_hash=metadata_hash,
            registration=None,
            receipt=None,
            duplicate_ids=duplicate_evidence_ids(db, evidence_obj),
            blockchain_available=True,
            is_missing=False,
            is_unreadable=False,
        )
        record_outcome(integrity.UNREGISTERED, "NOT_REGISTERED", integrity.AUDIT_EVIDENCE_UNREGISTERED,
                       {"computed_hash": current_hash, "database_hash": stored_hash}, new_status=integrity.UNREGISTERED)
        return verification_failure(409, integrity.UNREGISTERED, "NOT_REGISTERED",
                                    "Evidence is not registered on the blockchain, so its integrity cannot be verified. "
                                    "It is now marked Unregistered.", evidence_obj,
                                    {"calculatedHash": current_hash, "calculatedByteHash": current_hash,
                                     "storageMetadataHash": metadata_hash, "databaseHash": stored_hash,
                                     "deepVerification": True, "deepReport": deep_report})

    # 3. Check the stored registration transaction; adopt missing metadata.
    receipt, receipt_state = registration_receipt_state(evidence_obj)
    if receipt_state == "none":
        try:
            receipt = blockchain_service.find_registration_receipt(evidence_id)
        except BlockchainUnavailable:
            receipt = None
    sync_receipt_metadata(db, evidence_obj, receipt, user_info, request)

    # 4. On-chain verification (the contract's own verdict).
    try:
        is_verified, chain_result = blockchain_service.verify_evidence(evidence_id, current_hash, user_info["id"])
        on_chain = blockchain_service.custody_history(evidence_id)
    except (BlockchainUnavailable, BlockchainTransactionError) as e:
        reason = "BLOCKCHAIN_UNAVAILABLE" if isinstance(e, BlockchainUnavailable) else "TRANSACTION_FAILED"
        logger.error("evidence.verification_tx_failed id=%s error=%s", evidence_id, e)
        record_outcome(integrity.VERIFICATION_FAILED, reason, integrity.AUDIT_VERIFICATION_FAILED, {"detail": str(e)[:300]})
        return verification_failure(503, integrity.VERIFICATION_FAILED, reason,
                                    f"{integrity.REASONS[reason]} The evidence status is unchanged.", evidence_obj,
                                    {"calculatedHash": current_hash, "calculatedByteHash": current_hash,
                                     "storageMetadataHash": metadata_hash, "databaseHash": stored_hash})

    blockchain_hash = chain_result["onChainHash"]
    database_matches_blockchain = stored_hash == blockchain_hash
    status = integrity.VERIFIED if is_verified else integrity.TAMPERED
    reasons = ["HASH_MATCH" if is_verified else "HASH_MISMATCH"]
    warnings = []
    if not database_matches_blockchain:
        reasons.append("DATABASE_MISMATCH")
        warnings.append("The hash stored in the database differs from the hash registered on the blockchain; "
                        "the database record may have been altered. The blockchain hash is authoritative.")
    if receipt_state == "missing":
        reasons.append("TRANSACTION_MISSING")
        warnings.append(integrity.REASONS["TRANSACTION_MISSING"])

    if metadata_hash and metadata_hash.lower() != current_hash.lower():
        reasons.append("METADATA_MISMATCH")
        warnings.append("Storage provider metadata SHA-256 differs from freshly calculated byte hash.")

    deep_report = integrity.deep_integrity_verification(
        evidence=evidence_obj,
        calculated_byte_hash=current_hash,
        total_bytes=total_bytes,
        storage_metadata_hash=metadata_hash,
        registration=registration,
        receipt=receipt,
        duplicate_ids=duplicate_evidence_ids(db, evidence_obj),
        blockchain_available=True,
        is_missing=False,
        is_unreadable=False,
        receipt_known=receipt_state != "unknown",
    )
    checks = deep_report["checks"]

    # 5. Persist status, custody and the on-chain event log.
    try:
        now = datetime.datetime.now(datetime.timezone.utc)
        evidence_obj.verified_at = now
        evidence_obj.verified_by = uuid.UUID(user_info["id"]) if user_info["id"] else None
        evidence_obj.status = status
        evidence_obj.latest_verification_at = chain_result["timestamp"]
        evidence_obj.last_verification_result = status
        evidence_obj.last_verification_reason = reasons[0]
        custody = chain_result["custodyTransaction"]
        db.add(EvidenceCustodyRecord(evidence_id=evidence_obj.id, officer_id=user_info["id"], action="VERIFIED",
                                     occurred_at=custody["timestamp"], transaction_hash=custody["transactionHash"],
                                     block_number=custody["blockNumber"], source="blockchain",
                                     details={"result": status, "sha256": current_hash}))
        payload = {
            "isMatch": is_verified,
            "status": status,
            "calculatedHash": current_hash,
            "blockchainHash": blockchain_hash,
            "databaseHash": stored_hash,
            "storageMetadataHash": metadata_hash,
            "contractAddress": chain_result.get("contractAddress"),
            "gasUsed": chain_result.get("gasUsed"),
            "from": chain_result.get("from"),
        }
        db.add(BlockchainLog(evidence_id=evidence_obj.id, event_name="EvidenceVerified",
                             transaction_hash=chain_result["transactionHash"], block_number=chain_result["blockNumber"],
                             payload=make_json_safe(payload)))
        if not is_verified:
            db.add(BlockchainLog(evidence_id=evidence_obj.id, event_name="EvidenceTampered",
                                 transaction_hash=chain_result["transactionHash"], block_number=chain_result["blockNumber"],
                                 payload=make_json_safe(payload)))
        db.commit()
    except Exception as e:
        db.rollback()
        logger.exception("evidence.verification_persist_failed id=%s", evidence_id)
        raise HTTPException(status_code=500, detail="Failed to update verification status")

    audit_event(integrity.AUDIT_EVIDENCE_VERIFIED if is_verified else integrity.AUDIT_EVIDENCE_TAMPERED,
                user_info, request, result=status, evidence=evidence_obj, file_hash=current_hash,
                details={"stored_hash": stored_hash, "blockchain_hash": blockchain_hash, "computed_hash": current_hash,
                         "match": is_verified, "reasons": reasons, "transaction_hash": chain_result["transactionHash"]})
    if not database_matches_blockchain:
        audit_event(integrity.AUDIT_DB_HASH_MISMATCH, user_info, request, result="Inconsistent", evidence=evidence_obj,
                    details={"database_hash": stored_hash, "blockchain_hash": blockchain_hash})
    other_failures = [c for c in checks if not c["ok"] and c["severity"] == "critical"
                      and c["code"] not in ("FILE_MATCHES_CHAIN", "DB_MATCHES_CHAIN")]
    if other_failures:
        audit_event(integrity.AUDIT_INTEGRITY_INCONSISTENCY, user_info, request, result="Inconsistent", evidence=evidence_obj,
                    details={"checks": other_failures})

    return {
        "data": {
            "isVerified": is_verified,
            "verified": is_verified,
            "result": status,
            "reason": reasons[0],
            "reasons": reasons,
            "reasonText": integrity.REASONS[reasons[0]],
            "storedHash": stored_hash,
            "stored_hash": stored_hash,
            "calculatedHash": current_hash,
            "calculatedByteHash": current_hash,
            "computed_hash": current_hash,
            "totalBytes": total_bytes,
            "storageMetadataHash": metadata_hash,
            "databaseHash": stored_hash,
            "blockchainHash": blockchain_hash,
            "fileMatchesBlockchain": is_verified,
            "databaseMatchesBlockchain": database_matches_blockchain,
            "dbMatchesBytes": (stored_hash == current_hash),
            "metadataMatchesBytes": (metadata_hash == current_hash) if metadata_hash else None,
            "deepVerification": True,
            "deepReport": deep_report,
            "verificationSource": "blockchain",
            "warnings": warnings,
            "integrityChecks": checks,
            "integrity": integrity.integrity_summary(checks),
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
    evidence = load_evidence_for_user(evidence_id, user_info, db)
    try:
        custody = blockchain_service.custody_history(str(evidence.id))
        chain_available = True
    except BlockchainUnavailable:
        custody, chain_available = [], False
    record_view(db, evidence, user_info, request)
    timeline = build_custody_timeline(db, evidence, custody)
    if not chain_available:
        # Graceful degradation: show the locally mirrored on-chain custody entries.
        custody = [{"officerId": e["officerId"], "officer_id": e["officerId"], "action": e["action"], "timestamp": e["timestamp"]}
                   for e in timeline if e["source"] == "blockchain"]
    return {"data": {"status": public_blockchain_status(user_info), "chainAvailable": chain_available,
                     "evidence": serialize_blockchain_metadata(evidence), "custodyHistory": custody,
                     "timeline": timeline}, "success": True}


@app.get("/evidence/{evidence_id}/download")
def download_evidence(evidence_id: str, request: Request, db: Session = Depends(get_db)):
    """Authenticated, audited download. The served bytes are re-hashed and the result is
    returned in X-Evidence-SHA256 / X-Evidence-Integrity so the recipient can check them."""
    user_info = get_current_user_info(request)
    evidence = load_evidence_for_user(evidence_id, user_info, db)
    file_url = evidence.file_url or ""
    try:
        url_str = str(file_url).strip()
        # 1. Canonical Storage Gateway key (e.g. "cases/{case_id}/{filename}")
        if url_str.startswith("cases/") or (not urlparse(url_str).scheme and "/uploads/" not in url_str):
            try:
                provider = get_storage_provider()
                stream = provider.get(url_str)
                body = stream.read()
                stream.close()
                served_hash, path = hashlib.sha256(body).hexdigest(), None
            except KeyNotFoundError:
                raise EvidenceFileMissing(f"Evidence object '{url_str}' not found in storage gateway")
            except StorageUnavailableError as e:
                raise EvidenceStorageUnavailable(f"Storage gateway unreachable: {e}", 502)
            except Exception as e:
                logger.error("evidence.storage_gateway_get_failed key=%s error=%s", url_str, e)
                raise EvidenceStorageUnavailable(f"Failed to read from storage gateway: {e}", 500)
        elif "/uploads/" in file_url:
            path = resolve_upload_path(file_url)
            if not os.path.isfile(path):
                raise EvidenceFileMissing("Evidence file not found in local storage")
            digest = hashlib.sha256()
            with open(path, "rb") as f:
                while chunk := f.read(1 << 20):
                    digest.update(chunk)
            served_hash, body = digest.hexdigest(), None
        else:
            if not storage_url_allowed(file_url):
                raise UnsafeEvidenceLocation("Evidence location is not a recognised evidence store")
            try:
                response = requests.get(file_url, timeout=(5, 120))
            except requests.RequestException:
                raise EvidenceStorageUnavailable("Could not reach evidence storage", 502)
            if response.status_code == 404 or (response.status_code == 400 and "not_found" in response.text.lower()):
                raise EvidenceFileMissing("Evidence file not found in Supabase Storage")
            if response.status_code != 200:
                raise EvidenceStorageUnavailable(f"Evidence storage returned HTTP {response.status_code}", 502)
            body = response.content
            served_hash, path = hashlib.sha256(body).hexdigest(), None
    except EvidenceFileMissing as e:
        audit_event(integrity.AUDIT_EVIDENCE_MISSING, user_info, request, result=integrity.MISSING, evidence=evidence,
                    details={"context": "download", "detail": str(e)})
        raise HTTPException(status_code=404, detail=str(e))

    integrity_state = "match" if served_hash == evidence.file_hash else "mismatch"
    add_offchain_custody(db, evidence, user_info, integrity.CUSTODY_DOWNLOADED,
                         {"sha256": served_hash, "integrity": integrity_state, "ip_address": client_ip(request)})
    db.commit()
    audit_event(integrity.AUDIT_EVIDENCE_DOWNLOADED, user_info, request, result="Success", evidence=evidence,
                file_hash=served_hash, details={"integrity": integrity_state})
    if integrity_state == "mismatch":
        audit_event(integrity.AUDIT_INTEGRITY_INCONSISTENCY, user_info, request, result="Inconsistent", evidence=evidence,
                    details={"context": "download", "served_hash": served_hash, "database_hash": evidence.file_hash})

    headers = {"X-Evidence-SHA256": served_hash, "X-Evidence-Integrity": integrity_state,
               "Access-Control-Expose-Headers": "X-Evidence-SHA256, X-Evidence-Integrity, Content-Disposition"}
    filename = safe_filename(evidence.file_name)
    if path:
        return FileResponse(path, filename=filename, media_type=evidence.mime_type or "application/octet-stream", headers=headers)
    headers["Content-Disposition"] = f'attachment; filename="{filename}"'
    return Response(content=body, media_type=evidence.mime_type or "application/octet-stream", headers=headers)


class EvidenceMetadataUpdate(BaseModel):
    description: Optional[str] = None
    evidence_type: Optional[str] = None


@app.patch("/evidence/{evidence_id}")
def update_evidence_metadata(evidence_id: str, body: EvidenceMetadataUpdate, request: Request, db: Session = Depends(get_db)):
    """Edit descriptive metadata only. The file, its hash and all blockchain fields are immutable."""
    user_info = get_current_user_info(request)
    evidence = load_evidence_for_user(evidence_id, user_info, db)
    if not is_admin(user_info) and str(evidence.uploaded_by or "") != user_info["id"]:
        raise HTTPException(status_code=403, detail="Only the uploader or an administrator can edit evidence metadata")
    changes = {}
    if body.description is not None:
        if len(body.description) > MAX_DESCRIPTION_LENGTH:
            raise HTTPException(status_code=422, detail=f"description is limited to {MAX_DESCRIPTION_LENGTH} characters")
        if body.description != (evidence.description or ""):
            changes["description"] = {"old": evidence.description, "new": body.description}
            evidence.description = body.description
    if body.evidence_type is not None:
        value = body.evidence_type.strip()
        if not value or len(value) > MAX_EVIDENCE_TYPE_LENGTH:
            raise HTTPException(status_code=422, detail=f"evidence_type is required (max {MAX_EVIDENCE_TYPE_LENGTH} characters)")
        if value != evidence.evidence_type:
            changes["evidence_type"] = {"old": evidence.evidence_type, "new": value}
            evidence.evidence_type = value
    if not changes:
        return {"data": serialize_evidence(evidence), "success": True, "changed": []}
    add_offchain_custody(db, evidence, user_info, integrity.CUSTODY_MODIFIED, {"changes": changes})
    db.commit()
    db.refresh(evidence)
    audit_event(integrity.AUDIT_EVIDENCE_MODIFIED, user_info, request, result="Success", evidence=evidence,
                details={"changes": changes})
    return {"data": serialize_evidence(evidence), "success": True, "changed": list(changes)}


class CustodyTransferRequest(BaseModel):
    officer_id: str


@app.post("/evidence/{evidence_id}/custody/transfer")
def transfer_evidence_custody(evidence_id: str, body: CustodyTransferRequest, request: Request, db: Session = Depends(get_db)):
    user_info = get_current_user_info(request)
    evidence = load_evidence_for_user(evidence_id, user_info, db)
    officer_uuid = parse_uuid((body.officer_id or "").strip(), "officer_id")
    officer = db.query(User).filter(User.id == officer_uuid).first()
    if not officer or officer.is_active is False:
        raise HTTPException(status_code=422, detail="officer_id must be an active user")
    officer_id = str(officer_uuid)
    try:
        result = blockchain_service.transfer_custody(str(evidence.id), officer_id)
    except (BlockchainUnavailable, BlockchainTransactionError) as e:
        db.rollback()
        audit_event(integrity.AUDIT_CUSTODY_TRANSFERRED, user_info, request, result="Failed", evidence=evidence,
                    details={"to_officer_id": officer_id, "reason": str(e)[:300]})
        raise HTTPException(status_code=503, detail=str(e))
    db.add(EvidenceCustodyRecord(evidence_id=evidence.id, officer_id=officer_id, action="TRANSFERRED",
                                 occurred_at=result["timestamp"], transaction_hash=result["transactionHash"],
                                 block_number=result["blockNumber"], source="blockchain",
                                 details={"from_officer_id": user_info["id"], "to_officer_name": officer.full_name}))
    db.add(BlockchainLog(evidence_id=evidence.id, event_name="CustodyTransferred", transaction_hash=result["transactionHash"],
                         block_number=result["blockNumber"],
                         payload={"officerId": officer_id, "contractAddress": result.get("contractAddress"),
                                  "gasUsed": result.get("gasUsed"), "from": result.get("from")}))
    db.commit()
    audit_event(integrity.AUDIT_CUSTODY_TRANSFERRED, user_info, request, result="Success", evidence=evidence,
                details={"officer_id": officer_id, "to_officer_name": officer.full_name,
                         "transaction_hash": result["transactionHash"]})
    return {"data": make_json_safe(result), "success": True}


@app.get("/blockchain/status")
def blockchain_status():
    """Public liveness summary (no internal addresses of the RPC endpoint or error text)."""
    status = public_blockchain_status()
    return {
        "network": blockchain_network_name(status.get("chainId")) or "Unavailable" if status.get("connected") else "Unavailable",
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


@app.get("/blockchain/network")
def blockchain_network(request: Request):
    """Connection validation: node, contract code, signing wallet and its authorisation."""
    user_info = get_current_user_info(request)
    info = blockchain_service.network_info()
    if not is_admin(user_info):
        info.pop("walletBalanceWei", None)
        if info.get("error"):
            logger.warning("blockchain.network_error error=%s", info["error"])
            info["error"] = "Blockchain network is currently unavailable"
    return {"data": make_json_safe(info), "success": True}


class BlockchainRegisterRequest(BaseModel):
    evidence_id: str
    case_id: str
    file_name: str
    sha256_hash: str
    officer_id: Optional[str] = None


@app.post("/blockchain/register")
def blockchain_register(body: BlockchainRegisterRequest, request: Request, db: Session = Depends(get_db)):
    """Administrator repair path: register an existing evidence item that has no on-chain record.

    The supplied hash must equal both the stored file's current SHA-256 and the hash recorded
    at upload, so this endpoint can never certify a file that changed after collection.
    """
    user_info = get_current_user_info(request)
    require_admin(user_info, request, "blockchain.register")
    evidence = load_evidence_for_user(body.evidence_id, user_info, db)
    supplied = (body.sha256_hash or "").strip().lower()
    if not is_sha256_hex(supplied):
        raise HTTPException(status_code=422, detail="sha256_hash must be a 64-character hexadecimal SHA-256 digest")
    if str(evidence.case_id) != body.case_id.strip():
        raise HTTPException(status_code=422, detail="case_id does not match the evidence record")
    try:
        current_hash = compute_evidence_file_hash(evidence.file_url)
    except EvidenceFileMissing as e:
        raise HTTPException(status_code=404, detail=str(e))
    if supplied != current_hash or (evidence.file_hash and evidence.file_hash != current_hash):
        audit_event(integrity.AUDIT_REGISTRATION_FAILED, user_info, request, result="Rejected", evidence=evidence,
                    details={"reason": "hash does not match the stored file or the upload hash", "supplied_hash": supplied,
                             "current_hash": current_hash})
        raise HTTPException(status_code=409, detail="Refusing to register: the hash does not match the stored file "
                                                    "and the hash recorded at upload")
    if body.officer_id and body.officer_id != user_info["id"]:
        logger.info("blockchain.register officer_id override ignored requested=%s", body.officer_id)
    try:
        receipt = blockchain_service.register_evidence(str(evidence.id), str(evidence.case_id),
                                                       evidence.file_name or str(evidence.id), current_hash, user_info["id"])
    except (BlockchainUnavailable, BlockchainTransactionError) as e:
        db.rollback()
        audit_event(integrity.AUDIT_REGISTRATION_FAILED, user_info, request, result="Failed", evidence=evidence,
                    details={"reason": str(e)[:300]})
        raise HTTPException(status_code=503, detail=str(e))
    if not evidence.file_hash:
        evidence.file_hash = current_hash
    apply_registration_receipt(evidence, receipt)
    evidence.status = integrity.VERIFIED
    evidence.last_verification_result, evidence.last_verification_reason = integrity.VERIFIED, "HASH_MATCH"
    db.add(EvidenceCustodyRecord(evidence_id=evidence.id, officer_id=user_info["id"], action="REGISTERED",
                                 occurred_at=receipt["timestamp"], transaction_hash=receipt["transactionHash"],
                                 block_number=receipt["blockNumber"], source="blockchain"))
    db.add(BlockchainLog(evidence_id=evidence.id, event_name="EvidenceRegistered", transaction_hash=receipt["transactionHash"],
                         block_number=receipt["blockNumber"],
                         payload=make_json_safe({"caseId": str(evidence.case_id), "fileName": evidence.file_name,
                                                 "sha256Hash": current_hash, "officerId": user_info["id"],
                                                 "contractAddress": receipt["contractAddress"], "gasUsed": receipt["gasUsed"],
                                                 "from": receipt.get("from"), "source": "admin-register"})))
    db.commit()
    audit_event(integrity.AUDIT_EVIDENCE_REGISTERED, user_info, request, result="Success", evidence=evidence,
                details={"transaction_hash": receipt["transactionHash"], "source": "admin-register"})
    return {"data": make_json_safe({**receipt, "timestamp": receipt["timestamp"].isoformat()}), "success": True}


class BlockchainVerifyRequest(BaseModel):
    evidence_id: str
    sha256_hash: str
    officer_id: Optional[str] = None


@app.post("/blockchain/verify")
def blockchain_verify(body: BlockchainVerifyRequest, request: Request, db: Session = Depends(get_db)):
    """Administrator check of a caller-supplied hash against the chain.

    Because the hash is supplied, not computed from the stored file, the result never
    changes the evidence status; POST /evidence/{id}/verify is the authoritative check.
    """
    user_info = get_current_user_info(request)
    require_admin(user_info, request, "blockchain.verify")
    evidence = load_evidence_for_user(body.evidence_id, user_info, db)
    supplied = (body.sha256_hash or "").strip().lower()
    if not is_sha256_hex(supplied):
        raise HTTPException(status_code=422, detail="sha256_hash must be a 64-character hexadecimal SHA-256 digest")
    try:
        is_match, verification = blockchain_service.verify_evidence(str(evidence.id), supplied, user_info["id"])
    except (BlockchainUnavailable, BlockchainTransactionError) as e:
        db.rollback()
        audit_event(integrity.AUDIT_VERIFICATION_FAILED, user_info, request, result=integrity.VERIFICATION_FAILED,
                    evidence=evidence, details={"source": "blockchain.verify", "reason": str(e)[:300]})
        raise HTTPException(status_code=503, detail=str(e))
    custody = verification.get("custodyTransaction", {})
    db.add(EvidenceCustodyRecord(evidence_id=evidence.id, officer_id=user_info["id"], action="VERIFIED",
                                 occurred_at=custody.get("timestamp", verification["timestamp"]),
                                 transaction_hash=custody.get("transactionHash"), block_number=custody.get("blockNumber"),
                                 source="blockchain", details={"supplied_hash": supplied, "match": is_match}))
    payload = {"isMatch": is_match, "status": "Verified" if is_match else "Tampered", "calculatedHash": supplied,
               "source": "caller-supplied", "officerId": user_info["id"],
               "contractAddress": verification.get("contractAddress"), "gasUsed": verification.get("gasUsed")}
    db.add(BlockchainLog(evidence_id=evidence.id, event_name="EvidenceVerified", transaction_hash=verification["transactionHash"],
                         block_number=verification["blockNumber"], payload=payload))
    db.commit()
    audit_event("Blockchain Hash Check", user_info, request, result="Match" if is_match else "Mismatch", evidence=evidence,
                file_hash=supplied, details={"transaction_hash": verification["transactionHash"],
                                             "note": "caller-supplied hash; evidence status unchanged"})
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


def serialize_blockchain_log(log) -> dict:
    return {
        "id": str(log.id),
        "evidenceId": str(log.evidence_id) if log.evidence_id else None,
        "event": log.event_name,
        "eventName": log.event_name,
        "transactionHash": log.transaction_hash,
        "transaction_hash": log.transaction_hash,
        "blockNumber": log.block_number,
        "block_number": log.block_number,
        "payload": log.payload,
        "createdAt": log.created_at.isoformat() if log.created_at else None,
        "created_at": log.created_at.isoformat() if log.created_at else None,
    }


@app.get("/blockchain/history/{evidence_id}")
def blockchain_evidence_history(evidence_id: str, request: Request, db: Session = Depends(get_db)):
    user_info = get_current_user_info(request)
    evidence = load_evidence_for_user(evidence_id, user_info, db)
    try:
        chain_history, chain_available = blockchain_service.custody_history(str(evidence.id)), True
    except BlockchainUnavailable:
        chain_history, chain_available = [], False
    logs = db.query(BlockchainLog).filter(BlockchainLog.evidence_id == evidence.id).order_by(BlockchainLog.created_at.asc()).all()
    return {
        "data": {
            "evidenceId": str(evidence.id),
            "chainAvailable": chain_available,
            "custodyHistory": chain_history,
            "timeline": build_custody_timeline(db, evidence, chain_history),
            "blockchainLogs": [serialize_blockchain_log(log) for log in logs]
        },
        "success": True
    }


@app.get("/blockchain/evidence/{evidence_id}")
def blockchain_evidence_detail(evidence_id: str, request: Request, db: Session = Depends(get_db)):
    """Everything the ledger's detail modal needs: stored metadata, on-chain record,
    consistency checks (database vs chain, without re-hashing the file) and custody."""
    user_info = get_current_user_info(request)
    evidence = load_evidence_for_user(evidence_id, user_info, db)
    registration, chain_available, chain_history = None, True, []
    try:
        registration = blockchain_service.get_registration(str(evidence.id))
        chain_history = blockchain_service.custody_history(str(evidence.id))
    except BlockchainUnavailable:
        chain_available = False
    receipt, receipt_state = registration_receipt_state(evidence) if chain_available else (None, "unknown")
    if chain_available and receipt_state == "none" and registration is not None:
        receipt = blockchain_service.find_registration_receipt(str(evidence.id))
    if chain_available:
        sync_receipt_metadata(db, evidence, receipt, user_info, request)
    duplicates = duplicate_evidence_ids(db, evidence)
    checks = (integrity.integrity_checks(evidence, registration, receipt, duplicates,
                                         receipt_known=receipt_state != "unknown") if chain_available else [])
    record_view(db, evidence, user_info, request)
    return {"data": make_json_safe({
        "evidence": ledger_row(evidence),
        "blockchain": serialize_blockchain_metadata(evidence),
        "onChain": ({**registration, "timestamp": registration["timestamp"].isoformat()} if registration else None),
        "chainAvailable": chain_available,
        "transactionState": receipt_state,
        "integrityChecks": checks,
        "integrity": integrity.integrity_summary(checks) if checks else "Unknown",
        "duplicateEvidenceIds": duplicates,
        "timeline": build_custody_timeline(db, evidence, chain_history),
        "status": public_blockchain_status(user_info),
    }), "success": True}


@app.get("/blockchain/transaction/{tx_hash}")
def blockchain_transaction(tx_hash: str, request: Request, db: Session = Depends(get_db)):
    """Transaction details for the ledger modal (Ganache has no block explorer)."""
    user_info = get_current_user_info(request)
    if not TX_HASH_HEX.match(tx_hash or ""):
        raise HTTPException(status_code=400, detail="Invalid transaction hash")
    variants = hex_variants(tx_hash)
    evidence_id = (db.query(Evidence.id).filter(Evidence.blockchain_tx_hash.in_(variants)).scalar()
                   or db.query(EvidenceCustodyRecord.evidence_id).filter(EvidenceCustodyRecord.transaction_hash.in_(variants)).scalar()
                   or db.query(BlockchainLog.evidence_id).filter(BlockchainLog.transaction_hash.in_(variants),
                                                                 BlockchainLog.evidence_id.isnot(None)).limit(1).scalar())
    if evidence_id:
        load_evidence_for_user(str(evidence_id), user_info, db)
    elif not is_admin(user_info):
        raise HTTPException(status_code=404, detail="Transaction not found")
    try:
        details = blockchain_service.transaction_details(tx_hash)
    except BlockchainUnavailable:
        raise HTTPException(status_code=503, detail="Blockchain network is currently unavailable")
    if details is None:
        raise HTTPException(status_code=404, detail="Transaction not found on the blockchain")
    details["evidenceId"] = str(evidence_id) if evidence_id else None
    return {"data": make_json_safe(details), "success": True}


def visible_evidence_query(db: Session, user_info: dict):
    """Evidence the user may see: everything for administrators, own/unowned cases otherwise."""
    query = db.query(Evidence)
    if get_data_visibility(user_info, "view_cases") == "all":
        return query
    user_uuid = parse_uuid(user_info["id"], "user ID")
    case_ids = db.query(Case.id).filter((Case.created_by == user_uuid) | (Case.created_by.is_(None)))
    return query.filter(Evidence.case_id.in_(case_ids))


def ledger_row(evidence) -> dict:
    return {
        "id": str(evidence.id),
        "caseId": str(evidence.case_id) if evidence.case_id else None,
        "fileName": evidence.file_name,
        "evidenceType": evidence.evidence_type,
        "sha256": evidence.file_hash,
        "status": evidence.status,
        "uploadedBy": evidence.uploaded_by_name,
        "createdAt": evidence.created_at.isoformat() if evidence.created_at else None,
        "blockchainStatus": "Registered" if evidence.blockchain_tx_hash else "Not registered",
        "verificationStatus": evidence.last_verification_result or evidence.status,
        "verificationReason": evidence.last_verification_reason,
        "verifiedAt": evidence.verified_at.isoformat() if evidence.verified_at else None,
        **serialize_blockchain_metadata(evidence),
    }


@app.get("/blockchain/ledger")
def blockchain_ledger(request: Request, search: Optional[str] = None, status: Optional[str] = None,
                      limit: int = 50, offset: int = 0, db: Session = Depends(get_db)):
    """Paginated evidence ledger for the Blockchain Ledger page (scoped to the user's cases)."""
    user_info = get_current_user_info(request)
    limit, offset = max(1, min(limit, 200)), max(0, offset)
    query = visible_evidence_query(db, user_info)
    if status and status != "All":
        query = query.filter(Evidence.status == status) if status in integrity.EVIDENCE_STATES else \
            query.filter(Evidence.last_verification_result == status)
    if search:
        term = f"%{search.strip()[:100]}%"
        query = query.filter(Evidence.file_name.ilike(term) | Evidence.file_hash.ilike(term)
                             | Evidence.blockchain_tx_hash.ilike(term))
    total = query.count()
    rows = query.order_by(Evidence.created_at.desc()).offset(offset).limit(limit).all()
    return {"data": [ledger_row(row) for row in rows], "total": total, "limit": limit, "offset": offset, "success": True}


@app.get("/blockchain/dashboard")
def blockchain_dashboard(request: Request, db: Session = Depends(get_db)):
    user_info = get_current_user_info(request)
    status = public_blockchain_status(user_info)
    scoped = visible_evidence_query(db, user_info)
    visible_ids = scoped.with_entities(Evidence.id)

    def count(*criteria) -> int:
        return scoped.filter(*criteria).count()

    total_evidence = scoped.count()
    registered = count(Evidence.blockchain_tx_hash.isnot(None))
    verified = count(Evidence.status == integrity.VERIFIED, Evidence.blockchain_tx_hash.isnot(None))
    tampered = count(Evidence.status == integrity.TAMPERED)
    missing = count(Evidence.status == integrity.MISSING)
    unregistered = count(Evidence.blockchain_tx_hash.is_(None) | (Evidence.status == integrity.UNREGISTERED))
    verification_failed = count(Evidence.last_verification_result == integrity.VERIFICATION_FAILED)
    metadata_incomplete = count(Evidence.blockchain_tx_hash.isnot(None),
                                Evidence.blockchain_block_hash.is_(None) | Evidence.blockchain_wallet_address.is_(None))

    events = db.query(BlockchainLog).filter(BlockchainLog.evidence_id.in_(visible_ids))
    verification_events = events.filter(BlockchainLog.event_name == "EvidenceVerified")
    matches = verification_events.filter(BlockchainLog.payload["isMatch"].astext == "true").count()
    checks = verification_events.count()
    success_rate = round(100.0 * matches / checks, 1) if checks else None

    recent_txs = [serialize_blockchain_log(log) for log in events.order_by(BlockchainLog.created_at.desc()).limit(10).all()]
    verification_actions = [integrity.AUDIT_EVIDENCE_VERIFIED, integrity.AUDIT_EVIDENCE_TAMPERED, integrity.AUDIT_EVIDENCE_MISSING,
                            integrity.AUDIT_EVIDENCE_UNREGISTERED, integrity.AUDIT_VERIFICATION_FAILED, integrity.AUDIT_DB_HASH_MISMATCH]
    audit_query = db.query(AuditLog).filter(AuditLog.action.in_(verification_actions))
    if get_data_visibility(user_info, "view_cases") != "all":
        audit_query = audit_query.filter(AuditLog.metadata_["evidence_id"].astext.in_(
            [str(row[0]) for row in visible_ids.all()] or ["-"]))
    latest_verifications = [{
        "action": log.action,
        "status": integrity.audit_status(log.action),
        "result": (log.metadata_ or {}).get("result"),
        "reason": (log.metadata_ or {}).get("reason"),
        "evidenceId": (log.metadata_ or {}).get("evidence_id"),
        "userName": (log.metadata_ or {}).get("user_name"),
        "createdAt": log.created_at.isoformat() if log.created_at else None,
    } for log in audit_query.order_by(AuditLog.created_at.desc()).limit(10).all()]

    blocks = []
    if status.get("connected"):
        try:
            blocks = blockchain_service.recent_blocks()
        except Exception as e:
            logger.warning("blockchain.recent_blocks_failed error=%s", e)

    stats = {
        "totalEvidence": total_evidence,
        "totalRegisteredEvidence": registered,
        "verifiedEvidence": verified,
        "tamperedEvidence": tampered,
        "missingEvidence": missing,
        "unregisteredEvidence": unregistered,
        "verificationFailed": verification_failed,
        "metadataIncomplete": metadata_incomplete,
        "verificationChecks": checks,
        "verificationSuccessRate": success_rate,
    }
    return {
        "network": blockchain_network_name(status.get("chainId")) or "Unavailable" if status.get("connected") else "Unavailable",
        "chain_id": status.get("chainId", 1337),
        "contract_address": status.get("contractAddress", ""),
        "latest_block": status.get("latestBlock", 0),
        "registered_evidence": registered,
        "verified_evidence": verified,
        "tampered_evidence": tampered,
        "pending_transactions": 0,
        "recent_transactions": recent_txs,
        "status": "online" if status.get("connected") else "offline",
        "data": {
            "status": status,
            **stats,
            "latestTransactions": recent_txs,
            "latestVerificationEvents": latest_verifications,
            "latestBlocks": blocks,
            "pendingTransactions": 0
        },
        "success": True
    }


@app.post("/blockchain/integrity-scan")
def blockchain_integrity_scan(request: Request, db: Session = Depends(get_db)):
    """Administrator scan: database vs blockchain for every evidence item (files are not re-hashed).

    Fills empty metadata from receipts and writes one audit entry per inconsistent item.
    """
    user_info = get_current_user_info(request)
    require_admin(user_info, request, "blockchain.integrity-scan")
    if not blockchain_service.status().get("connected"):
        raise HTTPException(status_code=503, detail="Blockchain network is currently unavailable")
    results, counts = [], {"Consistent": 0, "Warning": 0, "Inconsistent": 0}
    for evidence in db.query(Evidence).order_by(Evidence.created_at.asc()).all():
        try:
            registration = blockchain_service.get_registration(str(evidence.id))
            receipt, state = registration_receipt_state(evidence)
            if state == "none" and registration is not None:
                receipt = blockchain_service.find_registration_receipt(str(evidence.id))
            backfilled = sync_receipt_metadata(db, evidence, receipt, user_info, request)
        except BlockchainUnavailable:
            raise HTTPException(status_code=503, detail="Blockchain network became unavailable during the scan")
        checks = integrity.integrity_checks(evidence, registration, receipt, duplicate_evidence_ids(db, evidence),
                                            receipt_known=state != "unknown")
        summary = integrity.integrity_summary(checks)
        counts[summary] += 1
        failed = [c for c in checks if not c["ok"]]
        if summary == "Inconsistent":
            audit_event(integrity.AUDIT_INTEGRITY_INCONSISTENCY, user_info, request, result="Inconsistent", evidence=evidence,
                        details={"checks": failed, "source": "integrity-scan"})
        results.append({"evidenceId": str(evidence.id), "fileName": evidence.file_name, "integrity": summary,
                        "failedChecks": failed, "metadataBackfilled": backfilled})
    audit_event("Blockchain Integrity Scan", user_info, request, result="Success", details={"summary": counts})
    return {"data": {"summary": counts, "items": results}, "success": True}


@app.get("/health")
def health_check():
    """Liveness/readiness: database is required, the blockchain may be degraded."""
    from db import test_connection
    database_ok = test_connection()
    chain = blockchain_service.network_info()
    body = {
        "status": "ok" if database_ok and chain.get("connected") else ("degraded" if database_ok else "down"),
        "database": "ok" if database_ok else "down",
        "blockchain": {
            "connected": bool(chain.get("connected")),
            "contractDeployed": chain.get("contractDeployed"),
            "walletAuthorised": chain.get("walletAuthorised"),
            "latestBlock": chain.get("latestBlock"),
            "latencyMs": chain.get("latencyMs"),
        },
    }
    return JSONResponse(status_code=200 if database_ok else 503, content=make_json_safe(body))


@app.post("/admin/blockchain/redeploy")
def redeploy_evidence_registry(request: Request):
    user_info = get_current_user_info(request)
    require_admin(user_info, request, "blockchain.redeploy")
    root = Path(__file__).resolve().parents[1]
    try:
        subprocess.run(["npx", "hardhat", "compile"], cwd=root / "blockchain", check=True, capture_output=True, text=True, timeout=120)
        subprocess.run(["node", "scripts/deploy.js"], cwd=root / "blockchain", check=True, capture_output=True, text=True, timeout=120)
        blockchain_service.reload()
        write_audit_log(user_info["id"], "EvidenceRegistry Redeployed",
                        metadata={"contract_address": blockchain_service.status().get("contractAddress"),
                                  "ip_address": client_ip(request), "result": "Success"})
        return {"data": blockchain_service.status(), "success": True}
    except (subprocess.SubprocessError, BlockchainUnavailable) as e:
        logger.exception("Admin contract redeployment failed")
        raise HTTPException(status_code=503, detail=f"Contract deployment failed: {e}")

# ====== DETECTION ENDPOINTS ======
@app.post("/detect")
async def detect_direct(request: Request, image: UploadFile = File(...)):
    user_info = get_current_user_info(request)
    if not has_permission(user_info, "run_ai_analysis"):
        raise HTTPException(status_code=403, detail="Forbidden: You do not have permission to run object detection.")
    try:
        contents = await image.read()
        resp = requests.post(
            CRIME_DETECTION_SERVICE_URL,
            files={"image": (image.filename or "image.jpg", contents, image.content_type or "image/jpeg")},
            data={"confidence": 0.25},
            timeout=30
        )
        if resp.status_code != 200:
            raise HTTPException(status_code=resp.status_code, detail=f"Detection error: {resp.text}")
        result_json = resp.json()
        write_audit_log(
            user_id=user_info["id"],
            action="Object Detection Direct",
            metadata={"filename": image.filename, "file_size": len(contents), "predictions_count": len(result_json.get("predictions", []))}
        )
        return JSONResponse(content=result_json)
    except HTTPException:
        raise
    except requests.RequestException as e:
        raise HTTPException(status_code=502, detail=f"Crime detection service (port 8003) unreachable: {e}")

@app.post("/ai/detect")
def run_ai_detect(req: DetectionRequest, request: Request, db: Session = Depends(get_db)):
    print(f"\n[DEBUG] /ai/detect called with evidence_id: {req.evidence_id}, case_id: {req.case_id}")
    
    user_info = get_current_user_info(request)
    check_case_access(req.case_id, user_info, db)

    # ---------------------------------------------------------
    # Original Code (Alisha) - Roboflow Model Check:
    # if not model:
    #     print("[DEBUG] Roboflow model is None")
    #     raise HTTPException(status_code=500, detail="Roboflow model not loaded")
    # ---------------------------------------------------------

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

            # Save to temporary local file for prediction
            file_id = str(uuid.uuid4())
            ext = file_path.split(".")[-1].split("?")[0]
            local_temp_file = os.path.join(UPLOADS_DIR, f"temp_{file_id}.{ext}")
            with open(local_temp_file, "wb") as f:
                f.write(file_bytes)
        elif file_path.startswith("cases/") or (not urlparse(file_path).scheme and "/uploads/" not in file_path and not os.path.exists(file_path)):
            is_remote_download = True
            try:
                provider = get_storage_provider()
                stream = provider.get(file_path)
                file_bytes = stream.read()
                if hasattr(stream, "close"):
                    stream.close()
                current_hash = hashlib.sha256(file_bytes).hexdigest()
                file_id = str(uuid.uuid4())
                ext = file_path.split(".")[-1].split("?")[0]
                local_temp_file = os.path.join(UPLOADS_DIR, f"temp_{file_id}.{ext}")
                with open(local_temp_file, "wb") as f:
                    f.write(file_bytes)
            except Exception as e:
                raise HTTPException(status_code=404, detail=f"Evidence file missing in storage gateway: {e}")
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

        # ---------------------------------------------------------
        # Original Code (Alisha) - Roboflow Prediction:
        # prediction = model.predict(local_temp_file).json()
        # print(f"[DEBUG] Prediction response: {str(prediction)[:200]}...")
        # ---------------------------------------------------------
        
        # Prepare base64 preview data URL and measure image dimensions before any cleanup
        preview_data_url = None
        image_width, image_height = 800.0, 600.0
        try:
            with open(local_temp_file, "rb") as img_f:
                raw_bytes = img_f.read()
                ext_clean = os.path.splitext(local_temp_file)[1].lower().replace(".", "")
                mime = f"image/{ext_clean}" if ext_clean in ("png", "webp", "gif") else "image/jpeg"
                preview_data_url = f"data:{mime};base64,{base64.b64encode(raw_bytes).decode('utf-8')}"
            from PIL import Image
            import io
            with Image.open(io.BytesIO(raw_bytes)) as im:
                image_width, image_height = float(im.width), float(im.height)
        except Exception as e:
            print(f"[DEBUG] Failed to parse image preview or dimensions: {e}")

        # Call local YOLOv8 Object Detection Service (Port 8003)
        try:
            with open(local_temp_file, "rb") as img_f:
                fname = os.path.basename(local_temp_file)
                resp = requests.post(
                    CRIME_DETECTION_SERVICE_URL,
                    files={"image": (fname, img_f, "image/jpeg")},
                    data={"confidence": 0.25},
                    timeout=30
                )
            if resp.status_code != 200:
                raise HTTPException(status_code=resp.status_code, detail=f"Object detection service error: {resp.text}")
            prediction = resp.json()
            print(f"[DEBUG] Local YOLO prediction response: {prediction}")
        except HTTPException:
            raise
        except Exception as e:
            print(f"[DEBUG] Object detection service error: {e}")
            raise HTTPException(status_code=500, detail=f"Object detection service (port 8003) unreachable: {e}")
    except HTTPException:
        raise
    except Exception as e:
        print(f"[DEBUG] Detection threw error: {e}")
        raise HTTPException(status_code=500, detail=f"Detection failed: {e}")
    finally:
        # Always clean up temporary file if it was downloaded from storage
        if is_remote and is_remote_download and local_temp_file and os.path.exists(local_temp_file):
            try:
                os.remove(local_temp_file)
            except Exception as e:
                print(f"[DEBUG] Failed to delete temporary file {local_temp_file}: {e}")

    objects = []
    
    # Parse local YOLOv8 detections format from port 8003
    for det in prediction.get("detections", []):
        bbox = det.get("bbox", {})
        if isinstance(bbox, dict):
            x1 = float(bbox.get("x1", 0))
            y1 = float(bbox.get("y1", 0))
            x2 = float(bbox.get("x2", 0))
            y2 = float(bbox.get("y2", 0))
            w = max(0.0, x2 - x1)
            h = max(0.0, y2 - y1)
            left_pct = (x1 / image_width) * 100
            top_pct = (y1 / image_height) * 100
            w_pct = (w / image_width) * 100
            h_pct = (h / image_height) * 100
            objects.append({
                "label": det.get("label", "suspicious_object"),
                "confidence": float(det.get("confidence") or 0.85),
                "bbox": [f"{left_pct:.2f}%", f"{top_pct:.2f}%", f"{w_pct:.2f}%", f"{h_pct:.2f}%"]
            })

    image_url_full = file_path if is_remote else f"http://localhost:8000/{file_path}"
    # Use data URL for immediate, authenticated frontend display without forbidden /uploads access
    result_data = {"objects": objects, "image_url": preview_data_url or image_url_full}

    # ---------------------------------------------------------
    # Original Code (Alisha) - Cloud Supabase Storage:
    # det_record = {
    #     "case_id": req.case_id,
    #     "evidence_id": req.evidence_id,
    #     "image_url": image_url_full,
    #     "predictions": {"objects": objects}
    # }
    # supabase_admin.table("detections").insert(det_record).execute()
    # ---------------------------------------------------------
    # Updated: Save to local PostgreSQL database
    try:
        cid = uuid.UUID(req.case_id) if isinstance(req.case_id, str) else req.case_id
        eid = uuid.UUID(req.evidence_id) if isinstance(req.evidence_id, str) else req.evidence_id
        det_obj = Detection(
            case_id=cid,
            evidence_id=eid,
            image_url=image_url_full,
            predictions={"objects": objects}
        )
        db.add(det_obj)
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"[WARN] Failed to save detection record to local DB: {e}")

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
def get_case_detections(case_id: str, request: Request, db: Session = Depends(get_db)):
    user_info = get_current_user_info(request)
    check_case_access(case_id, user_info, db)
    # ---------------------------------------------------------
    # Original Code (Alisha) - Supabase Query:
    # res = supabase_admin.table("detections").select("*").eq("case_id", case_id).execute()
    # return {"data": res.data}
    # ---------------------------------------------------------
    # Updated: Query from local PostgreSQL database
    try:
        cid = uuid.UUID(case_id) if isinstance(case_id, str) else case_id
        records = db.query(Detection).filter(Detection.case_id == cid).all()
        return {"data": [{"id": str(r.id), "case_id": str(r.case_id), "evidence_id": str(r.evidence_id), "image_url": r.image_url, "predictions": r.predictions, "created_at": str(r.created_at)} for r in records]}
    except Exception as e:
        print(f"[WARN] Failed to fetch detections from DB: {e}")
        return {"data": []}

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

    url_str = str(file_url).strip()
    if url_str.startswith("cases/") or (not urlparse(url_str).scheme and "/uploads/" not in url_str):
        try:
            provider = get_storage_provider()
            stream = provider.get(url_str)
            content = stream.read()
            stream.close()
            return bytes(content)
        except Exception as exc:
            print(f"[OCR] storage gateway evidence retrieval failed: {exc}")
            raise HTTPException(status_code=404, detail="Uploaded evidence file was not found") from exc

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


# ====== AUDIO FORENSICS PROXY ENDPOINT ======
AUDIO_SERVICE_URL = os.getenv("AUDIO_SERVICE_URL", "http://127.0.0.1:8002/audio/analyze")

@app.post("/ai/audio/analyze")
async def analyze_audio_gateway(
    request: Request,
    audio: Optional[UploadFile] = File(None),
    file: Optional[UploadFile] = File(None),
    case_id: Optional[str] = Form(None),
    evidence_id: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    """Authenticated gateway proxy for audio forensics. Enforces RBAC, case/evidence authorization, and records audit trail."""
    user_info = get_current_user_info(request)
    if not has_permission(user_info, "run_ai_analysis"):
        raise HTTPException(status_code=403, detail="Forbidden: You do not have permission to run audio analysis.")

    upload_file = audio or file
    if not upload_file:
        raise HTTPException(status_code=400, detail="Missing audio file for analysis.")

    clean_case_id = (case_id or "").strip() or None
    clean_evidence_id = (evidence_id or "").strip() or None
    target_case_id = clean_case_id
    evidence_record = None

    if clean_evidence_id:
        evidence_record = load_evidence_for_user(clean_evidence_id, user_info, db)
        if clean_case_id:
            if str(evidence_record.case_id) != clean_case_id:
                raise HTTPException(
                    status_code=400,
                    detail="Specified evidence does not belong to the specified case."
                )
        else:
            target_case_id = str(evidence_record.case_id) if evidence_record.case_id else None
    elif clean_case_id:
        check_case_access(clean_case_id, user_info, db)

    try:
        contents = await upload_file.read()
        if not contents or len(contents) == 0:
            raise HTTPException(status_code=400, detail="The uploaded file is empty (0 bytes).")

        resp = requests.post(
            AUDIO_SERVICE_URL,
            files={"audio": (upload_file.filename or "audio.wav", contents, upload_file.content_type or "audio/wav")},
            timeout=180
        )
        if resp.status_code != 200:
            raise HTTPException(status_code=resp.status_code, detail=f"Audio analysis service error: {resp.text}")

        result_data = resp.json()
        action_name = "Audio Forensics Analysis" if target_case_id else "Audio Forensics Analysis (Ad-hoc)"
        write_audit_log(
            user_id=user_info["id"],
            action=action_name,
            case_id=target_case_id,
            metadata={
                "filename": upload_file.filename,
                "file_size": len(contents),
                "evidence_id": str(evidence_record.id) if evidence_record else clean_evidence_id,
                "duration": result_data.get("duration"),
                "sample_rate": result_data.get("sample_rate"),
                "overall_status": result_data.get("overall_status") or result_data.get("audio_status"),
                "is_adhoc": target_case_id is None
            },
            db=db
        )
        return result_data
    except HTTPException:
        raise
    except requests.RequestException as e:
        raise HTTPException(status_code=502, detail=f"Failed to communicate with audio forensics microservice: {str(e)}")



# ── 6. Real audit log retrieval ───────────────────────────────────────────────
def get_status_for_action(action: str) -> str:
    return integrity.audit_status(action)

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
def bns_predict(payload: BNSRequest, request: Request):
    user_info = get_current_user_info(request)
    if not has_permission(user_info, "run_ai_analysis"):
        raise HTTPException(status_code=403, detail="Forbidden: You do not have permission to run BNS prediction.")
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

        write_audit_log(
            user_id=user_info["id"],
            action="BNS Section Prediction",
            metadata={"fir_length": len(payload.fir_text or ""), "sections_count": len(bns_list)}
        )

        return {
            "bns": bns_list,
            "sections": bns_list,
            "crime_type": raw_data.get("crime_type", "Multi-Offence Incident"),
            "crime_categories": raw_data.get("crime_categories", []),
            "total_sections": len(bns_list),
            "threshold_applied": raw_data.get("threshold_applied", payload.threshold or 0.35)
        }
    except HTTPException:
        raise
    except requests.RequestException as e:
        raise HTTPException(status_code=502, detail=f"Failed to communicate with BNS server: {str(e)}")

@app.post("/bns/store")
def bns_store(payload: BNSStore, request: Request, db: Session = Depends(get_db)):
    user_info = get_current_user_info(request)
    check_case_access(payload.case_id, user_info, db)

    try:
        # [PRESERVATION] Append-only: keep historical prediction records rather than destroying them
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
        metadata={"crime_type": payload.crime_type, "sections_count": len(payload.sections)},
        db=db
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
def photogrammetry_status(case_id: str, request: Request, evidence_id: Optional[str] = None):
    try:
        user_info = get_current_user_info(request)
        try:
            case_uuid = uuid.UUID(case_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="case_id must be a valid UUID.") from exc

        evidence_uuid = None
        if evidence_id:
            try:
                evidence_uuid = uuid.UUID(evidence_id)
            except ValueError as exc:
                raise HTTPException(status_code=400, detail="evidence_id must be a valid UUID.") from exc

        # Keep the microservice private behind this authenticated, case-scoped proxy.
        with SessionLocal() as db:
            check_case_access(case_id, user_info, db)
            if evidence_uuid:
                evidence = db.query(Evidence).filter(
                    Evidence.id == evidence_uuid,
                    Evidence.case_id == case_uuid
                ).first()
                if not evidence:
                    raise HTTPException(status_code=404, detail="Evidence not found for this case.")

        # Proxy request to photogrammetry-backend server on port 8004
        params = {}
        if evidence_id:
            params["evidence_id"] = evidence_id

        res = requests.get(f"http://localhost:8004/status/{case_id}", params=params, timeout=10)
        if res.status_code == 404:
            detail_msg = "Reconstruction job not found."
            try:
                err_json = res.json()
                if isinstance(err_json, dict) and "detail" in err_json:
                    detail_msg = err_json["detail"]
            except Exception:
                pass
            raise HTTPException(status_code=404, detail=detail_msg)
        res.raise_for_status()
        return res.json()
    except HTTPException:
        raise
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


@app.get("/photogrammetry/evaluation/{job_id}")
def photogrammetry_job_evaluation(job_id: str, request: Request):
    try:
        user_info = get_current_user_info(request)
        res = requests.get(f"http://localhost:8004/jobs/{job_id}/evaluation", timeout=10)
        res.raise_for_status()
        return res.json()
    except requests.RequestException as e:
        raise HTTPException(status_code=502, detail=f"Failed to communicate with photogrammetry server: {str(e)}")


@app.get("/photogrammetry/comparison")
def photogrammetry_benchmark_comparison(request: Request):
    try:
        user_info = get_current_user_info(request)
        res = requests.get(f"http://localhost:8004/jobs/comparison", timeout=10)
        res.raise_for_status()
        return res.json()
    except requests.RequestException as e:
        raise HTTPException(status_code=502, detail=f"Failed to communicate with photogrammetry server: {str(e)}")


@app.get("/photogrammetry/model/{job_id}/{fmt}")
def photogrammetry_get_model(
    job_id: str,
    fmt: str,
    request: Request,
    download: bool = False,
    db: Session = Depends(get_db)
):
    """
    Authenticated and case-authorized streaming endpoint for photogrammetry models.
    Supports fmt='glb' (3D mesh) and fmt='ply' (point cloud).
    Streams directly from the storage gateway without public URL exposure.
    """
    fmt_clean = fmt.lower().strip()
    if fmt_clean not in ("glb", "ply"):
        raise HTTPException(status_code=400, detail="Invalid format. Supported formats: 'glb', 'ply'")

    user_info = get_current_user_info(request)
    try:
        uuid.UUID(job_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="job_id must be a valid UUID.") from exc

    # Query photogrammetry service for job details
    try:
        res = requests.get(f"http://localhost:8004/status/job/{job_id}", timeout=10)
        if res.status_code == 404:
            raise HTTPException(status_code=404, detail="Photogrammetry reconstruction job was not found.")
        res.raise_for_status()
        job_data = res.json()
    except requests.RequestException as e:
        raise HTTPException(status_code=502, detail=f"Failed to communicate with photogrammetry server: {str(e)}")

    case_id = job_data.get("case_id")
    if not case_id:
        raise HTTPException(status_code=404, detail="Job record does not contain an associated case_id.")

    # Enforce case RBAC / assignment check
    check_case_access(case_id, user_info, db)

    model_target = job_data.get("model_url") if fmt_clean == "glb" else job_data.get("point_cloud_url")
    if not model_target or job_data.get("status") != "Completed":
        raise HTTPException(status_code=404, detail=f"Photogrammetry {fmt_clean.upper()} model is not available yet.")

    media_type = "model/gltf-binary" if fmt_clean == "glb" else "application/octet-stream"
    disposition = "attachment" if download else "inline"
    filename = f"{job_id}_model.{fmt_clean}"
    headers = {"Content-Disposition": f'{disposition}; filename="{filename}"'}

    # Stream from Storage Gateway (or fallback for legacy local/Supabase URLs)
    provider = get_storage_provider()
    stream = None
    target_str = str(model_target).strip()

    # 1. Canonical Storage Gateway key (models/...)
    if target_str.startswith("models/") or (not urlparse(target_str).scheme and "/uploads/" not in target_str):
        try:
            stream = provider.get(target_str)
        except KeyNotFoundError:
            # Earlier photogrammetry workers resolved a relative UPLOADS_DIR
            # from their own CWD and wrote to this legacy root.  Read it as a
            # fallback only; existing evidence is never moved or modified.
            legacy_root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "photogrammetry-backend", "uploads")
            try:
                stream = LocalStorageProvider(legacy_root).get(target_str)
                logger.info("Serving legacy photogrammetry artifact from %s", legacy_root)
            except KeyNotFoundError:
                raise HTTPException(status_code=404, detail=f"Model artifact '{target_str}' not found in storage.")
        except StorageUnavailableError as e:
            raise HTTPException(status_code=502, detail=f"Storage provider unreachable: {e}")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Storage error reading model: {e}")

    # 2. Local uploads
    elif "/uploads/" in target_str:
        local_path = resolve_upload_path(target_str)
        if not os.path.isfile(local_path):
            raise HTTPException(status_code=404, detail="Local model file not found.")
        stream = open(local_path, "rb")

    # 3. Remote URL fallback
    else:
        try:
            req_stream = requests.get(target_str, stream=True, timeout=(5, 60))
            if req_stream.status_code == 404:
                raise HTTPException(status_code=404, detail="Model file not found in remote storage.")
            req_stream.raise_for_status()
            stream = req_stream.raw
        except requests.RequestException as e:
            raise HTTPException(status_code=502, detail=f"Failed to fetch remote model file: {e}")

    write_audit_log(
        user_id=user_info["id"],
        action="Photogrammetry Model Downloaded" if download else "Photogrammetry Model Viewed",
        metadata={
            "job_id": job_id,
            "case_id": case_id,
            "format": fmt_clean,
            "download": download
        }
    )

    return StreamingResponse(stream, media_type=media_type, headers=headers)


def ensure_background_services():
    """Auto-detects and launches missing microservices (Ganache, BNS, Audio, Crime Detection, Photogrammetry, Frontend) if their ports are inactive."""
    if not os.environ.get("AUTO_SPAWN_MICROSERVICES", "True").lower() in ("true", "1", "yes"):
        return

    import socket
    import sys

    def is_port_in_use(port: int) -> bool:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.3)
            return s.connect_ex(("127.0.0.1", port)) == 0

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    def get_service_python(service_dir: str) -> str:
        venv_py = os.path.join(service_dir, "venv", "Scripts", "python.exe")
        if os.path.isfile(venv_py):
            return venv_py
        return sys.executable

    bns_dir = os.path.join(base_dir, "bns-backend")
    audio_dir = os.path.join(base_dir, "audio-backend")
    crime_dir = os.path.join(base_dir, "best")
    photo_dir = os.path.join(base_dir, "photogrammetry-backend")

    services_to_check = [
        ("Ganache Blockchain", 8545, ["npx", "ganache", "--server.host", "127.0.0.1", "--server.port", "8545", "--chain.chainId", "1337", "--wallet.deterministic", "--database.dbPath", "./ganache-data"], os.path.join(base_dir, "blockchain")),
        ("BNS ML Service", 8001, [get_service_python(bns_dir), "-m", "uvicorn", "app.main:app", "--port", "8001", "--reload"], bns_dir),
        ("Audio Forensics", 8002, [get_service_python(audio_dir), "app.py"], audio_dir),
        ("Object Detection (best)", 8003, [get_service_python(crime_dir), "main.py"], crime_dir),
        ("Photogrammetry", 8004, [get_service_python(photo_dir), "app.py"], photo_dir),
        ("React Frontend", 5173, ["npm", "run", "dev"], os.path.join(base_dir, "audit-frontend")),
    ]

    for name, port, cmd, cwd in services_to_check:
        if not is_port_in_use(port):
            print(f"[AUTO-LAUNCH] Port {port} ({name}) is inactive. Launching service...")
            try:
                is_shell = sys.platform == "win32" and (cmd[0] in ("npx", "npm"))
                subprocess.Popen(cmd, cwd=cwd, shell=is_shell)
                print(f"[AUTO-LAUNCH] Started {name} successfully.")
            except Exception as exc:
                print(f"[AUTO-LAUNCH] Failed to launch {name}: {exc}")


if __name__ == "__main__":
    import uvicorn
    ensure_background_services()
    uvicorn.run(app, host="0.0.0.0", port=8000)
