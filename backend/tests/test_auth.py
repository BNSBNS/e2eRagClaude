"""
Test authentication endpoints
"""

import pytest
from httpx import AsyncClient
from models.user import User


@pytest.mark.asyncio
async def test_signup_success(client: AsyncClient):
    """Test successful user registration"""
    response = await client.post(
        "/api/auth/signup",
        json={
            "username": "newuser",
            "email": "new@example.com",
            "password": "newpass123",
            "full_name": "New User"
        }
    )
    
    assert response.status_code == 201
    data = response.json()
    assert data["username"] == "newuser"
    assert data["email"] == "new@example.com"
    assert "password" not in data


@pytest.mark.asyncio
async def test_signup_duplicate_username(client: AsyncClient, test_user: User):
    """Test signup with duplicate username fails"""
    response = await client.post(
        "/api/auth/signup",
        json={
            "username": "testuser",  # Already exists
            "email": "another@example.com",
            "password": "pass123"
        }
    )
    
    assert response.status_code == 400
    assert "Username already registered" in response.json()["detail"]


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient, test_user: User):
    """Test successful login"""
    response = await client.post(
        "/api/auth/login",
        data={"username": "testuser", "password": "testpass123"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["expires_in"] == 1800


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient, test_user: User):
    """Test login with wrong password fails"""
    response = await client.post(
        "/api/auth/login",
        data={"username": "testuser", "password": "wrongpass"}
    )
    
    assert response.status_code == 401
    assert "Incorrect username or password" in response.json()["detail"]


@pytest.mark.asyncio
async def test_get_current_user(client: AsyncClient, auth_headers: dict):
    """Test getting current user info"""
    response = await client.get("/api/auth/me", headers=auth_headers)
    
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "testuser"
    assert data["email"] == "test@example.com"


@pytest.mark.asyncio
async def test_unauthorized_access(client: AsyncClient):
    """Test accessing protected route without token fails"""
    response = await client.get("/api/auth/me")
    
    assert response.status_code == 401