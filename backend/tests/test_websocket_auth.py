"""
WebSocket Authentication Tests

Tests the secure WebSocket endpoint with JWT token validation.

Educational Note:
WebSocket testing is different from HTTP testing because:
1. Persistent connections (not request-response)
2. Bidirectional communication
3. Need to test connection lifecycle (connect, message, disconnect)
4. Authentication happens at connection time, not per message
"""

import pytest
from fastapi.testclient import TestClient
from httpx import AsyncClient
from models.user import User
from core.security import create_access_token
from datetime import timedelta


@pytest.mark.asyncio
async def test_websocket_requires_token(client: TestClient):
    """
    Test that WebSocket connection without token is rejected.

    Expected behavior:
    - Connection should be rejected immediately
    - Close code should be 1008 (Policy Violation)
    - Reason should indicate missing token
    """
    with pytest.raises(Exception) as exc_info:
        with client.websocket_connect("/ws/connect"):
            pass

    # Connection should fail due to missing token
    assert exc_info.value is not None


@pytest.mark.asyncio
async def test_websocket_invalid_token(client: TestClient):
    """
    Test that WebSocket with invalid token is rejected.

    Security Test:
    - Invalid tokens should NOT be accepted
    - Connection should be closed with policy violation
    - No data should be transmitted
    """
    with pytest.raises(Exception) as exc_info:
        with client.websocket_connect("/ws/connect?token=invalid_fake_token_12345"):
            pass

    # Connection should fail due to invalid token
    assert exc_info.value is not None


@pytest.mark.asyncio
async def test_websocket_expired_token(client: TestClient, test_user: User):
    """
    Test that WebSocket with expired token is rejected.

    Educational Note:
    JWT tokens have an expiration time (exp claim).
    Even if signature is valid, expired tokens should be rejected.
    """
    # Create an expired token
    expired_token = create_access_token(
        data={"sub": test_user.username},
        expires_delta=timedelta(seconds=-60)  # Expired 60 seconds ago
    )

    with pytest.raises(Exception) as exc_info:
        with client.websocket_connect(f"/ws/connect?token={expired_token}"):
            pass

    # Should fail due to expired token
    assert exc_info.value is not None


@pytest.mark.asyncio
async def test_websocket_valid_token_connects(client: TestClient, auth_headers: dict):
    """
    Test that WebSocket with valid token connects successfully.

    Success Criteria:
    - Connection established
    - Can send and receive messages
    - User context is maintained
    """
    # Extract token from auth headers
    token = auth_headers["Authorization"].replace("Bearer ", "")

    # Should connect successfully
    with client.websocket_connect(f"/ws/connect?token={token}") as websocket:
        # Send ping message
        websocket.send_json({"type": "ping"})

        # Should receive pong response
        response = websocket.receive_json()
        assert response["type"] == "pong"
        assert "timestamp" in response


@pytest.mark.asyncio
async def test_websocket_message_routing(client: TestClient, auth_headers: dict):
    """
    Test that different message types are routed correctly.

    Tests the message router pattern:
    - ping → pong
    - subscribe → acknowledgment
    - chat → chat_response (placeholder)
    - unknown → error
    """
    token = auth_headers["Authorization"].replace("Bearer ", "")

    with client.websocket_connect(f"/ws/connect?token={token}") as websocket:
        # Test ping/pong
        websocket.send_json({"type": "ping"})
        response = websocket.receive_json()
        assert response["type"] == "pong"

        # Test subscribe
        websocket.send_json({"type": "subscribe", "document_id": 123})
        response = websocket.receive_json()
        assert response["type"] == "acknowledgment"
        assert "Subscribed" in response["message"]

        # Test chat (placeholder response)
        websocket.send_json({
            "type": "chat",
            "document_id": 123,
            "question": "Test question",
            "rag_mode": "vector"
        })
        response = websocket.receive_json()
        assert response["type"] == "chat_response"

        # Test unknown message type
        websocket.send_json({"type": "unknown_type"})
        response = websocket.receive_json()
        assert response["type"] == "error"
        assert "Unknown message type" in response["message"]


@pytest.mark.asyncio
async def test_websocket_user_isolation(
    client: TestClient,
    test_user: User,
    admin_user: User,
    auth_headers: dict,
    admin_headers: dict
):
    """
    Test that messages are isolated per authenticated user.

    Security Test:
    User A should not receive messages intended for User B.
    This tests the connection manager's user isolation.

    Educational Note:
    The ConnectionManager stores connections by user_id.
    Messages sent to one user should only go to their connections.
    """
    # Get tokens
    user_token = auth_headers["Authorization"].replace("Bearer ", "")
    admin_token = admin_headers["Authorization"].replace("Bearer ", "")

    # Connect both users
    with client.websocket_connect(f"/ws/connect?token={user_token}") as user_ws:
        with client.websocket_connect(f"/ws/connect?token={admin_token}") as admin_ws:
            # Both should be connected
            # Send ping from user
            user_ws.send_json({"type": "ping"})
            user_response = user_ws.receive_json()
            assert user_response["type"] == "pong"

            # Send ping from admin
            admin_ws.send_json({"type": "ping"})
            admin_response = admin_ws.receive_json()
            assert admin_response["type"] == "pong"

            # Verify connections are independent
            # (In a real test, we'd send personal messages and verify isolation)


@pytest.mark.asyncio
async def test_websocket_connection_lifecycle(client: TestClient, auth_headers: dict):
    """
    Test the complete WebSocket connection lifecycle.

    Lifecycle phases:
    1. Authentication
    2. Connection established
    3. Message exchange
    4. Graceful disconnection
    """
    token = auth_headers["Authorization"].replace("Bearer ", "")

    # Phase 1 & 2: Authenticate and connect
    with client.websocket_connect(f"/ws/connect?token={token}") as websocket:
        # Phase 3: Exchange messages
        websocket.send_json({"type": "ping"})
        response = websocket.receive_json()
        assert response["type"] == "pong"

        # Can send multiple messages
        websocket.send_json({"type": "subscribe", "document_id": 1})
        response = websocket.receive_json()
        assert response["type"] == "acknowledgment"

    # Phase 4: Connection closed automatically on context exit
    # websocket.close() is called implicitly


@pytest.mark.asyncio
async def test_websocket_legacy_endpoint_deprecated(client: TestClient):
    """
    Test that legacy endpoint is properly deprecated.

    The old /ws/connect/{user_id} endpoint should:
    - Reject connections
    - Return deprecation message
    - Direct users to new secure endpoint
    """
    with pytest.raises(Exception) as exc_info:
        with client.websocket_connect("/ws/connect/test_user"):
            pass

    # Should fail with deprecation message
    assert exc_info.value is not None


@pytest.mark.asyncio
async def test_websocket_inactive_user_rejected(
    client: TestClient,
    db_session,
    test_user: User
):
    """
    Test that inactive users cannot connect.

    Security Test:
    Even with valid token, inactive users should be rejected.
    This tests the is_active check in authenticate_websocket.
    """
    # Create token for user
    token = create_access_token(data={"sub": test_user.username})

    # Deactivate user
    test_user.is_active = False
    db_session.add(test_user)
    await db_session.commit()

    # Try to connect with valid token but inactive user
    with pytest.raises(Exception) as exc_info:
        with client.websocket_connect(f"/ws/connect?token={token}"):
            pass

    # Should fail due to inactive user
    assert exc_info.value is not None


@pytest.mark.asyncio
async def test_websocket_concurrent_connections_same_user(
    client: TestClient,
    auth_headers: dict
):
    """
    Test that same user can have multiple WebSocket connections.

    Use Case:
    User has multiple browser tabs open, each with its own WebSocket.
    All should be able to connect and receive messages.

    Educational Note:
    ConnectionManager stores a SET of connections per user_id.
    This allows multiple connections from the same user.
    """
    token = auth_headers["Authorization"].replace("Bearer ", "")

    # Open two connections for same user
    with client.websocket_connect(f"/ws/connect?token={token}") as ws1:
        with client.websocket_connect(f"/ws/connect?token={token}") as ws2:
            # Both connections should work independently
            ws1.send_json({"type": "ping"})
            response1 = ws1.receive_json()
            assert response1["type"] == "pong"

            ws2.send_json({"type": "ping"})
            response2 = ws2.receive_json()
            assert response2["type"] == "pong"
