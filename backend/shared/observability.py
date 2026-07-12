from __future__ import annotations

import logging
import os
import sys
import threading
import uuid as _uuid
from typing import Any

from fastapi import FastAPI
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from prometheus_client import Counter, Gauge, Histogram, make_asgi_app
import time as _time
from pythonjsonlogger import jsonlogger

logger = logging.getLogger(__name__)

_context_storage = threading.local()


def set_request_context(**values: str | None) -> None:
    current = getattr(_context_storage, "values", {})
    current.update({k: v for k, v in values.items() if v is not None})
    _context_storage.values = current


def get_request_context() -> dict[str, str]:
    return getattr(_context_storage, "values", {}).copy()


def clear_request_context() -> None:
    _context_storage.values = {}


def register_resilience_metrics(app: FastAPI, service_name: str) -> dict[str, Any]:
    cache_hits_total = Counter(
        "gateway_cache_hits_total",
        "Cache hits for gateway responses",
        ["service", "route"],
    )
    cache_misses_total = Counter(
        "gateway_cache_misses_total",
        "Cache misses for gateway responses",
        ["service", "route"],
    )
    circuit_open_total = Counter(
        "gateway_circuit_open_total",
        "Times the gateway circuit breaker opened",
        ["service", "target"],
    )
    circuit_state = Gauge(
        "gateway_circuit_state",
        "Current circuit breaker state for downstream targets",
        ["service", "target"],
    )
    return {
        "cache_hits_total": cache_hits_total,
        "cache_misses_total": cache_misses_total,
        "circuit_open_total": circuit_open_total,
        "circuit_state": circuit_state,
    }


def setup_observability(app: FastAPI, service_name: str, log_level: str = "INFO") -> None:
    try:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(
            jsonlogger.JsonFormatter(
                fmt="%(asctime)s %(levelname)s %(name)s %(message)s",
                rename_fields={
                    "asctime": "timestamp",
                    "levelname": "level",
                    "name": "service",
                },
            )
        )
        root_logger = logging.getLogger()
        root_logger.handlers.clear()
        root_logger.addHandler(handler)
        root_logger.setLevel(getattr(logging, log_level))

        resource = Resource.create({"service.name": service_name})
        provider = TracerProvider(resource=resource)
        otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://otel-collector:4317")
        try:
            exporter = OTLPSpanExporter(endpoint=otlp_endpoint, insecure=True)
            provider.add_span_processor(BatchSpanProcessor(exporter))
        except Exception as e:
            logger.warning("OTel exporter unavailable: %s", e)
        trace.set_tracer_provider(provider)

        FastAPIInstrumentor.instrument_app(app)
        try:
            from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
            SQLAlchemyInstrumentor().instrument()
        except ImportError:
            pass
        try:
            from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
            HTTPXClientInstrumentor().instrument()
        except ImportError:
            pass


        http_requests_total = Counter(
            "http_requests_total",
            "Total HTTP requests",
            ["service", "method", "endpoint", "status_code"],
        )
        http_requests_4xx_total = Counter(
            "http_requests_4xx_total",
            "HTTP 4xx errors",
            ["service", "method", "endpoint"],
        )
        http_requests_rejected_total = Counter(
            "http_requests_rejected_total",
            "Requisições rejeitadas (rate limit / auth)",
            ["service", "reason"],
        )
        http_request_duration = Histogram(
            "http_request_duration_seconds",
            "HTTP request duration",
            ["service", "method", "endpoint"],
            buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
        )
        http_request_size_bytes = Histogram(
            "http_request_size_bytes",
            "Tamanho das requisições HTTP",
            ["service", "method"],
            buckets=[100, 1000, 10000, 100000, 1000000],
        )
        http_response_size_bytes = Histogram(
            "http_response_size_bytes",
            "Tamanho das respostas HTTP",
            ["service", "method"],
            buckets=[100, 1000, 10000, 100000, 1000000],
        )
        service_start_time = Gauge(
            "service_start_time_seconds",
            "Timestamp de início do serviço",
            ["service"],
        )
        service_start_time.labels(service=service_name).set(_time.time())

        # ─── Audit-specific metrics ─────────────────────────────────
        audit_events_total = Counter(
            "audit_events_total",
            "Total de eventos de auditoria emitidos",
            ["service", "operation"],
        )
        audit_events_failed_total = Counter(
            "audit_events_failed_total",
            "Total de falhas ao registrar auditoria",
            ["service"],
        )

        # ─── Unified request context middleware ─────────────────────
        @app.middleware("http")
        async def request_context_middleware(request, call_next):
            request_id = request.headers.get("X-Request-Id") or request.headers.get("x-request-id") or str(_uuid.uuid4())
            correlation_id = request.headers.get("X-Correlation-Id") or request.headers.get("x-correlation-id") or request_id
            ip_address = request.client.host if request.client else "unknown"
            user_id = request.headers.get("X-User-Id") or request.headers.get("x-user-id")
            user_email = request.headers.get("X-User-Email") or request.headers.get("x-user-email")
            set_request_context(
                request_id=request_id,
                correlation_id=correlation_id,
                ip_address=ip_address,
                user_id=user_id,
                user_email=user_email,
            )
            request.state.request_id = request_id
            request.state.correlation_id = correlation_id
            request.state.ip_address = ip_address
            response = await call_next(request)
            response.headers["X-Request-Id"] = request_id
            response.headers["X-Correlation-Id"] = correlation_id
            clear_request_context()
            return response

        @app.middleware("http")
        async def metrics_middleware(request, call_next):
            import time as _time_module

            start = _time_module.time()
            body_size = len(request.headers.get("content-length", "0") or "0")
            http_request_size_bytes.labels(
                service=service_name,
                method=request.method,
            ).observe(int(body_size))
            response = await call_next(request)
            duration = _time_module.time() - start
            endpoint = request.url.path
            http_requests_total.labels(
                service=service_name,
                method=request.method,
                endpoint=endpoint,
                status_code=response.status_code,
            ).inc()
            if 400 <= response.status_code < 500:
                http_requests_4xx_total.labels(
                    service=service_name,
                    method=request.method,
                    endpoint=endpoint,
                ).inc()
            http_request_duration.labels(
                service=service_name,
                method=request.method,
                endpoint=endpoint,
            ).observe(duration)
            resp_size = len(response.body) if hasattr(response, "body") else 0
            http_response_size_bytes.labels(
                service=service_name,
                method=request.method,
            ).observe(resp_size)
            return response

        metrics_app = make_asgi_app()
        app.mount("/metrics", metrics_app)

    except Exception as e:
        logger.error("Observability setup failed (service continues): %s", e)