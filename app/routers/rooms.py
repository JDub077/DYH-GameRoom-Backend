import random
import string
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from app.core.database import get_db
from app.models.room import Room, RoomPlayer, Clue, RoomMessage
from app.models.character import Character
from app.services.room_manager import room_manager
from app.schemas.room import (
    RoomCreate,
    RoomOut,
    RoomJoin,
    ClueCreate,
    ClueOut,
    PhaseUpdate,
    RoleAssign,
    RoomMessageOut,
    MyRoleOut,
)

router = APIRouter()


def _generate_room_code(db: Session, length: int = 6) -> str:
    while True:
        code = "".join(random.choices(string.ascii_uppercase + string.digits, k=length))
        if not db.query(Room).filter(Room.code == code).first():
            return code


def _room_to_out(room: Room, db: Session) -> RoomOut:
    players = db.query(RoomPlayer).filter(RoomPlayer.room_id == room.id).all()
    player_outs = []
    for p in players:
        char_name = None
        if p.character_id:
            char = db.query(Character).filter(Character.id == p.character_id).first()
            char_name = char.name if char else None
        player_outs.append({
            "id": str(p.id),
            "user_id": p.user_id,
            "nickname": p.nickname,
            "character_id": p.character_id,
            "character_name": char_name,
            "is_host": p.is_host,
            "is_ready": p.is_ready,
            "joined_at": p.joined_at,
        })
    return RoomOut(
        id=str(room.id),
        name=room.name,
        code=room.code,
        host_id=room.host_id,
        status=room.status,
        current_phase=room.current_phase,
        max_players=room.max_players,
        players=player_outs,
        created_at=room.created_at,
    )


@router.post("/rooms", response_model=RoomOut)
def create_room(data: RoomCreate, db: Session = Depends(get_db)):
    code = _generate_room_code(db)
    room = Room(
        name=data.name,
        code=code,
        password=data.password,
        host_id=data.host_id,
    )
    db.add(room)
    db.commit()
    db.refresh(room)

    host = RoomPlayer(
        room_id=room.id,
        user_id=data.host_id,
        nickname=data.host_nickname,
        is_host=True,
    )
    db.add(host)
    db.commit()

    return _room_to_out(room, db)


@router.get("/rooms", response_model=list[RoomOut])
def list_rooms(db: Session = Depends(get_db)):
    rooms = db.query(Room).filter(Room.status == "waiting").all()
    return [_room_to_out(r, db) for r in rooms]


@router.get("/rooms/{room_id}", response_model=RoomOut)
def get_room(room_id: str, db: Session = Depends(get_db)):
    room = db.query(Room).filter(Room.id == room_id).first()
    if not room:
        raise HTTPException(status_code=404, detail="房间不存在")
    return _room_to_out(room, db)


@router.post("/rooms/join", response_model=RoomOut)
def join_room(data: RoomJoin, db: Session = Depends(get_db)):
    room = db.query(Room).filter(Room.code == data.code).first()
    if not room:
        raise HTTPException(status_code=404, detail="房间不存在")
    if room.status != "waiting":
        raise HTTPException(status_code=400, detail="房间已开始或已结束")
    if room.password and room.password != data.password:
        raise HTTPException(status_code=403, detail="房间密码错误")

    existing = db.query(RoomPlayer).filter(
        RoomPlayer.room_id == room.id,
        RoomPlayer.user_id == data.user_id,
    ).first()
    if existing:
        return _room_to_out(room, db)

    player_count = db.query(RoomPlayer).filter(RoomPlayer.room_id == room.id).count()
    if player_count >= room.max_players:
        raise HTTPException(status_code=400, detail="房间已满")

    player = RoomPlayer(
        room_id=room.id,
        user_id=data.user_id,
        nickname=data.nickname,
    )
    db.add(player)
    db.commit()

    return _room_to_out(room, db)


@router.post("/rooms/{room_id}/leave")
def leave_room(room_id: str, user_id: str, db: Session = Depends(get_db)):
    player = db.query(RoomPlayer).filter(
        RoomPlayer.room_id == room_id,
        RoomPlayer.user_id == user_id,
    ).first()
    if not player:
        raise HTTPException(status_code=404, detail="不在房间中")

    is_host = player.is_host
    db.delete(player)
    db.commit()

    remaining = db.query(RoomPlayer).filter(RoomPlayer.room_id == room_id).count()
    if remaining == 0:
        db.query(Room).filter(Room.id == room_id).delete()
        db.commit()
    elif is_host:
        # Promote oldest player to host
        new_host = db.query(RoomPlayer).filter(
            RoomPlayer.room_id == room_id,
        ).order_by(RoomPlayer.joined_at.asc()).first()
        if new_host:
            new_host.is_host = True
            room = db.query(Room).filter(Room.id == room_id).first()
            room.host_id = new_host.user_id
            db.commit()

    return {"code": 0, "message": "success"}


@router.patch("/rooms/{room_id}/phase", response_model=RoomOut)
def update_phase(room_id: str, user_id: str, data: PhaseUpdate, db: Session = Depends(get_db)):
    room = db.query(Room).filter(Room.id == room_id).first()
    if not room:
        raise HTTPException(status_code=404, detail="房间不存在")
    if room.host_id != user_id:
        raise HTTPException(status_code=403, detail="只有主持人可以切换阶段")

    room.current_phase = data.phase
    if data.phase == "opening":
        room.status = "playing"
    db.commit()
    db.refresh(room)
    return _room_to_out(room, db)


@router.post("/rooms/{room_id}/clues", response_model=ClueOut)
def create_clue(room_id: str, user_id: str, data: ClueCreate, db: Session = Depends(get_db)):
    room = db.query(Room).filter(Room.id == room_id).first()
    if not room:
        raise HTTPException(status_code=404, detail="房间不存在")
    if room.host_id != user_id:
        raise HTTPException(status_code=403, detail="只有主持人可以创建线索")

    clue = Clue(
        room_id=room_id,
        title=data.title,
        content=data.content,
        image_url=data.image_url,
        phase=data.phase,
    )
    db.add(clue)
    db.commit()
    db.refresh(clue)
    return ClueOut(
        id=str(clue.id),
        title=clue.title,
        content=clue.content,
        image_url=clue.image_url,
        phase=clue.phase,
        is_issued=clue.is_issued,
        issued_at=clue.issued_at,
        created_at=clue.created_at,
    )


@router.get("/rooms/{room_id}/clues", response_model=list[ClueOut])
def list_clues(room_id: str, db: Session = Depends(get_db)):
    clues = db.query(Clue).filter(Clue.room_id == room_id).all()
    return [
        ClueOut(
            id=str(c.id),
            title=c.title,
            content=c.content,
            image_url=c.image_url,
            phase=c.phase,
            is_issued=c.is_issued,
            issued_at=c.issued_at,
            created_at=c.created_at,
        )
        for c in clues
    ]


@router.post("/rooms/{room_id}/clues/{clue_id}/issue")
def issue_clue(room_id: str, clue_id: str, user_id: str, db: Session = Depends(get_db)):
    room = db.query(Room).filter(Room.id == room_id).first()
    if not room or room.host_id != user_id:
        raise HTTPException(status_code=403, detail="权限不足")

    clue = db.query(Clue).filter(Clue.id == clue_id, Clue.room_id == room_id).first()
    if not clue:
        raise HTTPException(status_code=404, detail="线索不存在")

    clue.is_issued = True
    clue.issued_at = datetime.now()
    db.commit()
    db.refresh(clue)
    return ClueOut(
        id=str(clue.id),
        title=clue.title,
        content=clue.content,
        image_url=clue.image_url,
        phase=clue.phase,
        is_issued=clue.is_issued,
        issued_at=clue.issued_at,
        created_at=clue.created_at,
    )


@router.post("/rooms/{room_id}/assign-role", response_model=RoomOut)
def assign_role(room_id: str, user_id: str, data: RoleAssign, db: Session = Depends(get_db)):
    room = db.query(Room).filter(Room.id == room_id).first()
    if not room:
        raise HTTPException(status_code=404, detail="房间不存在")
    if room.host_id != user_id:
        raise HTTPException(status_code=403, detail="只有主持人可以分配角色")

    player = db.query(RoomPlayer).filter(
        RoomPlayer.room_id == room_id,
        RoomPlayer.user_id == data.user_id,
    ).first()
    if not player:
        raise HTTPException(status_code=404, detail="玩家不在房间中")

    # Check character is not already assigned
    existing = db.query(RoomPlayer).filter(
        RoomPlayer.room_id == room_id,
        RoomPlayer.character_id == data.character_id,
    ).first()
    if existing and existing.user_id != data.user_id:
        raise HTTPException(status_code=400, detail="该角色已被分配")

    player.character_id = data.character_id
    db.commit()
    return _room_to_out(room, db)


@router.get("/rooms/{room_id}/messages", response_model=list[RoomMessageOut])
def get_messages(room_id: str, limit: int = 100, db: Session = Depends(get_db)):
    msgs = (
        db.query(RoomMessage)
        .filter(RoomMessage.room_id == room_id)
        .order_by(RoomMessage.created_at.desc())
        .limit(limit)
        .all()
    )
    return [
        RoomMessageOut(
            id=str(m.id),
            sender_id=m.sender_id,
            sender_nickname=m.sender_nickname,
            sender_character_name=m.sender_character_name,
            sender_avatar_url=m.sender_avatar_url,
            content=m.content,
            message_type=m.message_type,
            created_at=m.created_at,
        )
        for m in reversed(msgs)
    ]


@router.post("/rooms/{room_id}/ready")
def player_ready(room_id: str, user_id: str, db: Session = Depends(get_db)):
    player = db.query(RoomPlayer).filter(
        RoomPlayer.room_id == room_id,
        RoomPlayer.user_id == user_id,
    ).first()
    if not player:
        raise HTTPException(status_code=404, detail="玩家不在房间中")
    player.is_ready = not player.is_ready
    db.commit()
    room = db.query(Room).filter(Room.id == room_id).first()
    return _room_to_out(room, db)


@router.post("/rooms/{room_id}/start-game", response_model=RoomOut)
def start_game(room_id: str, user_id: str, db: Session = Depends(get_db)):
    room = db.query(Room).filter(Room.id == room_id).first()
    if not room:
        raise HTTPException(status_code=404, detail="房间不存在")
    if room.host_id != user_id:
        raise HTTPException(status_code=403, detail="只有主持人可以开始游戏")

    players = db.query(RoomPlayer).filter(RoomPlayer.room_id == room_id).all()
    non_host_players = [p for p in players if not p.is_host]

    if not non_host_players:
        raise HTTPException(status_code=400, detail="房间内没有其他玩家")

    characters = db.query(Character).filter(Character.status == "active").all()
    if len(characters) < len(non_host_players):
        raise HTTPException(status_code=400, detail=f"可用角色不足，需要 {len(non_host_players)} 个，当前只有 {len(characters)} 个")

    # Randomly assign characters
    assigned_chars = random.sample(characters, len(non_host_players))
    for player, char in zip(non_host_players, assigned_chars):
        player.character_id = char.id
        player.is_ready = False  # Reset ready for role reveal
    db.commit()

    # Update room phase
    room.current_phase = "role_reveal"
    room.status = "playing"
    db.commit()
    db.refresh(room)

    # System message
    sys_msg = RoomMessage(
        room_id=room_id,
        sender_id="system",
        sender_nickname="系统",
        content="游戏开始！请各位玩家查看自己的角色剧本。",
        message_type="system",
    )
    db.add(sys_msg)
    db.commit()

    # Broadcast role assignment to all connected players
    room_out = _room_to_out(room, db)
    import asyncio
    asyncio.create_task(room_manager.broadcast(room_id, {
        "event": "roles_assigned",
        "payload": {
            "players": room_out.players,
            "phase": room.current_phase,
            "system_message": {
                "id": str(sys_msg.id),
                "sender_id": sys_msg.sender_id,
                "sender_nickname": sys_msg.sender_nickname,
                "content": sys_msg.content,
                "message_type": sys_msg.message_type,
                "created_at": sys_msg.created_at.isoformat() if sys_msg.created_at else None,
            },
        },
        "timestamp": int(datetime.now().timestamp()),
    }))

    return room_out


@router.get("/rooms/{room_id}/my-role", response_model=MyRoleOut)
def get_my_role(room_id: str, user_id: str, db: Session = Depends(get_db)):
    player = db.query(RoomPlayer).filter(
        RoomPlayer.room_id == room_id,
        RoomPlayer.user_id == user_id,
    ).first()
    if not player:
        raise HTTPException(status_code=404, detail="玩家不在房间中")
    if not player.character_id:
        raise HTTPException(status_code=400, detail="你还没有被分配角色")

    char = db.query(Character).filter(Character.id == player.character_id).first()
    if not char:
        raise HTTPException(status_code=404, detail="角色不存在")

    return MyRoleOut(
        character_id=char.id,
        character_name=char.name,
        title=char.title,
        era=char.era,
        avatar_url=char.avatar_url,
        tagline=char.tagline,
        backstory=char.backstory,
        secrets=char.secrets,
    )
