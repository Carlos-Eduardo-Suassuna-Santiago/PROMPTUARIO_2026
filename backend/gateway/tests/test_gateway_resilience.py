import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from fastapi import HTTPException
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from gateway.app.main import app


class FakeRedis:
    def __init__(self):
        self.store = {}
        self.closed = False

    async def incr(self, key):
        self.store[key] = self.store.get(key, 0) + 1
        return self.store[key]

    async def expire(self, key, ttl):
        self.store[f"{key}:ttl"] = ttl

    async def exists(self, key):
        return 1 if key in self.store else 0

    async def get(self, key):
        return self.store.get(key)

    async def setex(self, key, ttl, value):
        self.store[key] = value
        self.store[f"{key}:ttl"] = ttl

    async def aclose(self):
        self.closed = True


@pytest.fixture
def client():
    app.state.redis = FakeRedis()
    app.state.http_client = httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json={"ok": True}))
    )
    app.state.circuit_breakers = {}
    app.state.circuit_breaker_lock = asyncio.Lock()
    with TestClient(app) as test_client:
        yield test_client


def test_cacheable_route_returns_cached_response(client):
    cached_response = JSONResponse(status_code=200, content={"cached": True})
    with patch("gateway.app.main.decode_token", return_value=SimpleNamespace(sub="user-1", role="ADMIN", email="admin@example.com")):
        with patch("gateway.app.main._get_cached_response", new=AsyncMock(return_value=cached_response)) as cached_mock:
            response = client.get(
                "/api/v1/patients/health",
                headers={"Authorization": "Bearer test"},
            )

    assert response.status_code == 200
    assert response.json() == {"cached": True}
    cached_mock.assert_awaited_once()


def test_circuit_breaker_returns_fallback_when_service_fails(client):
    async def failing_forward(*args, **kwargs):
        raise httpx.ConnectError("boom")

    with patch("gateway.app.main.decode_token", return_value=SimpleNamespace(sub="user-1", role="ADMIN", email="admin@example.com")):
        with patch("gateway.app.main._forward_to_service", new=AsyncMock(side_effect=failing_forward)):
            response = client.get(
                "/api/v1/patients/health",
                headers={"Authorization": "Bearer test"},
            )

    assert response.status_code == 503
    assert response.json()["detail"] == "Serviço temporariamente indisponível"


def test_api_key_rate_limit_is_enforced(client):
    async def rate_limited(*args, **kwargs):
        raise HTTPException(status_code=429, detail="too many")

    with patch("gateway.app.main.decode_token", return_value=SimpleNamespace(sub="user-1", role="ADMIN", email="admin@example.com")):
        with patch("gateway.app.main._check_rate_limit", new=AsyncMock(side_effect=rate_limited)):
            response = client.get("/api/v1/patients/health", headers={"X-Api-Key": "demo-key"})

    assert response.status_code == 429


def test_gzip_response_is_served_when_requested(client):
    large_payload = {"message": "x" * 1500}
    with patch("gateway.app.main.decode_token", return_value=SimpleNamespace(sub="user-1", role="ADMIN", email="admin@example.com")):
        with patch(
            "gateway.app.main._forward_to_service",
            new=AsyncMock(
                return_value=JSONResponse(status_code=200, content=large_payload)
            ),
        ):
            response = client.get(
                "/api/v1/patients/health",
                headers={"Authorization": "Bearer test", "Accept-Encoding": "gzip"},
            )

    assert response.status_code == 200
    assert "gzip" in response.headers.get("content-encoding", "")
