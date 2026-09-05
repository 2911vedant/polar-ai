"""
POLAR-AI Base Models
Common timestamp mixin and base class.
"""
from sqlalchemy import Column, DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID
import uuid
from app.database import Base


class TimestampMixin:
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class UUIDMixin:
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


class SystemEvent(Base, UUIDMixin, TimestampMixin):
    """Audit log for significant system events."""
    __tablename__ = "system_events"

    event_type = Column(String(100), nullable=False)
    message = Column(String(500))
    severity = Column(String(20), default="info")  # info | warning | error
    source = Column(String(100))
    data = Column(String(2000))  # JSON string
