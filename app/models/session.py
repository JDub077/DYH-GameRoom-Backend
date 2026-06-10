import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey
from app.core.database import Base, GUID


class Session(Base):
    __tablename__ = "sessions"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    character_id = Column(String(32), ForeignKey("characters.id"), nullable=False)
    user_id = Column(String(64), nullable=False, default="anonymous")
    room_id = Column(GUID(), ForeignKey("rooms.id"), nullable=True)
    context_type = Column(String(16), default="solo")  # solo, room
    status = Column(String(16), default="active")
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
