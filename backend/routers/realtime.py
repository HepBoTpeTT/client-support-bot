import asyncio

from fastapi import APIRouter, Request, WebSocket
from sse_starlette.sse import EventSourceResponse

from modules.sse_manager import sse_manager
from modules.ws_manager import ws_manager

router = APIRouter(tags=["realtime"])


@router.get("/api/admin/stream")
async def admin_sse_stream(request: Request):
    async def event_generator():
        async for msg in sse_manager.subscribe():
            if await request.is_disconnected():
                break
            yield msg
    return EventSourceResponse(event_generator())


@router.websocket("/ws/chat/{session_id}")
async def ws_chat(websocket: WebSocket, session_id: str):
    await ws_manager.join(session_id, websocket)
    try:
        while True:
            await asyncio.sleep(30)
    except Exception:
        pass
    finally:
        ws_manager.leave(session_id, websocket)
