from __future__ import annotations

import logging
import os
import sys
import uuid as _uuid

from fastapi import FastAPI
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from prometheus_client import Counter, Histogram, make_asgi_app
from pythonjsonlogger import jsonlogger

logger = logging.getLogger(__name__)


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
        http_request_duration = Histogram(
            "http_request_duration_seconds",
            "HTTP request duration",
            ["service", "method", "endpoint"],
        )

        @app.middleware("http")
        async def metrics_middleware(request, call_next):
            import time

            start = time.time()
            response = await call_next(request)
            duration = time.time() - start
            endpoint = request.url.path
            http_requests_total.labels(
                service=service_name,
                method=request.method,
                endpoint=endpoint,
                status_code=response.status_code,
            ).inc()
            http_request_duration.labels(
                service=service_name,
                method=request.method,
                endpoint=endpoint,
            ).observe(duration)
            return response

        metrics_app = make_asgi_app()
        app.mount("/metrics", metrics_app)

        @app.middleware("http")
        async def request_id_middleware(request, call_next):
            request_id = request.headers.get("X-Request-Id", str(_uuid.uuid4()))
            response = await call_next(request)
            response.headers["X-Request-Id"] = request_id
            return response

    except Exception as e:
        logger.error("Observability setup failed (service continues): %s", e)
