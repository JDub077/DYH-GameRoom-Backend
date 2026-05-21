import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.types import TypeDecorator, CHAR
from app.core.database import Base


class GUID(TypeDecorator):
    """Platform-independent GUID type. Uses PostgreSQL UUID or CHAR(32)."""
    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PGUUID(as_uuid=True))
        else:
            return dialect.type_descriptor(CHAR(32))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        elif dialect.name == "postgresql":
            return str(value)
        else:
            if not isinstance(value, uuid.UUID):
                return str(uuid.UUID(value))
            else:
                return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        else:
            if not isinstance(value, uuid.UUID):
                value = uuid.UUID(value)
            return value


class Session(Base):
    __tablename__ = "sessions"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    character_id = Column(String(32), ForeignKey("characters.id"), nullable=False)
    user_id = Column(String(64), nullable=False, default="anonymous")
    status = Column(String(16), default="active")
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
