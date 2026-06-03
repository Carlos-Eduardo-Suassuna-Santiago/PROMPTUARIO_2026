from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

TEST_FILE = Path(__file__).resolve()
SHARED_ROOT = TEST_FILE.parents[1]
BACKEND_ROOT = TEST_FILE.parents[2]

for path in (SHARED_ROOT, BACKEND_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from shared.observability import setup_observability  # noqa: E402


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
async def test_request_id_propagates_to_response_header():
    app = FastAPI()
    setup_observability(app, service_name="test-service", log_level="INFO")

    @app.get("/healthz")
    async def healthz():
        return {"status": "ok"}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/healthz", headers={"X-Request-Id": "req-abc-123"})

    assert response.status_code == 200
    assert response.headers.get("X-Request-Id") == "req-abc-123"


@pytest.mark.anyio
async def test_request_id_is_generated_when_missing():
    app = FastAPI()
    setup_observability(app, service_name="test-service", log_level="INFO")

    @app.get("/healthz")
    async def healthz():
        return {"status": "ok"}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/healthz")

    assert response.status_code == 200
    generated_id = response.headers.get("X-Request-Id")
    assert generated_id is not None
    assert len(generated_id) >= 8
