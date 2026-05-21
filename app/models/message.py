import uuid
from datetime import datetime
from sqlalchemy import Column, String, Text, DateTime, ForeignKey, JSON
from app.core.database import Base
from app.models.session import GUID


class Message(Base):
    __tablename__ = "messages"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    session_id = Column(GUID(), ForeignKey("sessions.id"), nullable=False)
    role = Column(String(16), nullable=False)
    content = Column(Text, nullable=False)
    emotion_tag = Column(String(32))
    extra = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.now)
