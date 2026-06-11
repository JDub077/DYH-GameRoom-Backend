import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey, Boolean, Text, Integer
from app.core.database import Base, GUID


class Room(Base):
    __tablename__ = "rooms"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    name = Column(String(128), nullable=False)
    code = Column(String(6), unique=True, nullable=False)
    password = Column(String(64), nullable=True)
    host_id = Column(String(64), nullable=False)
    status = Column(String(16), default="waiting")  # waiting, playing, ended
    current_phase = Column(String(32), default="waiting")
    max_players = Column(Integer, default=6)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class RoomPlayer(Base):
    __tablename__ = "room_players"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    room_id = Column(GUID(), ForeignKey("rooms.id"), nullable=False)
    user_id = Column(String(64), nullable=False)
    nickname = Column(String(64), nullable=False)
    character_id = Column(String(32), ForeignKey("characters.id"), nullable=True)
    is_host = Column(Boolean, default=False)
    is_ready = Column(Boolean, default=False)
    joined_at = Column(DateTime, default=datetime.now)
    last_seen_at = Column(DateTime, default=datetime.now)


class Clue(Base):
    __tablename__ = "clues"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    room_id = Column(GUID(), ForeignKey("rooms.id"), nullable=False)
    title = Column(String(128), nullable=False)
    content = Column(Text, nullable=False)
    image_url = Column(Text, nullable=True)
    phase = Column(String(32), nullable=False)
    is_issued = Column(Boolean, default=False)
    issued_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.now)


class RoomMessage(Base):
    __tablename__ = "room_messages"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    room_id = Column(GUID(), ForeignKey("rooms.id"), nullable=False)
    sender_id = Column(String(64), nullable=False)
    sender_nickname = Column(String(64), nullable=False)
    sender_character_name = Column(String(64), nullable=True)
    sender_avatar_url = Column(Text, nullable=True)
    content = Column(Text, nullable=False)
    message_type = Column(String(16), default="text")  # text, system, phase_change, clue_issued
    created_at = Column(DateTime, default=datetime.now)
