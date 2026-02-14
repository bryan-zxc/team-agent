import uuid
from fastapi import WebSocket


class ConnectionManager:
    def __init__(self):
        self._connections: dict[uuid.UUID, list[WebSocket]] = {}

    async def connect(self, chat_id: uuid.UUID, websocket: WebSocket):
        await websocket.accept()
        if chat_id not in self._connections:
            self._connections[chat_id] = []
        self._connections[chat_id].append(websocket)

    def disconnect(self, chat_id: uuid.UUID, websocket: WebSocket):
        if chat_id in self._connections:
            self._connections[chat_id].remove(websocket)
            if not self._connections[chat_id]:
                del self._connections[chat_id]

    async def broadcast(self, chat_id: uuid.UUID, data: dict):
        for ws in self._connections.get(chat_id, []):
            await ws.send_json(data)


manager = ConnectionManager()
