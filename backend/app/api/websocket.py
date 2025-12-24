"""
WebSocket API Router
Location: backend/api/websocket.py

Handles real-time communication between backend and frontend:
- Document processing updates
- AI query streaming
- System notifications

SECURITY: All WebSocket connections now require JWT authentication
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status, Query, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Dict, Set
import structlog
import json
import asyncio

from core.database import get_db
from core.security import decode_access_token
from models.user import User

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
# AUTHENTICATION
# ============================================================================

async def authenticate_websocket(token: str, db: AsyncSession) -> User:
    """
    Validate JWT token for WebSocket connection.

    Educational Note:
    WebSockets maintain persistent connections, unlike HTTP requests.
    We validate the JWT token ONCE when the connection is established,
    not on every message (which would be inefficient).

    Why separate from REST auth?
    - WebSocket uses query params, not OAuth2PasswordBearer scheme
    - Need to validate once at connection time
    - Must return User object for connection context

    Args:
        token: JWT access token from client
        db: Database session for user lookup

    Returns:
        User object if authentication successful

    Raises:
        HTTPException: If token is invalid or user not found
    """
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No authentication token provided"
        )

    # Decode JWT token (reusing existing security function)
    username = decode_access_token(token)
    if username is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token"
        )

    # Fetch user from database
    result = await db.execute(
        select(User).where(User.username == username)
    )
    user = result.scalar_one_or_none()

    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive"
        )

    return user


# ============================================================================
# WEBSOCKET ENDPOINTS
# ============================================================================

@router.websocket("/connect")
async def websocket_endpoint(
    websocket: WebSocket,
    token: str = Query(..., description="JWT access token for authentication"),
    db: AsyncSession = Depends(get_db)
):
    """
    Secure WebSocket endpoint with JWT validation.

    **IMPORTANT SECURITY CHANGE:**
    This endpoint now requires JWT authentication via query parameter.

    Connection URL Format:
        ws://localhost:8000/ws/connect?token=<JWT_TOKEN>

    Why Query Parameter for Token?
    - WebSocket spec doesn't support custom headers in browser clients
    - Query params work across all WebSocket implementations
    - Alternative approaches (subprotocol, first message) are more complex

    Message Types:
    1. ping: Keep-alive heartbeat
    2. chat: RAG query with document context
    3. subscribe: Subscribe to document processing updates

    Response Types:
    1. pong: Heartbeat response
    2. chat_response: Complete AI answer
    3. chat_partial: Streaming response chunk
    4. processing_update: Document processing status
    5. error: Error message

    Example message:
    {
        "type": "chat",
        "document_id": 123,
        "question": "What is RAG?",
        "rag_mode": "vector"
    }
    """
    try:
        # CRITICAL: Authenticate BEFORE accepting connection
        user = await authenticate_websocket(token, db)

        # Authentication successful - accept connection
        await manager.connect(websocket, str(user.id))

        logger.info("Authenticated WebSocket connection",
                   user_id=user.id,
                   username=user.username)

        # Store user context for message handling
        try:
            while True:
                # Receive messages from client
                data = await websocket.receive_text()
                message = json.loads(data)

                # All messages now have authenticated user context
                logger.info("WebSocket message received",
                           user_id=user.id,
                           username=user.username,
                           message_type=message.get('type'))

                # Handle different message types
                await handle_websocket_message(websocket, user, message)

        except WebSocketDisconnect:
            manager.disconnect(websocket, str(user.id))
            logger.info("Client disconnected", user_id=user.id)

    except HTTPException as e:
        # Reject connection for invalid tokens
        logger.warning("WebSocket authentication failed",
                      reason=e.detail)
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason=e.detail)
    except Exception as e:
        logger.error("WebSocket error", error=str(e))
        await websocket.close(code=status.WS_1011_INTERNAL_ERROR, reason="Internal server error")


async def handle_websocket_message(websocket: WebSocket, user: User, message: dict):
    """
    Route WebSocket messages to appropriate handlers.

    Educational Note:
    This is a message router pattern. Each message type has its own handler,
    making the code modular and testable.

    Message Types:
    - ping: Keep-alive heartbeat (prevents connection timeout)
    - chat: RAG query (will integrate with agents in Phase 3)
    - subscribe: Subscribe to document updates
    - unsubscribe: Unsubscribe from updates

    Args:
        websocket: Active WebSocket connection
        user: Authenticated user object
        message: Parsed JSON message from client
    """
    message_type = message.get('type')

    if message_type == 'ping':
        # Heartbeat response
        await websocket.send_json({
            'type': 'pong',
            'timestamp': asyncio.get_event_loop().time()
        })

    elif message_type == 'chat':
        # Chat message (placeholder for Phase 3 agent integration)
        document_id = message.get('document_id')
        question = message.get('question')
        rag_mode = message.get('rag_mode', 'vector')

        logger.info("Chat message received",
                   user_id=user.id,
                   document_id=document_id,
                   rag_mode=rag_mode)

        # TODO: Integrate with RAG agents in Phase 3
        await websocket.send_json({
            'type': 'chat_response',
            'answer': 'Chat functionality will be integrated with RAG agents in Phase 3',
            'document_id': document_id
        })

    elif message_type == 'subscribe':
        # Subscribe to document processing updates
        document_id = message.get('document_id')
        logger.info("Client subscribed to document updates",
                   user_id=user.id,
                   document_id=document_id)

        await websocket.send_json({
            'type': 'acknowledgment',
            'message': f'Subscribed to document {document_id} updates'
        })

    else:
        # Unknown message type
        logger.warning("Unknown message type",
                      user_id=user.id,
                      message_type=message_type)

        await websocket.send_json({
            'type': 'error',
            'message': f'Unknown message type: {message_type}'
        })


# ============================================================================
# BACKWARD COMPATIBILITY
# ============================================================================

@router.websocket("/connect/{user_id}")
async def websocket_endpoint_legacy(websocket: WebSocket, user_id: str):
    """
    DEPRECATED: Legacy endpoint without authentication.

    This endpoint is kept for backward compatibility but will be removed.
    Use /ws/connect?token=<JWT> instead.

    WARNING: This endpoint is insecure and should not be used in production.
    """
    logger.warning("Legacy WebSocket endpoint called (insecure)",
                  user_id=user_id)

    await websocket.close(
        code=status.WS_1008_POLICY_VIOLATION,
        reason="This endpoint is deprecated. Use /ws/connect?token=<JWT> instead."
    )


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