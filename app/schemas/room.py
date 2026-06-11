from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel


class RoomPlayerOut(BaseModel):
    id: str
    user_id: str
    nickname: str
    character_id: Optional[str] = None
    character_name: Optional[str] = None
    is_host: bool
    is_ready: bool
    joined_at: datetime

    class Config:
        from_attributes = True


class RoomOut(BaseModel):
    id: str
    name: str
    code: str
    host_id: str
    status: str
    current_phase: str
    max_players: int
    players: List[RoomPlayerOut] = []
    created_at: datetime

    class Config:
        from_attributes = True


class RoomCreate(BaseModel):
    name: str
    password: Optional[str] = None
    host_id: str
    host_nickname: str


class RoomJoin(BaseModel):
    code: str
    password: Optional[str] = None
    user_id: str
    nickname: str


class ClueCreate(BaseModel):
    title: str
    content: str
    image_url: Optional[str] = None
    phase: str


class ClueOut(BaseModel):
    id: str
    title: str
    content: str
    image_url: Optional[str] = None
    phase: str
    is_issued: bool
    issued_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


class PhaseUpdate(BaseModel):
    phase: str


class RoleAssign(BaseModel):
    user_id: str
    character_id: str


class MyRoleOut(BaseModel):
    character_id: str
    character_name: str
    title: Optional[str] = None
    era: Optional[str] = None
    avatar_url: Optional[str] = None
    tagline: Optional[str] = None
    backstory: Optional[str] = None
    secrets: Optional[list] = None

    class Config:
        from_attributes = True


class RoomMessageOut(BaseModel):
    id: str
    sender_id: str
    sender_nickname: str
    sender_character_name: Optional[str] = None
    sender_avatar_url: Optional[str] = None
    content: str
    message_type: str
    created_at: datetime

    class Config:
        from_attributes = True
