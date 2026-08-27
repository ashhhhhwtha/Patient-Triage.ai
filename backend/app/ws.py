"""WebSocket hub: every connected screen (queue board, nurse, doctor, patient phone)
gets an event whenever anything changes, so all views update live without refresh."""
import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()

class Manager:
    def __init__(self):
        self.active = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active.append(ws)

    def disconnect(self, ws: WebSocket):
        if ws in self.active:
            self.active.remove(ws)

    async def broadcast(self, event: str, data: dict | None = None):
        dead = []
        for ws in self.active:
            try:
                await ws.send_text(json.dumps({"event": event, "data": data or {}}))
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)

manager = Manager()

@router.websocket("/ws/queue")
async def ws_queue(ws: WebSocket):
    await manager.connect(ws)
    try:
        while True:
            await ws.receive_text()   # keepalive; clients never need to send anything
    except WebSocketDisconnect:
        manager.disconnect(ws)
