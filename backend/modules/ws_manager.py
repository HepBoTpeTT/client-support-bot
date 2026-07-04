from typing import Any
from fastapi import WebSocket


class WebSocketManager:
    def __init__(self):
        # session_id -> список активных WS-соединений
        self._rooms: dict[str, list[WebSocket]] = {}

    async def join(self, session_id: str, ws: WebSocket):
        await ws.accept()
        self._rooms.setdefault(session_id, []).append(ws)

    def leave(self, session_id: str, ws: WebSocket):
        room = self._rooms.get(session_id, [])
        if ws in room:
            room.remove(ws)
        if not room:
            self._rooms.pop(session_id, None)

    async def send_to_room(self, session_id: str, data: Any):
        """Отправить JSON всем участникам комнаты."""
        room = self._rooms.get(session_id, [])
        dead = []
        for ws in list(room):
            try:
                await ws.send_json(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.leave(session_id, ws)

    def room_size(self, session_id: str) -> int:
        return len(self._rooms.get(session_id, []))


ws_manager = WebSocketManager()