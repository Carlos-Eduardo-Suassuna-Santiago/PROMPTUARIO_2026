"""
Módulo de auditoria compartilhado.
Registra operações relevantes em tabela audit_logs em cada banco de serviço.
"""
from __future__ import annotations
import uuid
from datetime import datetime, timezone
from typing import Any
from contextvars import ContextVar

from sqlalchemy import DateTime, JSON, String, Index
from sqlalchemy.orm import Mapped, mapped_column

from shared.models.database import Base

audit_context_var: ContextVar[dict[str, Any]] = ContextVar("audit_context_var", default={})


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
    # Operações: INSERT, UPDATE, DELETE, AUTH_LOGIN, AUTH_LOGIN_FAILED,
    #            AUTH_LOGOUT, PASSWORD_CHANGE, TOKEN_REVOKE
    record_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    user_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    user_role: Mapped[str | None] = mapped_column(String(20), nullable=True)
    user_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    old_values: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    new_values: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    request_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )

    __table_args__ = (
        Index("ix_audit_logs_service_timestamp", "service_name", "timestamp"),
        Index("ix_audit_logs_user_id", "user_id"),
        Index("ix_audit_logs_operation", "operation"),
    )


# Campos que nunca devem aparecer nos logs
_SENSITIVE_FIELDS = frozenset({"hashed_password", "token_hash", "password"})


def _mask_dict(d: dict | None) -> dict | None:
    """Remove campos sensíveis de dicionários antes de persistir."""
    if not d:
        return d
    return {
        k: "[REDACTED]" if k in _SENSITIVE_FIELDS else v
        for k, v in d.items()
    }


async def log_operation(
    session,  # AsyncSession existente da request
    *,        # keyword-only para evitar erros de ordem
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
) -> None:
    """
    Registra uma operação de auditoria na sessão ativa.

    IMPORTANTE:
    - Não faz commit — o commit é responsabilidade do método de serviço que chama esta função.
    - Em caso de erro, loga o erro mas NÃO propaga a exceção
      (auditoria não deve quebrar a operação principal).
    - Deve ser chamado ANTES do commit do serviço para participar da mesma transação.
    """
    import logging
    _logger = logging.getLogger(__name__)
    try:
        ctx = audit_context_var.get()
        if user_id is None:
            user_id = ctx.get("user_id")
        if user_role is None:
            user_role = ctx.get("user_role")
        if user_email is None:
            user_email = ctx.get("user_email")
        if ip_address is None:
            ip_address = ctx.get("ip_address")
        if request_id is None:
            request_id = ctx.get("request_id")

        entry = AuditLog(
            service_name=service,
            table_name=table,
            operation=operation,
            record_id=record_id,
            user_id=user_id,
            user_role=user_role,
            user_email=user_email,
            old_values=_mask_dict(old_values),
            new_values=_mask_dict(new_values),
            ip_address=ip_address,
            request_id=request_id,
        )
        session.add(entry)
        # Sem flush aqui: o caller decide quando fazer flush/commit
    except Exception as exc:
        _logger.error(
            "Falha ao registrar audit log: service=%s table=%s op=%s err=%s",
            service, table, operation, exc,
        )