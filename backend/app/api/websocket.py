"""
WebSocket API Router
Location: backend/api/websocket.py

Handles real-time communication between backend and frontend:
- Document processing updates
- AI query streaming
- System notifications
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status
from typing import Dict, Set
import structlog
import json
import asyncio

logger = structlog.get_logger()

# Create router
router = APIRouter()


# ============================================================================
# CONNECTION MANAGER
# ============================================================================

class ConnectionManager:
    """
    Manages WebSocket connections.
    
    Allows broadcasting messages to:
    - All connected clients
    - Specific user
    - Specific room/channel
    
    Why WebSockets?
    - Real-time updates without polling
    - Bidirectional communication
    - Lower latency than HTTP polling
    - Efficient for live data streams
    """
    
    def __init__(self):
        # Store active connections by user_id
        self.active_connections: Dict[str, Set[WebSocket]] = {}
    
    async def connect(self, websocket: WebSocket, user_id: str):
        """Accept and store a new connection"""
        await websocket.accept()
        
        if user_id not in self.active_connections:
            self.active_connections[user_id] = set()
        
        self.active_connections[user_id].add(websocket)
        logger.info("WebSocket connected", user_id=user_id)
    
    def disconnect(self, websocket: WebSocket, user_id: str):
        """Remove a connection"""
        if user_id in self.active_connections:
            self.active_connections[user_id].discard(websocket)
            
            # Clean up empty sets
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]
        
        logger.info("WebSocket disconnected", user_id=user_id)
    
    async def send_personal_message(self, message: dict, user_id: str):
        """Send message to specific user (all their connections)"""
        if user_id in self.active_connections:
            disconnected = []
            
            for connection in self.active_connections[user_id]:
                try:
                    await connection.send_json(message)
                except Exception as e:
                    logger.error("Failed to send message", error=str(e))
                    disconnected.append(connection)
            
            # Remove failed connections
            for conn in disconnected:
                self.disconnect(conn, user_id)
    
    async def broadcast(self, message: dict):
        """Send message to all connected clients"""
        for user_id in list(self.active_connections.keys()):
            await self.send_personal_message(message, user_id)


# Global connection manager instance
manager = ConnectionManager()


# ============================================================================
# WEBSOCKET ENDPOINTS
# ============================================================================

@router.websocket("/connect/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: str):
    """
    Main WebSocket connection endpoint.
    
    Message Types:
    1. processing_update: Document processing status
    2. query_stream: Streaming AI responses
    3. notification: System notifications
    
    Example message:
    {
        "type": "processing_update",
        "document_id": 123,
        "status": "processing",
        "progress": 50,
        "message": "Generating embeddings..."
    }
    """
    await manager.connect(websocket, user_id)
    
    try:
        while True:
            # Receive messages from client
            data = await websocket.receive_text()
            message = json.loads(data)
            
            logger.info("WebSocket message received", user_id=user_id, message=message)
            
            # Echo back for now (placeholder)
            await manager.send_personal_message({
                "type": "acknowledgment",
                "message": f"Received: {message}"
            }, user_id)
            
    except WebSocketDisconnect:
        manager.disconnect(websocket, user_id)
        logger.info("Client disconnected", user_id=user_id)
    except Exception as e:
        logger.error("WebSocket error", error=str(e), user_id=user_id)
        manager.disconnect(websocket, user_id)


# ============================================================================
# HELPER FUNCTIONS (for use by other services)
# ============================================================================

async def send_processing_update(user_id: str, document_id: int, status: str, progress: int, message: str):
    """
    Send document processing update to user.
    
    Called by background processing tasks to update frontend.
    """
    await manager.send_personal_message({
        "type": "processing_update",
        "document_id": document_id,
        "status": status,
        "progress": progress,
        "message": message
    }, user_id)


async def send_query_stream(user_id: str, chunk: str, done: bool = False):
    """
    Stream AI response chunks to user.
    
    For real-time display of AI-generated text (like ChatGPT streaming).
    """
    await manager.send_personal_message({
        "type": "query_stream",
        "chunk": chunk,
        "done": done
    }, user_id)


async def send_notification(user_id: str, title: str, message: str, level: str = "info"):
    """
    Send notification to user.
    
    Levels: info, success, warning, error
    """
    await manager.send_personal_message({
        "type": "notification",
        "title": title,
        "message": message,
        "level": level
    }, user_id)