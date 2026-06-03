from __future__ import annotations

import logging
import os
import time
from contextlib import contextmanager
from typing import Iterator

from fastapi import FastAPI, Response
from opentelemetry import context, propagate, trace
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.psycopg2 import Psycopg2Instrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.propagate import extract
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest, start_http_server

from shared.logging_config import configure_logging
from shared.middleware.observability import RequestContextMiddleware, request_context


logger = logging.getLogger(__name__)

HTTP_REQUESTS_TOTAL = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["service", "route", "method", "status"],
)
HTTP_REQUEST_DURATION = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["service", "route"],
)
RABBITMQ_QUEUE_LENGTH = Gauge(
    "rabbitmq_queue_length",
    "Current RabbitMQ queue length",
    ["service", "queue"],
)
WORKER_JOB_DURATION = Histogram(
    "worker_job_duration_seconds",
    "Background worker job duration in seconds",
    ["service", "job_type"],
)

_TRACING_INITIALIZED = False
_HTTPX_INSTRUMENTED = False
_PSYCOPG2_INSTRUMENTED = False
_WORKER_METRICS_SERVER_STARTED = False


class _CarrierGetter:
    @staticmethod
    def get(carrier: dict, key: str):
        value = carrier.get(key)
        if value is None:
            return []
        return [value]

    @staticmethod
    def keys(carrier: dict):
        return list(carrier.keys())


class _CarrierSetter:
    @staticmethod
    def set(carrier: dict, key: str, value: str):
        carrier[key] = value


def setup_observability(app: FastAPI, service_name: str, log_level: str = "INFO") -> None:
    configure_logging(service_name=service_name, level=log_level)
    _setup_tracing(service_name)

    app.add_middleware(RequestContextMiddleware, service_name=service_name)
    FastAPIInstrumentor.instrument_app(app)

    global _HTTPX_INSTRUMENTED
    if not _HTTPX_INSTRUMENTED:
        HTTPXClientInstrumentor().instrument()
        _HTTPX_INSTRUMENTED = True

    @app.get("/metrics", include_in_schema=False)
    async def metrics_endpoint() -> Response:
        return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

    @app.middleware("http")
    async def prometheus_http_metrics(request, call_next):
        started = time.perf_counter()
        response = await call_next(request)
        elapsed = time.perf_counter() - started

        route_path = request.url.path
        if request.scope.get("route") is not None:
            route_path = getattr(request.scope["route"], "path", route_path)

        HTTP_REQUESTS_TOTAL.labels(
            service=service_name,
            route=route_path,
            method=request.method,
            status=str(response.status_code),
        ).inc()
        HTTP_REQUEST_DURATION.labels(service=service_name, route=route_path).observe(elapsed)
        return response


def setup_worker_observability(service_name: str, log_level: str = "INFO") -> None:
    configure_logging(service_name=service_name, level=log_level)
    _setup_tracing(service_name)
    instrument_psycopg2_once()


def instrument_sqlalchemy_engine(engine) -> None:
    SQLAlchemyInstrumentor().instrument(engine=engine.sync_engine)


def instrument_psycopg2_once() -> None:
    global _PSYCOPG2_INSTRUMENTED
    if _PSYCOPG2_INSTRUMENTED:
        return
    Psycopg2Instrumentor().instrument()
    _PSYCOPG2_INSTRUMENTED = True


def set_rabbitmq_queue_length(service: str, queue: str, size: int) -> None:
    RABBITMQ_QUEUE_LENGTH.labels(service=service, queue=queue).set(size)


@contextmanager
def worker_job_duration(service: str, job_type: str) -> Iterator[None]:
    start = time.perf_counter()
    try:
        yield
    finally:
        WORKER_JOB_DURATION.labels(service=service, job_type=job_type).observe(time.perf_counter() - start)


def start_worker_metrics_server(port: int) -> None:
    global _WORKER_METRICS_SERVER_STARTED
    if _WORKER_METRICS_SERVER_STARTED:
        return
    start_http_server(port)
    _WORKER_METRICS_SERVER_STARTED = True


def build_message_headers() -> dict[str, str]:
    headers: dict[str, str] = {
        "x-request-id": request_context.request_id.get(),
        "x-user-id": request_context.user_id.get(),
    }
    propagate.inject(headers, setter=_CarrierSetter())
    return headers


def context_from_message_headers(headers: dict | None):
    carrier = {}
    if headers:
        for key, value in headers.items():
            normalized = str(key).lower()
            carrier[normalized] = value.decode() if isinstance(value, bytes) else str(value)
    return extract(carrier, getter=_CarrierGetter())


def start_consumer_span(service_name: str, routing_key: str, message_headers: dict | None):
    tracer = trace.get_tracer(service_name)
    parent_ctx = context_from_message_headers(message_headers)
    span_name = f"rabbitmq.consume {routing_key}"
    return tracer.start_as_current_span(span_name, context=parent_ctx)


def _setup_tracing(service_name: str) -> None:
    global _TRACING_INITIALIZED
    if _TRACING_INITIALIZED:
        return

    resource = Resource.create({"service.name": service_name})
    provider = TracerProvider(resource=resource)

    otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")
    provider.add_span_processor(
        BatchSpanProcessor(OTLPSpanExporter(endpoint=otlp_endpoint, insecure=True))
    )

    jaeger_host = os.getenv("JAEGER_AGENT_HOST")
    jaeger_port = int(os.getenv("JAEGER_AGENT_PORT", "6831"))
    if jaeger_host:
        provider.add_span_processor(
            BatchSpanProcessor(JaegerExporter(agent_host_name=jaeger_host, agent_port=jaeger_port))
        )

    trace.set_tracer_provider(provider)
    _TRACING_INITIALIZED = True
    logger.info("Tracing initialized", extra={"service": service_name})
