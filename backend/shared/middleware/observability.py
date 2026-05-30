from __future__ import annotations

import logging
import time
import uuid
from contextvars import ContextVar

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware


logger = logging.getLogger(__name__)


class _RequestContext:
    request_id: ContextVar[str] = ContextVar("request_id", default="")
    user_id: ContextVar[str] = ContextVar("user_id", default="anonymous")
    service_name: ContextVar[str] = ContextVar("service_name", default="unknown-service")


request_context = _RequestContext()


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Injects correlation context into logs, traces and HTTP responses."""

    def __init__(self, app, service_name: str):
        super().__init__(app)
        self._service_name = service_name

    async def dispatch(self, request: Request, call_next):
        received_request_id = request.headers.get("X-Request-Id")
        request_id = received_request_id or str(uuid.uuid4())
        user_id = request.headers.get("X-User-Id", "anonymous")

        token_request = request_context.request_id.set(request_id)
        token_user = request_context.user_id.set(user_id)
        token_service = request_context.service_name.set(self._service_name)

        request.state.request_id = request_id
        request.state.user_id = user_id
        request.state.service_name = self._service_name

        start = time.perf_counter()
        response: Response | None = None

        try:
            response = await call_next(request)
            return response
        finally:
            duration_ms = round((time.perf_counter() - start) * 1000.0, 2)
            resolved_user_id = getattr(request.state, "authenticated_user_id", user_id)
            route_path = request.url.path
            if request.scope.get("route") is not None:
                route_path = getattr(request.scope["route"], "path", route_path)

            status_code = response.status_code if response else 500
            logger.info(
                "request.completed",
                extra={
                    "user_id": resolved_user_id,
                    "duration_ms": duration_ms,
                    "status_code": status_code,
                    "http_method": request.method,
                    "http_path": route_path,
                },
            )

            if response is not None:
                response.headers["X-Request-Id"] = request_id

            request_context.request_id.reset(token_request)
            request_context.user_id.reset(token_user)
            request_context.service_name.reset(token_service)
