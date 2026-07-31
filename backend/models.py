import uuid
from sqlalchemy import Column, String, Date, Time, DateTime, ForeignKey, BigInteger, Float, Integer
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from db import Base

class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True)


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


