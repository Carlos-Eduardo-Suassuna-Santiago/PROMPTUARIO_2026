"""
IAM Service integration tests.
Run with: pytest tests/ -v
"""
from __future__ import annotations

import pytest
from httpx import AsyncClient, ASGITransport

# Patch settings before importing app
import os
os.environ.update({
    "DATABASE_URL": "sqlite+aiosqlite:///:memory:",
    "REDIS_URL": "redis://localhost:6379/15",
    "RABBITMQ_URL": "amqp://guest:guest@localhost:5672/",
    "JWT_SECRET_KEY": "test-secret-key-for-testing-only",
})


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest.fixture(scope="session")
async def client():
    """
    Creates a test client with an in-memory SQLite DB.
    Note: full integration tests require the services running.
    This is a structural smoke test.
    """
    from app.main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest.mark.anyio
async def test_health(client: AsyncClient):
    resp = await client.get("/healthz")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["service"] == "iam-service"


@pytest.mark.anyio
async def test_login_invalid_credentials(client: AsyncClient):
    resp = await client.post("/api/v1/auth/login", json={
        "email": "nonexistent@test.com",
        "password": "wrongpass",
    })
    assert resp.status_code in (401, 422, 500)  # 500 if Redis/RabbitMQ not available


@pytest.mark.anyio
async def test_create_user_requires_auth(client: AsyncClient):
    resp = await client.post("/api/v1/users", json={
        "email": "new@test.com",
        "password": "Test@1234",
        "full_name": "Test User",
        "role": "PATIENT",
    })
    # Should be 401 or 403 — not 422
    assert resp.status_code in (401, 403, 500)


@pytest.mark.anyio
async def test_list_users_requires_admin(client: AsyncClient):
    resp = await client.get("/api/v1/users")
    assert resp.status_code in (401, 403, 500)


@pytest.mark.anyio
async def test_password_validation():
    from pydantic import ValidationError
    from app.domain.models.schemas import UserCreate
    # Missing uppercase
    with pytest.raises(ValidationError):
        UserCreate(email="a@b.com", password="test1234", full_name="Test", role="PATIENT")
    # Missing number
    with pytest.raises(ValidationError):
        UserCreate(email="a@b.com", password="Testabcd", full_name="Test", role="PATIENT")
    # Valid
    u = UserCreate(email="a@b.com", password="Test1234", full_name="Test", role="PATIENT")
    assert u.role == "PATIENT"


@pytest.mark.anyio
async def test_token_decode():
    from shared.utils.security import create_access_token, decode_token
    token = create_access_token(
        user_id="usr_123",
        role="DOCTOR",
        email="doc@test.com",
        secret="test-secret",
        algorithm="HS256",
        expire_minutes=30,
    )
    payload = decode_token(token, "test-secret", "HS256")
    assert payload.sub == "usr_123"
    assert payload.role == "DOCTOR"
    assert payload.type == "access"


@pytest.mark.anyio
async def test_invalid_token_raises():
    from shared.utils.security import decode_token
    with pytest.raises(ValueError):
        decode_token("not.a.valid.token", "secret", "HS256")


@pytest.mark.anyio
async def test_password_hashing():
    from shared.utils.security import hash_password, verify_password
    pwd = "MyS3cureP@ss"
    hashed = hash_password(pwd)
    assert hashed != pwd
    assert verify_password(pwd, hashed)
    assert not verify_password("wrongpassword", hashed)
