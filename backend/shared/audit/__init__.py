"""
Módulo de auditoria compartilhado.
Registra operações relevantes em tabela audit_logs em cada banco de serviço.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import DateTime, Index, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from shared.models.database import Base
from shared.observability import get_request_context


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _uuid() -> str:
    return str(uuid.uuid4())


class AuditLog(Base):
    """
    Tabela de auditoria imutável.
    Criada em CADA banco (iam_db, patient_db, clinical_db) via Base.metadata.create_all.
    Nunca atualiza ou deleta registros — apenas insere.
    """

    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    service_name: Mapped[str] = mapped_column(String(50), nullable=False)
    table_name: Mapped[str] = mapped_column(String(100), nullable=False)
    operation: Mapped[str] = mapped_column(String(30), nullable=False)
    record_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    user_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    user_role: Mapped[str | None] = mapped_column(String(20), nullable=True)
    user_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    old_values: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    new_values: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    request_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )

    __table_args__ = (
        Index("ix_audit_logs_service_timestamp", "service_name", "timestamp"),
        Index("ix_audit_logs_user_id", "user_id"),
        Index("ix_audit_logs_operation", "operation"),
        Index("ix_audit_logs_correlation_id", "correlation_id"),
    )


_SENSITIVE_FIELDS = frozenset({
    "password",
    "hashed_password",
    "token",
    "access_token",
    "refresh_token",
    "token_hash",
    "authorization",
    "secret",
    "api_key",
    "cookie",
    "session",
    "jwt",
    "bearer",
    "credit_card",
    "cvv",
    "ssn",
    "medical_history_raw",
})


def sanitize_payload(payload: Any) -> Any:
    """Recursively redact sensitive content from payloads before storage or logging."""
    if isinstance(payload, dict):
        return {key: "[REDACTED]" if _looks_sensitive(key) else sanitize_payload(value) for key, value in payload.items()}
    if isinstance(payload, (list, tuple)):
        return [sanitize_payload(item) for item in payload]
    if isinstance(payload, str):
        return "[REDACTED]" if _looks_sensitive_text(payload) else payload
    return payload


def _looks_sensitive(key: str) -> bool:
    lowered = key.lower().replace("-", "_")
    return any(token in lowered for token in _SENSITIVE_FIELDS)


def _looks_sensitive_text(value: str) -> bool:
    lowered = value.lower()
    return any(token in lowered for token in ("password", "token", "secret", "authorization", "api_key", "session", "bearer", "jwt"))


def build_audit_event(
    *,
    service: str,
    operation: str,
    target: str | None = None,
    user: str | None = None,
    request_id: str | None = None,
    correlation_id: str | None = None,
    old_values: dict | None = None,
    new_values: dict | None = None,
    details: dict | None = None,
) -> dict[str, Any]:
    context = get_request_context()
    event_request_id = request_id or context.get("request_id")
    event_correlation_id = correlation_id or context.get("correlation_id")
    return {
        "event": "audit",
        "service": service,
        "operation": operation,
        "target": target or "unknown",
        "user": user or context.get("user_id") or context.get("user_email") or "anonymous",
        "timestamp": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "request_id": event_request_id,
        "correlation_id": event_correlation_id,
        "old_values": sanitize_payload(old_values),
        "new_values": sanitize_payload(new_values),
        "details": sanitize_payload(details),
    }


async def log_operation(
    session,
    *,
    service: str,
    table: str,
    operation: str,
    record_id: str | None = None,
    user_id: str | None = None,
    user_role: str | None = None,
    user_email: str | None = None,
    old_values: dict | None = None,
    new_values: dict | None = None,
    ip_address: str | None = None,
    request_id: str | None = None,
    correlation_id: str | None = None,
) -> None:
    """
    Registra uma operação de auditoria na sessão ativa.

    IMPORTANTE:
    - Não faz commit — o commit é responsabilidade do método de serviço que chama esta função.
    - Em caso de erro, loga o erro mas NÃO propaga a exceção
      (auditoria não deve quebrar a operação principal).
    - Deve ser chamado ANTES do commit do serviço para participar da mesma transação.
    """
    _logger = logging.getLogger("audit")
    try:
        context = get_request_context()
        event_request_id = request_id or context.get("request_id")
        event_correlation_id = correlation_id or context.get("correlation_id")
        event_ip_address = ip_address or context.get("ip_address")
        event = build_audit_event(
            service=service,
            operation=operation,
            target=record_id or table,
            user=user_id or user_email,
            request_id=event_request_id,
            correlation_id=event_correlation_id,
            old_values=old_values,
            new_values=new_values,
            details={"table": table, "user_role": user_role, "ip_address": event_ip_address},
        )
        entry = AuditLog(
            service_name=service,
            table_name=table,
            operation=operation,
            record_id=record_id,
            user_id=user_id,
            user_role=user_role,
            user_email=user_email,
            old_values=sanitize_payload(old_values),
            new_values=sanitize_payload(new_values),
            ip_address=event_ip_address,
            request_id=event_request_id,
            correlation_id=event_correlation_id,
        )
        session.add(entry)
        _logger.info("audit_event", extra={"audit_event": event})
    except Exception as exc:
        _logger.error(
            "Falha ao registrar audit log: service=%s table=%s op=%s err=%s",
            service,
            table,
            operation,
            exc,
        )