import os
from contextlib import asynccontextmanager

import yaml
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.database import engine, Base, SessionLocal
from app.routers import characters, sessions, chat
from app.models.character import Character


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: 创建表 + 初始化角色数据
    Base.metadata.create_all(bind=engine)
    init_characters()
    yield
    # Shutdown


def init_characters():
    db = SessionLocal()
    try:
        existing = db.query(Character).count()
        if existing > 0:
            return

        prompts_dir = os.path.join(os.path.dirname(__file__), "prompts")
        characters_data = []

        for filename in sorted(os.listdir(prompts_dir)):
            if not filename.endswith(".yaml"):
                continue
            filepath = os.path.join(prompts_dir, filename)
            with open(filepath, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)

            characters_data.append({
                "id": data.get("id", ""),
                "name": data.get("name", ""),
                "title": data.get("title", ""),
                "era": data.get("era", "永乐十九年"),
                "avatar_url": data.get("avatar_url", ""),
                "tagline": data.get("tagline", ""),
                "tags": data.get("tags", []),
                "system_prompt": data.get("system_prompt", ""),
                "few_shots": data.get("few_shots", []),
                "knowledge_nodes": data.get("knowledge_nodes", []),
                "secrets": data.get("secrets", []),
            })

        for c in characters_data:
            db.add(Character(**c))
        db.commit()
    finally:
        db.close()


app = FastAPI(
    title="明舟北渡 · 角色智能体 API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(characters.router, prefix="/api/v1")
app.include_router(sessions.router, prefix="/api/v1")
app.include_router(chat.router, prefix="/api/v1")


@app.get("/health")
def health_check():
    return {"status": "ok"}
