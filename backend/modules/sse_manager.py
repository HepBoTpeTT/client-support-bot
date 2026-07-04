import asyncio
import json
from typing import Any

class SSEManager:
    def __init__(self):
        self._queues: list[asyncio.Queue] = []

    def _make_event(self, event: str, data: Any) -> str:
        payload = json.dumps(data, ensure_ascii=False)
        return f"event: {event}\ndata: {payload}\n\n"

    async def subscribe(self):
        """Генератор для EventSourceResponse."""
        q: asyncio.Queue = asyncio.Queue()
        self._queues.append(q)
        try:
            # первый пинг — клиент сразу знает что соединение живое
            yield {"event": "connected", "data": "ok"}
            while True:
                msg = await q.get()
                yield msg
        finally:
            self._queues.remove(q)

    async def broadcast(self, event: str, data: Any = None):
        """Рассылает событие всем подключённым SSE-клиентам."""
        msg = {"event": event, "data": json.dumps(data, ensure_ascii=False)}
        for q in list(self._queues):
            await q.put(msg)


sse_manager = SSEManager()