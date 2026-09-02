"""In-memory WebSocket hub for IM realtime push."""
import asyncio
import json
from typing import Dict, Set
from fastapi import WebSocket


class ConnectionManager:
    def __init__(self):
        # user_id -> set of websockets
        self._connections: Dict[str, Set[WebSocket]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, user_id: str, websocket: WebSocket):
        await websocket.accept()
        async with self._lock:
            self._connections.setdefault(user_id, set()).add(websocket)

    async def disconnect(self, user_id: str, websocket: WebSocket):
        async with self._lock:
            conns = self._connections.get(user_id)
            if conns:
                conns.discard(websocket)
                if not conns:
                    self._connections.pop(user_id, None)

    async def send_to_user(self, user_id: str, event: dict):
        async with self._lock:
            conns = list(self._connections.get(user_id, set()))
        dead = []
        data = json.dumps(event, ensure_ascii=False, default=str)
        for ws in conns:
            try:
                await ws.send_text(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            await self.disconnect(user_id, ws)

    async def broadcast_to_users(self, user_ids: list, event: dict):
        for uid in set(user_ids):
            await self.send_to_user(uid, event)


ws_manager = ConnectionManager()
