import json
from datetime import datetime
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.room import Room, RoomPlayer, RoomMessage, Clue
from app.services.room_manager import room_manager

router = APIRouter()


async def _build_room_state(room_id: str, db: Session):
    """Build full room state snapshot for reconnection."""
    room = db.query(Room).filter(Room.id == room_id).first()
    if not room:
        return None

    players = db.query(RoomPlayer).filter(RoomPlayer.room_id == room_id).all()
    player_outs = []
    for p in players:
        from app.models.character import Character
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
            "joined_at": p.joined_at.isoformat() if p.joined_at else None,
        })

    clues = db.query(Clue).filter(Clue.room_id == room_id).all()
    clue_outs = []
    for c in clues:
        clue_outs.append({
            "id": str(c.id),
            "title": c.title,
            "content": c.content,
            "image_url": c.image_url,
            "phase": c.phase,
            "is_issued": c.is_issued,
            "issued_at": c.issued_at.isoformat() if c.issued_at else None,
            "created_at": c.created_at.isoformat() if c.created_at else None,
        })

    messages = (
        db.query(RoomMessage)
        .filter(RoomMessage.room_id == room_id)
        .order_by(RoomMessage.created_at.asc())
        .limit(200)
        .all()
    )
    msg_outs = []
    for m in messages:
        msg_outs.append({
            "id": str(m.id),
            "sender_id": m.sender_id,
            "sender_nickname": m.sender_nickname,
            "content": m.content,
            "message_type": m.message_type,
            "created_at": m.created_at.isoformat() if m.created_at else None,
        })

    return {
        "room": {
            "id": str(room.id),
            "name": room.name,
            "code": room.code,
            "host_id": room.host_id,
            "status": room.status,
            "current_phase": room.current_phase,
            "max_players": room.max_players,
            "created_at": room.created_at.isoformat() if room.created_at else None,
        },
        "players": player_outs,
        "clues": clue_outs,
        "messages": msg_outs,
        "current_phase": room.current_phase,
    }


@router.websocket("/ws/rooms/{room_id}")
async def room_websocket(websocket: WebSocket, room_id: str, db: Session = Depends(get_db)):
    params = websocket.query_params
    user_id = params.get("user_id")
    nickname = params.get("nickname", "匿名")

    if not user_id:
        await websocket.close(code=4001, reason="missing user_id")
        return

    # Verify player is in room
    player = db.query(RoomPlayer).filter(
        RoomPlayer.room_id == room_id,
        RoomPlayer.user_id == user_id,
    ).first()
    if not player:
        await websocket.close(code=4002, reason="not in room")
        return

    await room_manager.connect(room_id, user_id, websocket)

    # Update last_seen
    player.last_seen_at = datetime.now()
    db.commit()

    # Send full room state to the joining client
    state = await _build_room_state(room_id, db)
    if state:
        await websocket.send_json({
            "event": "room_state",
            "payload": state,
            "timestamp": int(datetime.now().timestamp()),
        })

    # Broadcast player joined
    from app.models.character import Character
    char_name = None
    if player.character_id:
        char = db.query(Character).filter(Character.id == player.character_id).first()
        char_name = char.name if char else None

    await room_manager.broadcast(room_id, {
        "event": "player_joined",
        "payload": {
            "player": {
                "id": str(player.id),
                "user_id": player.user_id,
                "nickname": player.nickname,
                "character_id": player.character_id,
                "character_name": char_name,
                "is_host": player.is_host,
                "is_ready": player.is_ready,
                "joined_at": player.joined_at.isoformat() if player.joined_at else None,
            },
        },
        "timestamp": int(datetime.now().timestamp()),
    })

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                continue

            event = data.get("event")
            payload = data.get("payload", {})

            if event == "ping":
                await websocket.send_json({
                    "event": "pong",
                    "payload": {},
                    "timestamp": int(datetime.now().timestamp()),
                })
                continue

            if event == "chat":
                content = payload.get("content", "").strip()
                if not content:
                    continue
                msg = RoomMessage(
                    room_id=room_id,
                    sender_id=user_id,
                    sender_nickname=player.nickname,
                    content=content,
                    message_type="text",
                )
                db.add(msg)
                db.commit()
                db.refresh(msg)

                await room_manager.broadcast(room_id, {
                    "event": "chat",
                    "payload": {
                        "message": {
                            "id": str(msg.id),
                            "sender_id": msg.sender_id,
                            "sender_nickname": msg.sender_nickname,
                            "content": msg.content,
                            "message_type": msg.message_type,
                            "created_at": msg.created_at.isoformat() if msg.created_at else None,
                        },
                    },
                    "timestamp": int(datetime.now().timestamp()),
                })

            elif event == "ready":
                player.is_ready = not player.is_ready
                db.commit()
                await room_manager.broadcast(room_id, {
                    "event": "player_ready",
                    "payload": {
                        "user_id": user_id,
                        "is_ready": player.is_ready,
                    },
                    "timestamp": int(datetime.now().timestamp()),
                })

            elif event == "phase_change":
                if not player.is_host:
                    await websocket.send_json({
                        "event": "error",
                        "payload": {"code": "NOT_HOST", "message": "只有主持人可以切换阶段"},
                        "timestamp": int(datetime.now().timestamp()),
                    })
                    continue

                new_phase = payload.get("phase", "")
                room = db.query(Room).filter(Room.id == room_id).first()
                if room:
                    room.current_phase = new_phase
                    if new_phase == "opening":
                        room.status = "playing"
                    db.commit()

                    # System message for phase change
                    phase_labels = {
                        "waiting": "等待中",
                        "opening": "游戏开始",
                        "search_1": "第一轮搜证",
                        "discuss_1": "第一轮讨论",
                        "search_2": "第二轮搜证",
                        "discuss_2": "第二轮讨论",
                        "final": "最终讨论",
                        "closed": "游戏结束",
                    }
                    label = phase_labels.get(new_phase, new_phase)
                    sys_msg = RoomMessage(
                        room_id=room_id,
                        sender_id="system",
                        sender_nickname="系统",
                        content=f"阶段变更：{label}",
                        message_type="phase_change",
                    )
                    db.add(sys_msg)
                    db.commit()

                    await room_manager.broadcast(room_id, {
                        "event": "phase_changed",
                        "payload": {
                            "phase": new_phase,
                            "label": label,
                            "changed_by": user_id,
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
                    })

            elif event == "issue_clue":
                if not player.is_host:
                    await websocket.send_json({
                        "event": "error",
                        "payload": {"code": "NOT_HOST", "message": "只有主持人可以发放线索"},
                        "timestamp": int(datetime.now().timestamp()),
                    })
                    continue

                clue_id = payload.get("clue_id", "")
                clue = db.query(Clue).filter(Clue.id == clue_id, Clue.room_id == room_id).first()
                if clue and not clue.is_issued:
                    clue.is_issued = True
                    clue.issued_at = datetime.now()
                    db.commit()

                    sys_msg = RoomMessage(
                        room_id=room_id,
                        sender_id="system",
                        sender_nickname="系统",
                        content=f"新线索：{clue.title}",
                        message_type="clue_issued",
                    )
                    db.add(sys_msg)
                    db.commit()

                    await room_manager.broadcast(room_id, {
                        "event": "clue_issued",
                        "payload": {
                            "clue": {
                                "id": str(clue.id),
                                "title": clue.title,
                                "content": clue.content,
                                "image_url": clue.image_url,
                                "phase": clue.phase,
                                "is_issued": clue.is_issued,
                                "issued_at": clue.issued_at.isoformat() if clue.issued_at else None,
                                "created_at": clue.created_at.isoformat() if clue.created_at else None,
                            },
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
                    })

    except WebSocketDisconnect:
        await room_manager.disconnect(room_id, user_id)
        await room_manager.broadcast(room_id, {
            "event": "player_left",
            "payload": {"user_id": user_id},
            "timestamp": int(datetime.now().timestamp()),
        })
