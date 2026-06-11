from sqlalchemy import Column, String, Text, JSON
from app.core.database import Base


class Character(Base):
    __tablename__ = "characters"

    id = Column(String(32), primary_key=True)
    name = Column(String(64), nullable=False)
    title = Column(String(64))
    era = Column(String(32))
    avatar_url = Column(Text)
    tagline = Column(Text)
    tags = Column(JSON, default=list)
    backstory = Column(Text, nullable=True)
    system_prompt = Column(Text, nullable=False)
    few_shots = Column(JSON, default=list)
    knowledge_nodes = Column(JSON, default=list)
    secrets = Column(JSON, default=list)
    status = Column(String(16), default="active")
