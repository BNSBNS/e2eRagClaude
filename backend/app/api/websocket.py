# app/api/websocket.py
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import Dict, List
import json

router = APIRouter()

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}
    
    async def connect(self, websocket: WebSocket, user_id: str):
        await websocket.accept()
        if user_id not in self.active_connections:
            self.active_connections[user_id] = []
        self.active_connections[user_id].append(websocket)
    
    def disconnect(self, websocket: WebSocket, user_id: str):
        self.active_connections[user_id].remove(websocket)
        if not self.active_connections[user_id]:
            del self.active_connections[user_id]
    
    async def send_personal_message(self, message: str, user_id: str):
        if user_id in self.active_connections:
            for connection in self.active_connections[user_id]:
                await connection.send_text(message)

manager = ConnectionManager()

@router.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: str):
    await manager.connect(websocket, user_id)
    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            
            # Handle different message types
            if message["type"] == "chat":
                # Process chat message and send response
                response = await process_chat_message(message["content"], user_id)
                await manager.send_personal_message(
                    json.dumps({"type": "chat_response", "content": response}),
                    user_id
                )
            elif message["type"] == "document_processing":
                # Send processing updates
                await manager.send_personal_message(
                    json.dumps({"type": "processing_update", "status": "processing"}),
                    user_id
                )
                
    except WebSocketDisconnect:
        manager.disconnect(websocket, user_id)