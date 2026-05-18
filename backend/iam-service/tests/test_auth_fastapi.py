from __future__ import annotations

import sys
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine


TEST_FILE = Path(__file__).resolve()
IAM_SERVICE_ROOT = TEST_FILE.parents[1]
REPO_ROOT = TEST_FILE.parents[2]

for path in (IAM_SERVICE_ROOT, REPO_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


class _FakeRedis:
    async def aclose(self) -> None:
        return None


@pytest.fixture
async def app_client(monkeypatch, tmp_path: Path):
    db_path = tmp_path / "iam-fastapi.db"
    database_url = f"sqlite+aiosqlite:///{db_path.as_posix()}"

    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/15")
    monkeypatch.setenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-key-for-fastapi-tests")

    from app import main as app_main

    async def _fake_connect(self) -> None:
        return None

    async def _fake_from_url(*args, **kwargs):
        return _FakeRedis()

    def _test_build_engine(url: str):
        return create_async_engine(url, echo=False)

    monkeypatch.setattr(app_main.EventPublisher, "connect", _fake_connect)
    monkeypatch.setattr(app_main, "build_engine", _test_build_engine)
    monkeypatch.setattr(app_main.aioredis, "from_url", _fake_from_url)

    await app_main.app.router.startup()
    try:
        async with AsyncClient(transport=ASGITransport(app=app_main.app), base_url="http://test") as client:
            yield client
    finally:
        await app_main.app.router.shutdown()


@pytest.mark.anyio
async def test_fastapi_auth_flow(app_client: AsyncClient):
    login_response = await app_client.post(
        "/api/v1/auth/login",
        json={"email": "admin@promptuario.health", "password": "Admin@12345"},
    )

    assert login_response.status_code == 200
    login_data = login_response.json()
    assert "access_token" in login_data
    assert "refresh_token" in login_data

    access_token = login_data["access_token"]
    refresh_token = login_data["refresh_token"]

    me_response = await app_client.get(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert me_response.status_code == 200
    me_data = me_response.json()
    assert me_data["email"] == "admin@promptuario.health"
    assert me_data["role"] == "ADMIN"

    refresh_response = await app_client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert refresh_response.status_code == 200
    refresh_data = refresh_response.json()
    assert "access_token" in refresh_data
    assert "refresh_token" in refresh_data

    logout_response = await app_client.post(
        "/api/v1/auth/logout",
        json={"refresh_token": refresh_token},
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert logout_response.status_code == 204