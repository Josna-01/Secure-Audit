import uuid
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from db import Base

class PhotogrammetryModel(Base):
    __tablename__ = "photogrammetry_models"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    case_id = Column(UUID(as_uuid=True), nullable=True)
    evidence_id = Column(UUID(as_uuid=True), nullable=True)
    model_url = Column(String, nullable=True)
    point_cloud_url = Column(String, nullable=True)
    status = Column(String, server_default="Pending", default="Pending")
    frame_count = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)
    error_message = Column(String, nullable=True)
