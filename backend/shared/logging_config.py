from __future__ import annotations

import logging
import sys
from datetime import datetime, timezone

from pythonjsonlogger import jsonlogger

from shared.middleware.observability import request_context


class PromptuarioJsonFormatter(jsonlogger.JsonFormatter):
    """JSON formatter that normalizes the log schema expected by observability."""

    def add_fields(self, log_record, record, message_dict):
        super().add_fields(log_record, record, message_dict)

        timestamp = datetime.fromtimestamp(record.created, timezone.utc).isoformat()
        log_record["timestamp"] = log_record.get("timestamp") or timestamp
        log_record["level"] = (log_record.get("level") or record.levelname).lower()
        log_record["service"] = log_record.get("service") or request_context.service_name.get()
        log_record["module"] = log_record.get("module") or record.module
        log_record["request_id"] = log_record.get("request_id") or request_context.request_id.get()
        log_record["user_id"] = log_record.get("user_id") or request_context.user_id.get()
        log_record["duration_ms"] = log_record.get("duration_ms")
        log_record["status_code"] = log_record.get("status_code")
        log_record["message"] = log_record.get("message") or record.getMessage()

        # Keep schema-compatible dotted keys while avoiding invalid LogRecord attrs.
        log_record["http.method"] = log_record.get("http.method") or getattr(record, "http_method", None)
        log_record["http.path"] = log_record.get("http.path") or getattr(record, "http_path", None)


class _ContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.service = getattr(record, "service", request_context.service_name.get())
        record.request_id = getattr(record, "request_id", request_context.request_id.get())
        record.user_id = getattr(record, "user_id", request_context.user_id.get())
        return True


def configure_logging(service_name: str, level: str = "INFO") -> None:
    """Configures root logger with JSON output and correlated context fields."""
    request_context.service_name.set(service_name)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(PromptuarioJsonFormatter())
    handler.addFilter(_ContextFilter())

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Keep noisy internals at warning while preserving service logs.
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("opentelemetry").setLevel(logging.WARNING)
