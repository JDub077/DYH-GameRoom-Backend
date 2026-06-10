import asyncio
import json
from typing import Dict, List
from fastapi import WebSocket


class RoomConnectionManager:
    """Manages WebSocket connections per room with optional Redis pub/sub."""

    def __init__(self):
        # room_id -> {user_id -> WebSocket}
        self._rooms: Dict[str, Dict[str, WebSocket]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, room_id: str, user_id: str, websocket: WebSocket):
        await websocket.accept()
        async with self._lock:
            if room_id not in self._rooms:
                self._rooms[room_id] = {}
            self._rooms[room_id][user_id] = websocket

    async def disconnect(self, room_id: str, user_id: str):
        async with self._lock:
            if room_id in self._rooms:
                self._rooms[room_id].pop(user_id, None)
                if not self._rooms[room_id]:
                    del self._rooms[room_id]

    async def broadcast(self, room_id: str, message: dict):
        """Broadcast a message to all connections in a room."""
        async with self._lock:
            connections = list(self._rooms.get(room_id, {}).values())
        dead = []
        for ws in connections:
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        # Clean up dead connections on next operation

    async def send_to_user(self, room_id: str, user_id: str, message: dict):
        async with self._lock:
            ws = self._rooms.get(room_id, {}).get(user_id)
        if ws:
            try:
                await ws.send_json(message)
            except Exception:
                pass

    def get_room_users(self, room_id: str) -> List[str]:
        return list(self._rooms.get(room_id, {}).keys())


# Global singleton instance
room_manager = RoomConnectionManager()
