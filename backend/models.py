import uuid
from sqlalchemy import Column, String, Date, Time, DateTime, ForeignKey, BigInteger, Float, Integer, Boolean
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from db import Base

class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True)
    email = Column(String, nullable=False, unique=True)
    full_name = Column(String, nullable=False)
    role = Column(String, nullable=False)
    department = Column(String, nullable=True)
    badge_number = Column(String, nullable=True)
    clearance_level = Column(Integer, server_default="1", default=1)
    is_active = Column(Boolean, server_default="true", default=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    can_create_case = Column(Boolean, server_default="true", default=True)
    last_login = Column(DateTime(timezone=True), nullable=True)



class Case(Base):
    __tablename__ = "cases"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String, nullable=False)
    offence_type = Column(String, nullable=False)
    fir_description = Column(String, nullable=True)
    fir_language = Column(String, server_default="en", default="en")
    complainant_name = Column(String, nullable=True)
    complainant_contact = Column(String, nullable=True)
    victims = Column(JSONB, nullable=True)
    suspects = Column(JSONB, nullable=True)
    incident_date = Column(Date, nullable=True)
    incident_time = Column(Time, nullable=True)
    incident_location = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    case_number = Column(String, unique=True, nullable=True)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_by_name = Column(String, nullable=True)


class Evidence(Base):
    __tablename__ = "evidence"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    case_id = Column(UUID(as_uuid=True), ForeignKey("cases.id", ondelete="CASCADE"), nullable=True)
    evidence_type = Column(String, nullable=False)
    description = Column(String, nullable=True)
    file_url = Column(String, nullable=False)
    file_hash = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    file_name = Column(String, nullable=True)
    file_size = Column(BigInteger, nullable=True)
    mime_type = Column(String, nullable=True)
    uploaded_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    uploaded_by_name = Column(String, nullable=True)
    verified_at = Column(DateTime(timezone=True), nullable=True)
    verified_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    chain_of_custody_status = Column(String, server_default="Collected", default="Collected")
    status = Column(String, server_default="Verified", default="Verified")
    blockchain_tx_hash = Column(String, unique=True, nullable=True)
    blockchain_block_number = Column(BigInteger, nullable=True)
    blockchain_contract_address = Column(String, nullable=True)
    blockchain_gas_used = Column(BigInteger, nullable=True)
    blockchain_registered_at = Column(DateTime(timezone=True), nullable=True)
    latest_verification_at = Column(DateTime(timezone=True), nullable=True)
    # Receipt metadata captured at registration (added by migrate_blockchain.py).
    blockchain_block_hash = Column(String, nullable=True)
    blockchain_wallet_address = Column(String, nullable=True)
    blockchain_chain_id = Column(BigInteger, nullable=True)
    blockchain_tx_status = Column(String, nullable=True)
    # Outcome of the most recent verification attempt. Unlike ``status`` this may be
    # "Verification Failed" (an outage), which says nothing about the evidence itself.
    last_verification_result = Column(String, nullable=True)
    last_verification_reason = Column(String, nullable=True)


class EvidenceCustodyRecord(Base):
    __tablename__ = "evidence_custody_records"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    evidence_id = Column(UUID(as_uuid=True), ForeignKey("evidence.id", ondelete="CASCADE"), nullable=False, index=True)
    officer_id = Column(String, nullable=False)
    action = Column(String, nullable=False)
    occurred_at = Column(DateTime(timezone=True), nullable=False)
    transaction_hash = Column(String, nullable=True, unique=True)
    block_number = Column(BigInteger, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    # "blockchain" for entries mirrored from the contract, "database" for off-chain
    # custody events (created, viewed, downloaded, metadata modified).
    source = Column(String, nullable=True, server_default="blockchain", default="blockchain")
    details = Column(JSONB, nullable=True)


class BlockchainLog(Base):
    __tablename__ = "blockchain_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    evidence_id = Column(UUID(as_uuid=True), ForeignKey("evidence.id", ondelete="CASCADE"), nullable=True)
    event_name = Column(String, nullable=False)
    transaction_hash = Column(String, nullable=True, index=True)
    block_number = Column(BigInteger, nullable=True)
    payload = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(String, nullable=True)
    action = Column(String, nullable=False)
    case_id = Column(UUID(as_uuid=True), ForeignKey("cases.id", ondelete="CASCADE"), nullable=True)
    file_hash = Column(String, nullable=True)
    metadata_ = Column("metadata", JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class OCRResult(Base):
    __tablename__ = "ocr_results"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    evidence_id = Column(UUID(as_uuid=True), ForeignKey("evidence.id", ondelete="CASCADE"), nullable=True)
    extracted_text = Column(String, nullable=False)
    language = Column(String, nullable=False)
    confidence = Column(Float, nullable=True)
    page_number = Column(Integer, nullable=False, server_default="1", default=1)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    # [{"code": "hi", "name": "Hindi", "ratio": 0.8, "char_count": 412}, ...]
    detected_languages = Column(JSONB, nullable=True)
    # Page-level extraction details: status, warnings, tables, line boxes,
    # preprocessing steps, requested languages and processing time.
    ocr_metadata = Column(JSONB, nullable=True)


class BNSPrediction(Base):
    __tablename__ = "bns_predictions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    case_id = Column(UUID(as_uuid=True), ForeignKey("cases.id", ondelete="CASCADE"), nullable=False)
    crime_type = Column(String, nullable=False)
    sections = Column(JSONB, nullable=False)
    fir_text = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class OTPToken(Base):
    __tablename__ = "otp_tokens"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    token = Column(String, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    used = Column(Boolean, server_default="false", default=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class Detection(Base):
    __tablename__ = "detections"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    case_id = Column(UUID(as_uuid=True), ForeignKey("cases.id", ondelete="CASCADE"), nullable=True)
    evidence_id = Column(UUID(as_uuid=True), ForeignKey("evidence.id", ondelete="CASCADE"), nullable=True)
    image_url = Column(String, nullable=True)
    predictions = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

