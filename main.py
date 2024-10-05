from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from typing import Dict, List, Tuple
from datetime import datetime, timedelta
import base64

app = FastAPI()


class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[int, WebSocket] = {}
        self.messages: Dict[int, List[Tuple[str, datetime]]] = {}

    async def connect(self, websocket: WebSocket, client_id: int):
        await websocket.accept()
        self.active_connections[client_id] = websocket
        if client_id in self.messages:
            self.clean_old_messages(client_id)
            for message, _ in self.messages[client_id]:
                await websocket.send_text(message)

    def disconnect(self, client_id: int):
        del self.active_connections[client_id]

    async def send_personal_message(self, message: str, client_id: int):
        websocket = self.active_connections.get(client_id)
        if websocket:
            await websocket.send_text(message)
        else:
            if client_id not in self.messages:
                self.messages[client_id] = []
            self.messages[client_id].append((message, datetime.now()))

    async def send_file(self, file_type: str, file_data: str, target_id: int):
        if target_id in self.active_connections:
            websocket = self.active_connections[target_id]

            await websocket.send_text(f"FILE:{file_type}:{file_data}")
            await websocket.send_text("EOF")

    async def broadcast(self, message: str):
        for connection in self.active_connections.values():
            await connection.send_text(message)

    def clean_old_messages(self, client_id: int):
        if client_id in self.messages:
            three_months_ago = datetime.now() - timedelta(days=90)
            self.messages[client_id] = [
                (msg, timestamp)
                for msg, timestamp in self.messages[client_id]
                if timestamp > three_months_ago
            ]


manager = ConnectionManager()


@app.get("/")
async def get():
    return {"message": "WebSocket server is running."}


@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: int):
    await manager.connect(websocket, client_id)
    try:
        while True:
            data = await websocket.receive_text()
            if data.startswith("FILE:"):
                _, file_type, target_id, file_data = data.split(":", 3)
                target_id = int(target_id)
                await manager.send_file(file_type, file_data, target_id)
            else:
                target_id, message = data.split(":", 1)
                target_id = int(target_id)
                await manager.send_personal_message(message, target_id)
    except WebSocketDisconnect:
        manager.disconnect(client_id)
        await manager.broadcast(f"Usuario {client_id} ha salido del chat.")
